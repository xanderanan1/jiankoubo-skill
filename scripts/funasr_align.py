#!/usr/bin/env python3
"""Run FunASR and normalize timestamps to the skill alignment schema."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


CJK_RE = re.compile(r"[\u3400-\u9fff]")
PUNCT_RE = re.compile(r"^[\s，。！？!?、：:；;“”\"'（）()《》【】\[\]\{\}<>,.]+$")


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
    work_dir = work_dir or Path(tempfile.mkdtemp(prefix="funasr-align-"))
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


def import_automodel() -> Any:
    try:
        from funasr import AutoModel  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "FunASR is not installed. Install it with: "
            "python3 -m pip install -U funasr modelscope soundfile"
        ) from exc
    return AutoModel


def automodel_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": args.model,
        "disable_update": True,
    }
    if args.device:
        kwargs["device"] = args.device
    if args.mode == "asr":
        if args.vad_model:
            kwargs["vad_model"] = args.vad_model
        if args.punc_model:
            kwargs["punc_model"] = args.punc_model
    return kwargs


def generate_asr(model: Any, wav: Path, args: argparse.Namespace) -> Any:
    params: dict[str, Any] = {"input": str(wav), "batch_size_s": args.batch_size_s}
    if args.hotword:
        params["hotword"] = args.hotword
    return model.generate(**params)


def generate_force_align(model: Any, wav: Path, script: str, args: argparse.Namespace) -> Any:
    """Try common FunASR forced-alignment call shapes.

    FunASR has changed examples across releases. Keep the script tolerant so the
    skill can survive small API shifts while still failing with useful context.
    """

    attempts: list[tuple[str, dict[str, Any]]] = [
        ("input tuple with inline text", {"input": (str(wav), script), "data_type": ("sound", "text")}),
        ("input wav with text kwarg", {"input": str(wav), "text": script}),
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as handle:
        handle.write(script)
        text_path = Path(handle.name)
    attempts.append(
        ("input tuple with text file", {"input": (str(wav), str(text_path)), "data_type": ("sound", "text")})
    )

    errors: list[str] = []
    for label, params in attempts:
        try:
            params.setdefault("batch_size_s", args.batch_size_s)
            return model.generate(**params)
        except Exception as exc:  # pragma: no cover - depends on installed FunASR release.
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
    raise SystemExit("FunASR forced alignment failed:\n" + "\n".join(errors))


def as_list(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        return [result]
    return []


def timestamp_pairs(raw: Any) -> list[tuple[Any, Any]]:
    pairs: list[tuple[Any, Any]] = []
    if not isinstance(raw, list):
        return pairs
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            pairs.append((item[0], item[1]))
        elif isinstance(item, dict):
            start = item.get("start") or item.get("start_time") or item.get("start_ms")
            end = item.get("end") or item.get("end_time") or item.get("end_ms")
            if start is not None and end is not None:
                pairs.append((start, end))
    return pairs


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def to_ms(value: Any, timestamp_unit: str = "ms") -> int:
    numeric = float(value)
    if timestamp_unit == "s":
        numeric *= 1000
    return int(round(numeric))


def normalize_token(text: str) -> str:
    return text.strip()


def char_tokens(text: str) -> list[str]:
    return [char for char in text if char.strip() and not PUNCT_RE.match(char)]


def word_tokens(text: str) -> list[str]:
    if CJK_RE.search(text):
        return char_tokens(text)
    return [token for token in re.split(r"\s+", text.strip()) if token and not PUNCT_RE.match(token)]


def words_from_text_and_timestamps(
    text: str,
    timestamps: list[tuple[Any, Any]],
    timestamp_unit: str,
) -> list[dict[str, Any]]:
    tokens = word_tokens(text)
    if not tokens or not timestamps:
        return []

    words: list[dict[str, Any]] = []
    if len(tokens) == len(timestamps):
        for token, (start, end) in zip(tokens, timestamps):
            words.append(
                {
                    "text": normalize_token(token),
                    "start_time": to_ms(start, timestamp_unit),
                    "end_time": to_ms(end, timestamp_unit),
                }
            )
        return [word for word in words if word["text"] and word["end_time"] >= word["start_time"]]

    # FunASR Chinese timestamps are often character-level. If the text tokenizes
    # differently, distribute timestamps across visible non-punctuation chars.
    chars = char_tokens(text)
    if len(chars) == len(timestamps):
        for token, (start, end) in zip(chars, timestamps):
            words.append({"text": token, "start_time": to_ms(start, timestamp_unit), "end_time": to_ms(end, timestamp_unit)})
        return [word for word in words if word["end_time"] >= word["start_time"]]

    # Last-resort proportional timing keeps the downstream pipeline usable, but
    # it should only happen when the model output has coarse utterance timings.
    start_ms = to_ms(timestamps[0][0], timestamp_unit)
    end_ms = to_ms(timestamps[-1][1], timestamp_unit)
    span = max(1, end_ms - start_ms)
    for index, token in enumerate(tokens):
        token_start = start_ms + round(span * index / len(tokens))
        token_end = start_ms + round(span * (index + 1) / len(tokens))
        words.append({"text": token, "start_time": token_start, "end_time": max(token_end, token_start + 40)})
    return words


def utterance_from_item(item: dict[str, Any], timestamp_unit: str) -> list[dict[str, Any]]:
    utterances: list[dict[str, Any]] = []
    sentence_info = item.get("sentence_info")
    if isinstance(sentence_info, list) and sentence_info:
        for sentence in sentence_info:
            if not isinstance(sentence, dict):
                continue
            text = str(sentence.get("text") or sentence.get("sentence") or "").strip()
            timestamps = timestamp_pairs(sentence.get("timestamp") or sentence.get("timestamps"))
            start = first_present(sentence.get("start"), sentence.get("start_time"), timestamps[0][0] if timestamps else None)
            end = first_present(sentence.get("end"), sentence.get("end_time"), timestamps[-1][1] if timestamps else None)
            words = words_from_text_and_timestamps(text, timestamps, timestamp_unit)
            if text and start is not None and end is not None:
                utterances.append(
                    {
                        "text": text,
                        "start_time": to_ms(start, timestamp_unit),
                        "end_time": to_ms(end, timestamp_unit),
                        "words": words,
                    }
                )
        return utterances

    text = str(item.get("text") or "").strip()
    timestamps = timestamp_pairs(item.get("timestamp") or item.get("timestamps"))
    words = words_from_text_and_timestamps(text, timestamps, timestamp_unit)
    if words:
        utterances.append(
            {
                "text": text or "".join(str(word["text"]) for word in words),
                "start_time": words[0]["start_time"],
                "end_time": words[-1]["end_time"],
                "words": words,
            }
        )
    return utterances


def normalize_result(
    result: Any,
    source: str,
    media: Path,
    duration_ms: int | None,
    timestamp_unit: str = "ms",
) -> dict[str, Any]:
    utterances: list[dict[str, Any]] = []
    for item in as_list(result):
        utterances.extend(utterance_from_item(item, timestamp_unit))
    utterances = [utt for utt in utterances if utt.get("words")]
    utterances.sort(key=lambda item: (int(item["start_time"]), int(item["end_time"])))
    return {
        "source": source,
        "media": str(media.resolve()),
        "duration_ms": duration_ms,
        "utterances": utterances,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create normalized alignment JSON with FunASR.")
    parser.add_argument("media", type=Path, help="Audio or video file.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-output", type=Path, help="Optional raw FunASR JSON output.")
    parser.add_argument("--work-dir", type=Path, help="Directory for extracted wav files.")
    parser.add_argument("--mode", choices=["asr", "force-align"], default="asr")
    parser.add_argument("--model", default=None, help="FunASR model name. Defaults to paraformer-zh or fa-zh.")
    parser.add_argument("--vad-model", default="fsmn-vad", help="ASR mode VAD model; empty string disables it.")
    parser.add_argument("--punc-model", default="ct-punc", help="ASR mode punctuation model; empty string disables it.")
    parser.add_argument("--device", default="", help="Optional FunASR device, e.g. cpu, cuda:0, mps.")
    parser.add_argument("--batch-size-s", type=int, default=300)
    parser.add_argument("--timestamp-unit", choices=["ms", "s"], default="ms")
    parser.add_argument("--hotword", help="Optional FunASR hotword string.")
    parser.add_argument("--script", help="Target or full script for force-align mode.")
    parser.add_argument("--script-file", type=Path, help="Script file for force-align mode.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.model:
        args.model = "fa-zh" if args.mode == "force-align" else "paraformer-zh"
    if args.vad_model == "":
        args.vad_model = None
    if args.punc_model == "":
        args.punc_model = None

    script = args.script or (args.script_file.read_text(encoding="utf-8") if args.script_file else "")
    if args.mode == "force-align" and not script.strip():
        raise SystemExit("--script or --script-file is required in force-align mode")

    duration_ms = media_duration_ms(args.media)
    wav = ensure_wav(args.media, args.work_dir)
    AutoModel = import_automodel()
    model = AutoModel(**automodel_kwargs(args))
    raw = generate_force_align(model, wav, script, args) if args.mode == "force-align" else generate_asr(model, wav, args)

    if args.raw_output:
        args.raw_output.parent.mkdir(parents=True, exist_ok=True)
        args.raw_output.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    normalized = normalize_result(raw, f"funasr:{args.mode}:{args.model}", args.media, duration_ms, args.timestamp_unit)
    if not normalized["utterances"]:
        raise SystemExit("FunASR returned no usable word or character timestamps")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
