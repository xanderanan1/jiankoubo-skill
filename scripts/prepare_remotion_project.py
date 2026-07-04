#!/usr/bin/env python3
"""Prepare a Remotion project from a manifest and local media assets."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = SKILL_ROOT / "assets" / "remotion-template"


def public_path(path: str) -> bool:
    return bool(path) and not path.startswith("/") and "://" not in path


def copy_video(video: Path, project_dir: Path) -> str:
    target = project_dir / "public" / video.name
    target.parent.mkdir(parents=True, exist_ok=True)
    if video.resolve() != target.resolve():
        shutil.copy2(video, target)
    return video.name


def relative_audio_paths(manifest: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    audio = manifest.get("audio") or {}
    if not isinstance(audio, dict):
        return paths
    bgm = audio.get("bgm")
    if isinstance(bgm, dict) and isinstance(bgm.get("path"), str) and public_path(bgm["path"]):
        paths.append(bgm["path"])
    for item in audio.get("sfx", []) or []:
        if isinstance(item, dict) and isinstance(item.get("path"), str) and public_path(item["path"]):
            paths.append(item["path"])
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy the Remotion template and rewrite manifest media paths.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--video", type=Path, help="Clean video to copy into public/. Defaults to manifest.video.path when absolute.")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--manifest-name", default="manifest.json")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.project_dir.exists():
        if not args.overwrite:
            raise SystemExit(f"project dir already exists: {args.project_dir}")
        shutil.rmtree(args.project_dir)
    shutil.copytree(args.template, args.project_dir, ignore=shutil.ignore_patterns("node_modules", ".cache", "out"))

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    video = manifest.get("video") or {}
    if not isinstance(video, dict):
        raise SystemExit("manifest.video must be an object")

    video_path = str(video.get("path") or "")
    source_video = args.video
    if source_video is None and video_path.startswith("/"):
        source_video = Path(video_path)
    if source_video is not None:
        if not source_video.exists():
            raise SystemExit(f"video not found: {source_video}")
        video["path"] = copy_video(source_video, args.project_dir)
    elif not public_path(video_path):
        raise SystemExit("video path must be public-relative or provide --video")

    missing_assets = [path for path in relative_audio_paths(manifest) if not (args.project_dir / "public" / path).exists()]
    if missing_assets:
        raise SystemExit("missing public audio assets: " + ", ".join(missing_assets))

    manifest_path = args.project_dir / args.manifest_name
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_command = (
        f"node node_modules/@remotion/cli/remotion-cli.js render "
        f"src/index.tsx TalkingVideo out/final.mp4 --props {args.manifest_name} --overwrite"
    )
    print(
        json.dumps(
            {
                "project_dir": str(args.project_dir.resolve()),
                "manifest": str(manifest_path.resolve()),
                "video_public_path": video["path"],
                "render_command": render_command,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
