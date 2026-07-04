#!/usr/bin/env python3
"""Probe video metadata with ffprobe and infer orientation."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def probe(path: Path) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,duration,r_frame_rate",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    stream = (payload.get("streams") or [{}])[0]
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    orientation = "horizontal" if width >= height else "vertical"
    return {
        "path": str(path.resolve()),
        "width": width,
        "height": height,
        "orientation": orientation,
        "duration": stream.get("duration"),
        "r_frame_rate": stream.get("r_frame_rate"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe media metadata.")
    parser.add_argument("video", type=Path)
    args = parser.parse_args()
    print(json.dumps(probe(args.video), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
