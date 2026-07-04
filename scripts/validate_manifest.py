#!/usr/bin/env python3
"""Validate a render-talking-video Remotion manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ALLOWED_SEMANTIC_TYPES = {"entity", "number", "benefit", "proof", "risk", "action", "emotion"}
ALLOWED_RENDER_MODES = {"caption", "flower"}
ALLOWED_MOTION_PRESETS = {
    "cardRise",
    "numberBurst",
    "softGlow",
    "stampIn",
    "warningShake",
    "slideSnap",
    "popElastic",
    "underlineSweep",
    "hookSnap",
    "impactZoom",
    "chipSlide",
    "badgeSweep",
    "scanReveal",
    "ribbonSnap",
    "bracketPop",
    "speedCount",
}
ALLOWED_COMPONENTS = {"metric_card", "spec_chip", "benefit_badge", "hook_title", "callout"}
ALLOWED_VARIANTS = {
    "metric_card": {"dashboard_glow", "minimal_clean", "speedometer", "giant_number"},
    "spec_chip": {"white_label", "dark_glass", "neon_pill", "stacked_specs"},
    "benefit_badge": {"scanline_bar", "left_ribbon", "glow_label"},
    "hook_title": {"product_launch", "punch_number", "editorial_clean"},
    "callout": {"arrow_pointer", "bracket_focus", "area_scan"},
}
ALLOWED_LAYOUTS = {
    "upper-right",
    "upper-left",
    "middle-right",
    "middle-left",
    "lower-right",
    "lower-left",
    "center",
    "top-center",
    "lower-third",
}
ALLOWED_PALETTES = {
    "semantic_auto",
    "auto_yellow_black",
    "clean_white_blue",
    "neon_cyan_magenta",
    "warning_red_black",
    "fresh_green_dark",
    "editorial_black_white",
}
ALLOWED_DECORATIONS = {
    "scanline",
    "sweep_light",
    "corner_ticks",
    "progress_bar",
    "bracket_focus",
    "dot_grid",
    "underline",
    "arrow",
}
ALLOWED_SFX_CUES = {"", "entity_ping", "number_pop", "benefit_spark", "proof_chime", "risk_snap", "action_tick", "emotion_boop"}


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_event(event: dict[str, Any], index: int, duration_ms: int, errors: list[str]) -> None:
    start = event.get("start_ms")
    end = event.get("end_ms")
    require(isinstance(start, int), f"event[{index}].start_ms must be int", errors)
    require(isinstance(end, int), f"event[{index}].end_ms must be int", errors)
    if isinstance(start, int) and isinstance(end, int):
        require(0 <= start <= duration_ms, f"event[{index}].start_ms outside duration", errors)
        require(start <= end <= duration_ms, f"event[{index}].end_ms outside duration/order", errors)


def validate_director_fields(item: dict[str, Any], prefix: str, errors: list[str]) -> None:
    component = item.get("component")
    if component is not None and component != "":
        require(component in ALLOWED_COMPONENTS, f"{prefix}.component must be one of {sorted(ALLOWED_COMPONENTS)}", errors)
    variant = item.get("variant")
    if variant is not None and variant != "":
        if isinstance(component, str) and component in ALLOWED_VARIANTS:
            require(variant in ALLOWED_VARIANTS[component], f"{prefix}.variant invalid for {component}", errors)
        else:
            require(False, f"{prefix}.variant requires a valid component", errors)
    layout = item.get("layout")
    if layout is not None and layout != "":
        require(layout in ALLOWED_LAYOUTS, f"{prefix}.layout must be one of {sorted(ALLOWED_LAYOUTS)}", errors)
    palette = item.get("palette")
    if palette is not None and palette != "":
        require(palette in ALLOWED_PALETTES, f"{prefix}.palette must be one of {sorted(ALLOWED_PALETTES)}", errors)
    decorations = item.get("decorations")
    if decorations is not None:
        require(isinstance(decorations, dict), f"{prefix}.decorations must be object", errors)
        if isinstance(decorations, dict):
            for key, value in decorations.items():
                require(key in ALLOWED_DECORATIONS, f"{prefix}.decorations.{key} is not allowed", errors)
                require(isinstance(value, bool), f"{prefix}.decorations.{key} must be bool", errors)
    motion = item.get("motion")
    if motion is not None:
        require(isinstance(motion, dict), f"{prefix}.motion must be object", errors)
        if isinstance(motion, dict):
            preset = motion.get("preset")
            if preset is not None:
                require(preset in ALLOWED_MOTION_PRESETS, f"{prefix}.motion.preset must be one of {sorted(ALLOWED_MOTION_PRESETS)}", errors)
            intensity = motion.get("intensity")
            if intensity is not None:
                require(isinstance(intensity, (int, float)) and 0.2 <= float(intensity) <= 1.4, f"{prefix}.motion.intensity must be 0.2..1.4", errors)
            duration_ms = motion.get("duration_ms")
            if duration_ms is not None:
                require(isinstance(duration_ms, int) and 160 <= duration_ms <= 900, f"{prefix}.motion.duration_ms must be int 160..900", errors)
            sfx = motion.get("sfx")
            if sfx is not None:
                require(sfx in ALLOWED_SFX_CUES, f"{prefix}.motion.sfx must be one of {sorted(ALLOWED_SFX_CUES)}", errors)


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    require(manifest.get("version") == 1, "version must be 1", errors)
    output = manifest.get("output")
    require(isinstance(output, dict), "output must be object", errors)
    duration_ms = 0
    if isinstance(output, dict):
        for field in ["width", "height", "fps", "duration_ms"]:
            require(isinstance(output.get(field), int), f"output.{field} must be int", errors)
        duration_ms = int(output.get("duration_ms") or 0)
        require(duration_ms > 0, "output.duration_ms must be positive", errors)
    video = manifest.get("video")
    require(isinstance(video, dict), "video must be object", errors)
    if isinstance(video, dict):
        path = video.get("path")
        require(isinstance(path, str) and bool(path), "video.path must be string", errors)
    for index, subtitle in enumerate(manifest.get("subtitles", []) or []):
        require(isinstance(subtitle.get("text"), str), f"subtitles[{index}].text must be string", errors)
        validate_event(subtitle, index, duration_ms, errors)
    for index, event in enumerate(manifest.get("visual_events", []) or []):
        require(isinstance(event.get("type"), str), f"visual_events[{index}].type must be string", errors)
        semantic_type = event.get("semantic_type")
        if semantic_type is not None:
            require(
                semantic_type in ALLOWED_SEMANTIC_TYPES,
                f"visual_events[{index}].semantic_type must be one of {sorted(ALLOWED_SEMANTIC_TYPES)}",
                errors,
            )
        render_mode = event.get("render_mode")
        if render_mode is not None:
            require(
                render_mode in ALLOWED_RENDER_MODES,
                f"visual_events[{index}].render_mode must be one of {sorted(ALLOWED_RENDER_MODES)}",
                errors,
            )
        emphasis_level = event.get("emphasis_level")
        if emphasis_level is not None:
            require(
                isinstance(emphasis_level, int) and 1 <= emphasis_level <= 3,
                f"visual_events[{index}].emphasis_level must be int 1..3",
                errors,
            )
        motion_preset = event.get("motion_preset")
        if motion_preset is not None:
            require(
                motion_preset in ALLOWED_MOTION_PRESETS,
                f"visual_events[{index}].motion_preset must be one of {sorted(ALLOWED_MOTION_PRESETS)}",
                errors,
            )
        validate_director_fields(event, f"visual_events[{index}]", errors)
        validate_event(event, index, duration_ms, errors)
    packaging = manifest.get("packaging")
    if packaging is not None:
        require(isinstance(packaging, dict), "packaging must be object", errors)
        if isinstance(packaging, dict):
            hook = packaging.get("hook")
            if hook is not None:
                require(isinstance(hook, dict), "packaging.hook must be object", errors)
                if isinstance(hook, dict) and hook.get("enabled", True):
                    require(isinstance(hook.get("text"), str) and bool(hook.get("text")), "packaging.hook.text must be string", errors)
                    semantic_type = hook.get("semantic_type")
                    if semantic_type is not None:
                        require(
                            semantic_type in ALLOWED_SEMANTIC_TYPES,
                            f"packaging.hook.semantic_type must be one of {sorted(ALLOWED_SEMANTIC_TYPES)}",
                            errors,
                        )
                    motion_preset = hook.get("motion_preset")
                    if motion_preset is not None:
                        require(
                            motion_preset in ALLOWED_MOTION_PRESETS,
                            f"packaging.hook.motion_preset must be one of {sorted(ALLOWED_MOTION_PRESETS)}",
                            errors,
                        )
                    validate_director_fields(hook, "packaging.hook", errors)
                    validate_event(hook, 0, duration_ms, errors)
    audio = manifest.get("audio", {})
    if audio is not None:
        require(isinstance(audio, dict), "audio must be object", errors)
    if isinstance(audio, dict):
        for index, sfx in enumerate(audio.get("sfx", []) or []):
            require(isinstance(sfx.get("path"), str) and bool(sfx.get("path")), f"audio.sfx[{index}].path must be string", errors)
            require(isinstance(sfx.get("start_ms"), int), f"audio.sfx[{index}].start_ms must be int", errors)
            if isinstance(sfx.get("start_ms"), int):
                require(0 <= sfx["start_ms"] <= duration_ms, f"audio.sfx[{index}].start_ms outside duration", errors)
            semantic_type = sfx.get("semantic_type")
            if semantic_type is not None:
                require(
                    semantic_type in ALLOWED_SEMANTIC_TYPES,
                    f"audio.sfx[{index}].semantic_type must be one of {sorted(ALLOWED_SEMANTIC_TYPES)}",
                    errors,
                )
        bgm = audio.get("bgm")
        if bgm is not None:
            require(isinstance(bgm, dict), "audio.bgm must be object", errors)
            if isinstance(bgm, dict):
                require(isinstance(bgm.get("path"), str) and bool(bgm.get("path")), "audio.bgm.path must be string", errors)
                start = bgm.get("start_ms")
                end = bgm.get("end_ms")
                if start is not None:
                    require(isinstance(start, int), "audio.bgm.start_ms must be int", errors)
                if end is not None:
                    require(isinstance(end, int), "audio.bgm.end_ms must be int", errors)
                if isinstance(start, int):
                    require(0 <= start <= duration_ms, "audio.bgm.start_ms outside duration", errors)
                if isinstance(end, int):
                    require(0 <= end <= duration_ms, "audio.bgm.end_ms outside duration", errors)
    attribution = manifest.get("attribution", [])
    require(isinstance(attribution, list), "attribution must be list", errors)
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate render manifest JSON.")
    parser.add_argument("manifest_json", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest_json.read_text(encoding="utf-8"))
    errors = validate_manifest(manifest)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("OK")


if __name__ == "__main__":
    main()
