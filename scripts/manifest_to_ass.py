#!/usr/bin/env python3
"""Convert a render manifest's subtitles into an ASS subtitle file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def ass_time(ms: int) -> str:
    total_centiseconds = max(0, round(ms / 10))
    centiseconds = total_centiseconds % 100
    total_seconds = total_centiseconds // 100
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def escape_ass(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def build_ass(manifest: dict) -> str:
    width = manifest["output"]["width"]
    height = manifest["output"]["height"]
    font_size = 58 if height > width else 44
    margin_v = 130 if height > width else 80
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,PingFang SC,{font_size},&H00FFFFFF,&H00FFFFFF,&HCC000000,&H99000000,-1,0,0,0,100,100,0,0,1,4,1,2,48,48,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for subtitle in manifest.get("subtitles", []):
        text = escape_ass(subtitle["text"])
        lines.append(
            f"Dialogue: 0,{ass_time(subtitle['start_ms'])},{ass_time(subtitle['end_ms'])},Default,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert manifest subtitles to ASS.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.output.write_text(build_ass(manifest), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
