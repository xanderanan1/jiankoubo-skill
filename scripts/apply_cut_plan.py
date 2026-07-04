#!/usr/bin/env python3
"""Apply keep segments from a cut plan to a video with ffmpeg."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def build_filter(segments: list[dict[str, int]]) -> str:
    filter_parts: list[str] = []
    labels: list[str] = []
    for index, segment in enumerate(segments):
        start = segment["start_ms"] / 1000
        end = segment["end_ms"] / 1000
        filter_parts.append(f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{index}]")
        filter_parts.append(f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{index}]")
        labels.append(f"[v{index}][a{index}]")
    return ";".join(filter_parts) + ";" + "".join(labels) + f"concat=n={len(segments)}:v=1:a=1[outv][outa]"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a cleaned video from cut-plan keep segments.")
    parser.add_argument("video", type=Path)
    parser.add_argument("cut_plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--crf", type=int, default=20)
    parser.add_argument("--preset", default="veryfast")
    args = parser.parse_args()

    plan = json.loads(args.cut_plan.read_text(encoding="utf-8"))
    segments = plan.get("keep_segments") or []
    if not segments:
        raise SystemExit("cut plan has no keep_segments")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(args.video),
        "-filter_complex",
        build_filter(segments),
        "-map",
        "[outv]",
        "-map",
        "[outa]",
        "-c:v",
        "libx264",
        "-preset",
        args.preset,
        "-crf",
        str(args.crf),
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(args.output),
    ]
    subprocess.run(command, check=True)
    print(args.output)


if __name__ == "__main__":
    main()
