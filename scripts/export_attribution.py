#!/usr/bin/env python3
"""Export attribution metadata from a render manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Write manifest.attribution to a sidecar JSON file.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    attribution = manifest.get("attribution") or []
    if not isinstance(attribution, list):
        raise SystemExit("manifest.attribution must be a list")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(attribution, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
