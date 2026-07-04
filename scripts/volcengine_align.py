#!/usr/bin/env python3
"""Call Volcengine ATA and normalize word timings for the video skill."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


SUBMIT_URL = "https://openspeech.bytedance.com/api/v1/vc/ata/submit"
QUERY_URL = "https://openspeech.bytedance.com/api/v1/vc/ata/query"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def media_duration_ms(path: Path) -> int:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    return int(round(float(result.stdout.strip()) * 1000))


def ensure_wav(media: Path, work_dir: Path | None = None) -> Path:
    if media.suffix.lower() == ".wav":
        return media
    work_dir = work_dir or Path(tempfile.mkdtemp(prefix="volcengine-ata-"))
    work_dir.mkdir(parents=True, exist_ok=True)
    wav = work_dir / f"{media.stem}.16k.wav"
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(media),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(wav),
        ]
    )
    return wav


def first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return ""


def apply_runtime_credentials(args: argparse.Namespace) -> tuple[str, str]:
    """Use provided credentials for this process without writing them to disk."""

    if args.appid:
        os.environ["VOLCENGINE_ATA_APPID"] = args.appid
    if args.token:
        os.environ["VOLCENGINE_ATA_TOKEN"] = args.token

    appid = first_env("VOLCENGINE_ATA_APPID", "VOLCENGINE_APPID", "BYTEDANCE_ATA_APPID", "BYTEDANCE_APPID")
    token = first_env(
        "VOLCENGINE_ATA_TOKEN",
        "VOLCENGINE_ACCESS_TOKEN",
        "BYTEDANCE_ATA_TOKEN",
        "BYTEDANCE_ACCESS_TOKEN",
    )
    missing = []
    if not appid:
        missing.append("VOLCENGINE_ATA_APPID")
    if not token:
        missing.append("VOLCENGINE_ATA_TOKEN")
    if missing:
        raise SystemExit(
            "Missing Volcengine ATA credentials: "
            + ", ".join(missing)
            + ". Provide them as environment variables or pass --appid and --token for this run."
        )
    return appid, token


def auth_headers(token: str, content_type: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "*/*",
        "Authorization": f"Bearer; {token}",
        "Connection": "keep-alive",
        "User-Agent": "codex-render-talking-video/1.0",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def request_json(url: str, headers: dict[str, str], body: bytes | None = None, method: str | None = None) -> dict[str, Any]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Volcengine ATA HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Volcengine ATA request failed: {exc}") from exc
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Volcengine ATA returned non-JSON response: {payload[:500]}") from exc


def multipart_body(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----codex-volcengine-{uuid.uuid4().hex}"
    lines: list[bytes] = []
    for name, value in fields.items():
        lines.extend(
            [
                f"--{boundary}".encode(),
                f'Content-Disposition: form-data; name="{name}"'.encode(),
                b"",
                value.encode("utf-8"),
            ]
        )
    mime = mimetypes.guess_type(file_path.name)[0] or "audio/wav"
    lines.extend(
        [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"'.encode(),
            f"Content-Type: {mime}".encode(),
            b"",
            file_path.read_bytes(),
            f"--{boundary}--".encode(),
            b"",
        ]
    )
    return b"\r\n".join(lines), f"multipart/form-data; boundary={boundary}"


def submit_audio(wav: Path, script: str, appid: str, token: str, args: argparse.Namespace) -> str:
    query = urllib.parse.urlencode(
        {
            "appid": appid,
            "caption_type": args.caption_type,
            "sta_punc_mode": str(args.sta_punc_mode),
        }
    )
    body, content_type = multipart_body({"audio-text": script, "audio_text": script}, "data", wav)
    payload = request_json(f"{SUBMIT_URL}?{query}", auth_headers(token, content_type), body, "POST")
    code = str(payload.get("code"))
    if code != "0":
        raise SystemExit(f"Volcengine ATA submit failed: code={payload.get('code')} message={payload.get('message')}")
    task_id = str(payload.get("id") or "")
    if not task_id:
        raise SystemExit(f"Volcengine ATA submit response has no task id: {payload}")
    return task_id


def query_result(task_id: str, appid: str, token: str, args: argparse.Namespace) -> dict[str, Any]:
    deadline = time.monotonic() + args.timeout_s
    last_payload: dict[str, Any] = {}
    while time.monotonic() < deadline:
        query = urllib.parse.urlencode({"appid": appid, "id": task_id, "blocking": "1" if args.blocking else "0"})
        payload = request_json(f"{QUERY_URL}?{query}", auth_headers(token), method="GET")
        last_payload = payload
        code = str(payload.get("code"))
        if code == "0":
            return payload
        if code != "2000":
            raise SystemExit(f"Volcengine ATA query failed: code={payload.get('code')} message={payload.get('message')}")
        if args.blocking:
            # Blocking query may still return processing on timeout/load; poll gently.
            time.sleep(args.poll_interval_s)
        else:
            time.sleep(args.poll_interval_s)
    raise SystemExit(f"Volcengine ATA query timed out after {args.timeout_s}s; last response: {last_payload}")


def to_ms(value: Any) -> int:
    return int(round(float(value)))


def normalize_word(raw: dict[str, Any]) -> dict[str, Any] | None:
    text = str(raw.get("text") or raw.get("word") or "").strip()
    start = raw.get("start_time", raw.get("start_ms", raw.get("start")))
    end = raw.get("end_time", raw.get("end_ms", raw.get("end")))
    if not text or start is None or end is None:
        return None
    start_ms = to_ms(start)
    end_ms = to_ms(end)
    if end_ms < start_ms:
        return None
    return {"text": text, "start_time": start_ms, "end_time": end_ms}


def normalize_utterance(raw: dict[str, Any]) -> dict[str, Any] | None:
    words = [word for item in raw.get("words", []) or [] if isinstance(item, dict) for word in [normalize_word(item)] if word]
    text = str(raw.get("text") or "".join(word["text"] for word in words)).strip()
    start = raw.get("start_time", raw.get("start_ms", raw.get("start")))
    end = raw.get("end_time", raw.get("end_ms", raw.get("end")))
    if words:
        start_ms = to_ms(start) if start is not None else words[0]["start_time"]
        end_ms = to_ms(end) if end is not None else words[-1]["end_time"]
    elif start is not None and end is not None and text:
        start_ms = to_ms(start)
        end_ms = to_ms(end)
    else:
        return None
    return {"text": text, "start_time": start_ms, "end_time": end_ms, "words": words}


def normalize_result(result: dict[str, Any], media: Path, duration_ms: int | None) -> dict[str, Any]:
    utterances = [
        utterance
        for item in result.get("utterances", []) or []
        if isinstance(item, dict)
        for utterance in [normalize_utterance(item)]
        if utterance and utterance.get("words")
    ]
    utterances.sort(key=lambda item: (int(item["start_time"]), int(item["end_time"])))
    reported_duration = result.get("duration")
    return {
        "source": "volcengine:ata",
        "media": str(media.resolve()),
        "duration_ms": int(round(float(reported_duration) * 1000)) if reported_duration is not None else duration_ms,
        "utterances": utterances,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create normalized alignment JSON with Volcengine ATA.")
    parser.add_argument("media", type=Path, help="Audio or video file.")
    parser.add_argument("--script", help="Target or full script text for alignment.")
    parser.add_argument("--script-file", type=Path, help="Path containing script text for alignment.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-output", type=Path, help="Optional raw Volcengine query JSON output.")
    parser.add_argument("--submit-output", type=Path, help="Optional submit response JSON output.")
    parser.add_argument("--work-dir", type=Path, help="Directory for extracted wav files.")
    parser.add_argument("--appid", help="Volcengine app id. Stored only in this process environment.")
    parser.add_argument("--token", help="Volcengine access token. Stored only in this process environment.")
    parser.add_argument("--caption-type", choices=["speech", "singing"], default="speech")
    parser.add_argument("--sta-punc-mode", choices=["1", "2", "3"], default="1")
    parser.add_argument("--blocking", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--timeout-s", type=int, default=300)
    parser.add_argument("--poll-interval-s", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    script = args.script or (args.script_file.read_text(encoding="utf-8") if args.script_file else "")
    if not script.strip():
        raise SystemExit("--script or --script-file is required for Volcengine ATA alignment")

    appid, token = apply_runtime_credentials(args)
    duration_ms = media_duration_ms(args.media)
    wav = ensure_wav(args.media, args.work_dir)
    task_id = submit_audio(wav, script, appid, token, args)
    submit_payload = {"code": 0, "message": "Success", "id": task_id}
    if args.submit_output:
        args.submit_output.parent.mkdir(parents=True, exist_ok=True)
        args.submit_output.write_text(json.dumps(submit_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    raw = query_result(task_id, appid, token, args)
    if args.raw_output:
        args.raw_output.parent.mkdir(parents=True, exist_ok=True)
        args.raw_output.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    normalized = normalize_result(raw, args.media, duration_ms)
    if not normalized["utterances"]:
        raise SystemExit("Volcengine ATA returned no usable word timings")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
