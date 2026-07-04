#!/usr/bin/env python3
"""Build a Remotion manifest from alignment JSON and a cut plan."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

PUNCTUATION_RE = re.compile(r"[。！？!?，,、：:；;“”\"'（）()《》【】\[\]\s]+")
NUMBER_RE = re.compile(r"(?:全球|全国|全网|行业|平台|TOP)?[0-9一二三四五六七八九十百千万亿]+(?:\.[0-9]+)?(?:星|级|分|%|％|万|亿|千|百|天|小时|分钟|秒|年|个月|台|个|倍|折)")
PRICE_RE = re.compile(r"[0-9一二三四五六七八九十百千万亿]+(?:\.[0-9]+)?(?:万|亿|千|百)?(?:块钱|元|块|人民币)")
STOP_TOKENS = set("，。！？、：；,.!?;")
SUBTITLE_BREAK_RE = re.compile(r"^[。！？!?，,、：:；;]+$")
ENTITY_BOUNDARY_WORDS = [
    "当然了",
    "除了",
    "还有",
    "主打",
    "也能",
    "拿到",
    "就能",
    "可以买",
    "能买",
    "同步",
    "登场",
]
SEMANTIC_STYLES = {
    "entity": "entity_title",
    "number": "number_burst",
    "benefit": "benefit_glow",
    "proof": "proof_underline",
    "risk": "risk_alert",
    "action": "action_arrow",
    "emotion": "emotion_pop",
}
MOTION_PRESETS = {
    "entity": "cardRise",
    "number": "numberBurst",
    "benefit": "softGlow",
    "proof": "stampIn",
    "risk": "warningShake",
    "action": "slideSnap",
    "emotion": "popElastic",
}
ALLOWED_MOTION_PRESETS = set(MOTION_PRESETS.values()) | {
    "underlineSweep",
    "impactZoom",
    "chipSlide",
    "badgeSweep",
    "hookSnap",
    "scanReveal",
    "ribbonSnap",
    "bracketPop",
    "speedCount",
}
DIRECTOR_COMPONENT_ALIASES = {
    "number_impact": "metric_card",
    "metric": "metric_card",
    "metric_card": "metric_card",
    "spec_chip": "spec_chip",
    "chip": "spec_chip",
    "benefit_badge": "benefit_badge",
    "badge": "benefit_badge",
    "hook_title": "hook_title",
    "title": "hook_title",
    "callout": "callout",
}
COMPONENT_DEFAULT_BY_SEMANTIC = {
    "entity": "spec_chip",
    "number": "metric_card",
    "benefit": "benefit_badge",
    "proof": "benefit_badge",
    "risk": "callout",
    "action": "callout",
    "emotion": "benefit_badge",
}
COMPONENT_VARIANTS = {
    "metric_card": {"dashboard_glow", "minimal_clean", "speedometer", "giant_number"},
    "spec_chip": {"white_label", "dark_glass", "neon_pill", "stacked_specs"},
    "benefit_badge": {"scanline_bar", "left_ribbon", "glow_label"},
    "hook_title": {"product_launch", "punch_number", "editorial_clean"},
    "callout": {"arrow_pointer", "bracket_focus", "area_scan"},
}
DEFAULT_VARIANT_BY_COMPONENT = {
    "metric_card": "dashboard_glow",
    "spec_chip": "dark_glass",
    "benefit_badge": "scanline_bar",
    "hook_title": "product_launch",
    "callout": "bracket_focus",
}
LAYOUT_ALIASES = {
    "upper-right": "upper-right",
    "upper_right": "upper-right",
    "upper-left": "upper-left",
    "upper_left": "upper-left",
    "middle_right": "middle-right",
    "middle-left": "middle-left",
    "middle_left": "middle-left",
    "middle-right": "middle-right",
    "lower_right": "lower-right",
    "lower-right": "lower-right",
    "lower_left": "lower-left",
    "lower-left": "lower-left",
    "center": "center",
    "top_center": "top-center",
    "top-center": "top-center",
    "lower_third": "lower-third",
    "lower-third": "lower-third",
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
RENDER_MODE_BY_LEVEL = {
    1: "caption",
    2: "caption",
    3: "flower",
}
DEFAULT_ASSET_INDEX = Path(__file__).resolve().parents[1] / "assets" / "audio" / "pixabay" / "index.json"
ALLOWED_SEMANTIC_TYPES = set(SEMANTIC_STYLES)
SFX_BY_SEMANTIC = {
    "entity": {"path": "entity_ping.wav", "volume": 0.36, "offset_ms": 0},
    "number": {"path": "number_pop.wav", "volume": 0.44, "offset_ms": 0},
    "benefit": {"path": "benefit_spark.wav", "volume": 0.34, "offset_ms": 0},
    "proof": {"path": "proof_chime.wav", "volume": 0.34, "offset_ms": 0},
    "risk": {"path": "risk_snap.wav", "volume": 0.42, "offset_ms": 0},
    "action": {"path": "action_tick.wav", "volume": 0.36, "offset_ms": 0},
    "emotion": {"path": "emotion_boop.wav", "volume": 0.38, "offset_ms": 0},
}
LANES = ["upper-right", "upper-left", "middle-right", "middle-left"]


def run_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def probe_video(path: Path) -> dict[str, Any]:
    payload = run_json(
        [
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
    )
    stream = (payload.get("streams") or [{}])[0]
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    duration = float(stream.get("duration") or 0)
    rate = stream.get("r_frame_rate") or "30/1"
    fps = parse_fps(rate)
    return {"width": width, "height": height, "duration_ms": round(duration * 1000), "fps": fps}


def parse_fps(rate: str) -> int:
    if "/" in rate:
        left, right = rate.split("/", 1)
        denom = float(right or 1)
        value = float(left or 30) / denom if denom else 30
    else:
        value = float(rate or 30)
    return max(1, round(value))


def load_words(alignment: dict[str, Any]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for utterance in alignment.get("utterances", []) or []:
        for raw in utterance.get("words", []) or []:
            text = str(raw.get("text") or "").strip()
            if not text:
                continue
            start = int(round(float(raw.get("start_time", 0))))
            end = int(round(float(raw.get("end_time", 0))))
            if end < start:
                continue
            if end == start and re.match(r"^[。！？!?，,、：:]$", text):
                continue
            words.append({"text": text, "start_ms": start, "end_ms": end})
    words.sort(key=lambda item: (item["start_ms"], item["end_ms"]))
    return words


def map_time(original_ms: int, keep_segments: list[dict[str, int]]) -> int | None:
    new_cursor = 0
    for segment in keep_segments:
        start = segment["start_ms"]
        end = segment["end_ms"]
        if start <= original_ms <= end:
            return new_cursor + (original_ms - start)
        new_cursor += end - start
    return None


def annotate_subtitle_breaks_from_script(words: list[dict[str, Any]], script_text: str) -> list[dict[str, Any]]:
    break_positions: set[int] = set()
    clean_count = 0
    for char in script_text:
        if SUBTITLE_BREAK_RE.match(char):
            if clean_count:
                break_positions.add(clean_count)
            continue
        cleaned = PUNCTUATION_RE.sub("", char)
        if cleaned:
            clean_count += len(cleaned)

    annotated: list[dict[str, Any]] = []
    cursor = 0
    for word in words:
        updated = dict(word)
        cleaned = PUNCTUATION_RE.sub("", str(word["text"]))
        if cleaned:
            cursor += len(cleaned)
            if cursor in break_positions:
                updated["break_after"] = True
        annotated.append(updated)
    return annotated


def remap_words(words: list[dict[str, Any]], keep_segments: list[dict[str, int]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for word in words:
        start = map_time(word["start_ms"], keep_segments)
        end = map_time(word["end_ms"], keep_segments)
        if start is None or end is None or end < start:
            continue
        mapped_word = {"text": word["text"], "start_ms": start, "end_ms": max(end, start + 60)}
        if word.get("break_after"):
            mapped_word["break_after"] = True
        mapped.append(mapped_word)
    return mapped


def group_subtitles(
    words: list[dict[str, Any]],
    max_line_chars: int = 15,
    max_lines: int = 2,
    max_gap_ms: int = 420,
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    max_chars = max_line_chars * max_lines
    for word in words:
        if not current:
            current = [word]
            continue
        text = PUNCTUATION_RE.sub("", "".join(item["text"] for item in current))
        next_text = PUNCTUATION_RE.sub("", str(word["text"]))
        gap = word["start_ms"] - current[-1]["end_ms"]
        ended_by_punctuation = bool(current[-1].get("break_after")) or bool(SUBTITLE_BREAK_RE.match(str(current[-1]["text"])))
        too_long = len(text + next_text) > max_chars
        if too_long or gap > max_gap_ms or ended_by_punctuation:
            subtitle = to_subtitle(current, max_line_chars=max_line_chars, max_lines=max_lines)
            if subtitle["text"]:
                groups.append(subtitle)
            current = [word]
        else:
            current.append(word)
    if current:
        subtitle = to_subtitle(current, max_line_chars=max_line_chars, max_lines=max_lines)
        if subtitle["text"]:
            groups.append(subtitle)
    return groups


def to_subtitle(words: list[dict[str, Any]], max_line_chars: int = 15, max_lines: int = 2) -> dict[str, Any]:
    text = PUNCTUATION_RE.sub("", "".join(item["text"] for item in words))
    text = wrap_subtitle_text(text, max_line_chars=max_line_chars, max_lines=max_lines)
    return {
        "text": text,
        "start_ms": words[0]["start_ms"],
        "end_ms": words[-1]["end_ms"],
    }


def wrap_subtitle_text(text: str, max_line_chars: int = 15, max_lines: int = 2) -> str:
    if max_line_chars <= 0 or max_lines <= 1 or len(text) <= max_line_chars:
        return text
    lines = [text[index : index + max_line_chars] for index in range(0, len(text), max_line_chars)]
    return "\n".join(lines[:max_lines])


def visual_events(
    words: list[dict[str, Any]],
    highlight_plan: list[dict[str, Any]] | None = None,
    max_events: int = 5,
) -> list[dict[str, Any]]:
    candidates = planned_key_phrase_candidates(words, highlight_plan or [])
    candidates.extend(collect_key_phrase_candidates(words))
    selected: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []
    seen: set[str] = set()
    for candidate in sorted(candidates, key=lambda item: (-item["priority"], item["start_ms"], -len(item["text"]))):
        text = candidate["text"]
        if text in seen or len(text) < 2:
            continue
        span = (candidate["start_ms"], candidate["end_ms"])
        if any(overlap_ratio(span, used) > 0.62 for used in occupied):
            continue
        seen.add(text)
        occupied.append(span)
        candidate["lane"] = LANES[len(selected) % len(LANES)]
        selected.append(candidate)
        if len(selected) >= max_events:
            break
    selected.sort(key=lambda item: item["start_ms"])
    for item in selected:
        if not item.get("layout"):
            item["layout"] = item.get("lane", "")
        item.pop("priority", None)
    return enrich_emphasis_events(selected)


def enrich_emphasis_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for event in events:
        semantic_type = normalize_semantic_type(str(event.get("semantic_type") or ""), str(event.get("text") or ""))
        event = dict(event)
        event["semantic_type"] = semantic_type
        event["visual_style"] = str(event.get("visual_style") or "") or SEMANTIC_STYLES[semantic_type]
        event["style"] = str(event.get("style") or "") or event["visual_style"]
        event["emphasis_level"] = clamp_int(event.get("emphasis_level"), default_emphasis_level(event), 1, 3)
        event["render_mode"] = normalize_render_mode(str(event.get("render_mode") or ""), event["emphasis_level"])
        event["motion_preset"] = normalize_motion_preset(str(event.get("motion_preset") or ""), semantic_type)
        event.update(normalize_director_params(event, semantic_type, str(event.get("component") or ""), str(event.get("layout") or event.get("lane") or "")))
        enriched.append(event)
    return enriched


def clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def default_emphasis_level(event: dict[str, Any]) -> int:
    semantic_type = str(event.get("semantic_type") or "")
    source = str(event.get("source") or "")
    text = str(event.get("text") or "")
    if source == "llm" or semantic_type in {"number", "risk", "proof"}:
        return 3
    if semantic_type in {"benefit", "action", "emotion"} or len(text) >= 5:
        return 2
    return 1


def normalize_render_mode(value: str, emphasis_level: int) -> str:
    value = value.strip().lower()
    if value in {"caption", "flower"}:
        return value
    return RENDER_MODE_BY_LEVEL.get(emphasis_level, "flower")


def normalize_motion_preset(value: str, semantic_type: str) -> str:
    value = value.strip()
    if value in ALLOWED_MOTION_PRESETS:
        return value
    return MOTION_PRESETS.get(semantic_type, "popElastic")


def planned_key_phrase_candidates(words: list[dict[str, Any]], plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(plan):
        phrase = clean_text(str(item.get("text") or ""))
        if not phrase:
            continue
        semantic_type = normalize_semantic_type(str(item.get("semantic_type") or ""), phrase)
        visual_style = str(item.get("visual_style") or "") or SEMANTIC_STYLES[semantic_type]
        span = planned_span(words, phrase, item)
        if not span:
            continue
        start, end = span
        event = {
            "type": "key_phrase",
            "text": phrase,
            "start_ms": start,
            "end_ms": min(end + 1200, start + 2400),
            "semantic_type": semantic_type,
            "visual_style": visual_style,
            "style": visual_style,
            "render_mode": str(item.get("render_mode") or ""),
            "emphasis_level": item.get("emphasis_level"),
            "motion_preset": str(item.get("motion_preset") or ""),
            "component": normalize_director_component(str(item.get("component") or item.get("treatment") or "")),
            "treatment": str(item.get("treatment") or ""),
            "label": str(item.get("label") or item.get("intent") or ""),
            "supporting_text": str(item.get("supporting_text") or item.get("intent") or item.get("reason") or ""),
            "priority": 240 - index,
            "source": "llm",
        }
        event.update(normalize_director_params(item, semantic_type, event["component"], event["lane"] if "lane" in event else ""))
        candidates.append(event)
    return candidates


def normalize_director_component(value: str) -> str:
    value = clean_text(value.strip().lower().replace("-", "_").replace(" ", "_"))
    return DIRECTOR_COMPONENT_ALIASES.get(value, value if value in set(DIRECTOR_COMPONENT_ALIASES.values()) else "")


def normalize_director_params(
    item: dict[str, Any],
    semantic_type: str,
    component: str = "",
    assigned_lane: str = "",
) -> dict[str, Any]:
    component = component or default_component(semantic_type, item)
    params: dict[str, Any] = {"component": component}
    params["variant"] = normalize_variant(component, str(item.get("variant") or item.get("visual_variant") or ""))
    params["layout"] = normalize_layout(str(item.get("layout") or item.get("position") or assigned_lane or ""))
    params["palette"] = normalize_palette(str(item.get("palette") or item.get("color_palette") or ""))
    params["decorations"] = normalize_decorations(item.get("decorations"))
    motion = normalize_motion(item.get("motion"), str(item.get("motion_preset") or ""), semantic_type)
    params["motion"] = motion
    params["motion_preset"] = motion["preset"]
    return params


def default_component(semantic_type: str, item: dict[str, Any]) -> str:
    render_mode = str(item.get("render_mode") or "")
    emphasis = item.get("emphasis_level")
    if render_mode == "caption" or emphasis in {1, 2}:
        return ""
    return COMPONENT_DEFAULT_BY_SEMANTIC.get(semantic_type, "")


def normalize_variant(component: str, value: str) -> str:
    allowed = COMPONENT_VARIANTS.get(component, set())
    value = value.strip().lower().replace("-", "_").replace(" ", "_")
    if value in allowed:
        return value
    return DEFAULT_VARIANT_BY_COMPONENT.get(component, "")


def normalize_layout(value: str) -> str:
    value = value.strip().lower().replace(" ", "_")
    return LAYOUT_ALIASES.get(value, "")


def normalize_palette(value: str) -> str:
    value = value.strip().lower().replace("-", "_").replace(" ", "_")
    return value if value in ALLOWED_PALETTES else "semantic_auto"


def normalize_decorations(value: Any) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, bool] = {}
    for key, enabled in value.items():
        name = str(key).strip().lower().replace("-", "_").replace(" ", "_")
        if name in ALLOWED_DECORATIONS:
            normalized[name] = bool(enabled)
    return normalized


def normalize_motion(value: Any, preset: str, semantic_type: str) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    return {
        "preset": normalize_motion_preset(str(raw.get("preset") or preset), semantic_type),
        "intensity": clamp_float(raw.get("intensity"), 0.75, 0.2, 1.4),
        "duration_ms": clamp_int(raw.get("duration_ms"), 420, 160, 900),
        "sfx": normalize_sfx_cue(str(raw.get("sfx") or "")),
    }


def clamp_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def normalize_sfx_cue(value: str) -> str:
    value = value.strip().lower().replace("-", "_").replace(" ", "_")
    allowed = {"", "entity_ping", "number_pop", "benefit_spark", "proof_chime", "risk_snap", "action_tick", "emotion_boop"}
    return value if value in allowed else ""


def planned_span(words: list[dict[str, Any]], phrase: str, item: dict[str, Any]) -> tuple[int, int] | None:
    span = find_phrase_span(words, phrase)
    if span:
        return span
    start = item.get("start_ms")
    end = item.get("end_ms")
    if isinstance(start, int) and isinstance(end, int) and end >= start:
        return start, end
    return None


def collect_key_phrase_candidates(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for segment in split_phrase_segments(words):
        text = clean_text("".join(item["text"] for item in segment))
        if not text:
            continue
        add_number_candidates(candidates, segment, text)
        add_entity_candidates(candidates, segment)
        add_cue_phrase_candidates(candidates, segment, text)
    return candidates


def split_phrase_segments(words: list[dict[str, Any]], max_gap_ms: int = 620) -> list[list[dict[str, Any]]]:
    segments: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for word in words:
        token = str(word["text"])
        gap = word["start_ms"] - current[-1]["end_ms"] if current else 0
        if current and (gap > max_gap_ms or token in STOP_TOKENS):
            segments.append(current)
            current = []
        if token not in STOP_TOKENS:
            current.append(word)
    if current:
        segments.append(current)
    return segments


def add_number_candidates(candidates: list[dict[str, Any]], segment: list[dict[str, Any]], text: str) -> None:
    for regex, semantic_type, base_priority in [(PRICE_RE, "number", 95), (NUMBER_RE, "number", 88)]:
        for match in regex.finditer(text):
            phrase = expand_numeric_phrase(text, match.group(0), match.end())
            semantic = classify_phrase(phrase, fallback=semantic_type)
            priority = base_priority + semantic_bonus(semantic)
            add_candidate(candidates, segment, phrase, semantic, priority)


def add_entity_candidates(candidates: list[dict[str, Any]], segment: list[dict[str, Any]]) -> None:
    clean_tokens = [clean_text(str(item["text"])) for item in segment]
    for index, token in enumerate(clean_tokens):
        if not re.search(r"[A-Za-z0-9]", token):
            continue
        start = max(0, index - 4)
        end = min(len(clean_tokens), index + 5)
        phrase = trim_entity_phrase("".join(clean_tokens[start:end]))
        if 2 <= len(phrase) <= 10:
            semantic = classify_phrase(phrase, fallback="entity")
            mixed_code_bonus = 10 if re.search(r"[A-Za-z]", phrase) and re.search(r"[0-9]", phrase) else 0
            add_candidate(candidates, segment, phrase, semantic, 72 + min(len(phrase), 6) + mixed_code_bonus)


def add_cue_phrase_candidates(candidates: list[dict[str, Any]], segment: list[dict[str, Any]], text: str) -> None:
    cue_specs = [
        ("主打", "benefit", 68, 12),
        ("可以", "benefit", 58, 10),
        ("能", "benefit", 54, 10),
        ("不要", "risk", 75, 10),
        ("千万", "risk", 76, 10),
        ("注意", "risk", 72, 10),
        ("点击", "action", 72, 8),
        ("打开", "action", 70, 8),
        ("选择", "action", 70, 8),
        ("关注", "action", 72, 8),
        ("收藏", "action", 72, 8),
    ]
    for cue, semantic, priority, length in cue_specs:
        index = text.find(cue)
        if index < 0:
            continue
        phrase = text[index : index + length]
        phrase = trim_entity_phrase(phrase)
        if len(phrase) >= 4:
            add_candidate(candidates, segment, phrase, semantic, priority)


def add_candidate(
    candidates: list[dict[str, Any]],
    segment: list[dict[str, Any]],
    phrase: str,
    semantic_type: str,
    priority: int,
) -> None:
    phrase = clean_text(phrase)
    if not phrase or is_weak_number_phrase(phrase, semantic_type):
        return
    span = find_phrase_span(segment, phrase)
    if not span:
        return
    start, end = span
    visual_style = SEMANTIC_STYLES.get(semantic_type, "emphasis_pop")
    candidates.append(
        {
            "type": "key_phrase",
            "text": phrase,
            "start_ms": start,
            "end_ms": min(end + 1200, start + 2400),
            "semantic_type": semantic_type,
            "visual_style": visual_style,
            "style": visual_style,
            "priority": priority,
        }
    )


def packaging_hook(
    words: list[dict[str, Any]],
    subtitles: list[dict[str, Any]],
    highlights: list[dict[str, Any]],
    plan_payload: Any,
    duration_ms: int,
) -> dict[str, Any]:
    planned = plan_hook(plan_payload)
    if planned:
        text = planned
    elif highlights:
        text = str(highlights[0].get("text") or "")
    elif subtitles:
        text = str(subtitles[0].get("text") or "")
    else:
        text = clean_text("".join(str(word["text"]) for word in words[:8]))
    text = trim_hook_text(text)
    if not text or duration_ms < 900:
        return {"enabled": False}
    planned_config = plan_hook_config(plan_payload)
    semantic_type = normalize_semantic_type(str(planned_config.get("semantic_type") or ""), text)
    hook = {
        "enabled": True,
        "text": text,
        "start_ms": 0,
        "end_ms": min(duration_ms, 1350),
        "semantic_type": semantic_type,
        "visual_style": SEMANTIC_STYLES[semantic_type],
        "emphasis_level": 3,
        "motion_preset": "hookSnap",
    }
    for field in ["label", "supporting_text"]:
        if isinstance(planned_config.get(field), str) and planned_config[field].strip():
            hook[field] = planned_config[field].strip()
    hook.update(
        normalize_director_params(
            {**planned_config, "component": planned_config.get("component") or "hook_title", "motion_preset": planned_config.get("motion_preset") or "hookSnap"},
            semantic_type,
            "hook_title",
            "top-center",
        )
    )
    return hook


def plan_hook_config(plan_payload: Any) -> dict[str, Any]:
    if not isinstance(plan_payload, dict):
        return {}
    candidates = [
        plan_payload.get("hook"),
        plan_payload.get("opening_hook"),
        (plan_payload.get("packaging") or {}).get("hook") if isinstance(plan_payload.get("packaging"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    return {}


def plan_hook(plan_payload: Any) -> str:
    if not isinstance(plan_payload, dict):
        return ""
    candidates = [
        plan_payload.get("hook"),
        plan_payload.get("title"),
        plan_payload.get("opening_hook"),
        (plan_payload.get("packaging") or {}).get("hook") if isinstance(plan_payload.get("packaging"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        if isinstance(candidate, dict):
            text = candidate.get("text") or candidate.get("title")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return ""


def trim_hook_text(text: str, max_chars: int = 16) -> str:
    text = clean_text(text)
    return text[:max_chars]


def normalize_semantic_type(value: str, phrase: str) -> str:
    value = value.strip().lower()
    if value in ALLOWED_SEMANTIC_TYPES:
        return value
    return classify_phrase(phrase, fallback="entity")


def expand_numeric_phrase(text: str, phrase: str, end_index: int) -> str:
    tail = text[end_index : end_index + 4]
    for keyword in ["安全", "认证", "排名", "好评", "销量", "背书", "保障"]:
        keyword_index = tail.find(keyword)
        if keyword_index >= 0:
            return phrase + tail[: keyword_index + len(keyword)]
    return phrase


def classify_phrase(phrase: str, fallback: str = "entity") -> str:
    if re.search(r"块钱|元|人民币|折|%|％|万|亿|千|百", phrase):
        return "number"
    if re.search(r"认证|排名|第一|TOP|五星|5星|奖|官方|背书|全球|全国|安全|保障", phrase, re.I):
        return "proof"
    if re.search(r"避坑|不要|千万|注意|风险|问题|失败|亏|坑|雷", phrase):
        return "risk"
    if re.search(r"点击|打开|选择|输入|保存|下载|购买|预约|关注|收藏|评论|报名|领取|加入", phrase):
        return "action"
    if re.search(r"提升|省|更快|好用|颜值|精品|优势|效果|解决|适合|主打|可以|能", phrase):
        return "benefit"
    if re.search(r"震惊|离谱|太|真的|竟然|没想到|绝了", phrase):
        return "emotion"
    return fallback


def load_highlight_plan(path: Path | None) -> list[dict[str, Any]]:
    payload = load_plan_payload(path)
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = (
            payload.get("key_phrases")
            or payload.get("timeline")
            or payload.get("packaging_timeline")
            or payload.get("highlights")
            or payload.get("visual_events")
            or []
        )
    else:
        items = []
    return [item for item in items if isinstance(item, dict)]


def load_plan_payload(path: Path | None) -> Any:
    if not path:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_asset_index(path: Path | None, disabled: bool = False) -> dict[str, Any]:
    if disabled or not path or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def asset_license(asset_index: dict[str, Any]) -> dict[str, Any]:
    license_info = asset_index.get("license")
    return license_info if isinstance(license_info, dict) else {}


def sfx_asset_by_semantic(asset_index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    assets: dict[str, dict[str, Any]] = {}
    for asset in asset_index.get("sfx", []) or []:
        if not isinstance(asset, dict):
            continue
        semantic_type = str(asset.get("semantic_type") or "")
        path = str(asset.get("path") or "")
        if semantic_type in ALLOWED_SEMANTIC_TYPES and path:
            assets[semantic_type] = asset
    return assets


def keyword_sfx(
    events: list[dict[str, Any]],
    sfx_prefix: str,
    duration_ms: int,
    asset_index: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    indexed_assets = sfx_asset_by_semantic(asset_index or {})
    sfx: list[dict[str, Any]] = []
    for event in events:
        semantic_type = normalize_semantic_type(str(event.get("semantic_type") or ""), str(event.get("text") or ""))
        asset = indexed_assets.get(semantic_type)
        config = asset if asset else SFX_BY_SEMANTIC[semantic_type]
        start_ms = max(0, min(int(event["start_ms"]) + int(config["offset_ms"]), duration_ms))
        path = str(config["path"])
        item = {
            "path": path if asset else str(Path(sfx_prefix) / path),
            "start_ms": start_ms,
            "volume": float(config["volume"]),
            "semantic_type": semantic_type,
            "for_text": event.get("text", ""),
        }
        if asset:
            item.update(
                {
                    "source": asset.get("source", "pixabay"),
                    "title": asset.get("title", ""),
                    "creator": asset.get("creator", ""),
                    "source_url": asset.get("source_url", ""),
                    "attribution_text": asset.get("attribution_text", ""),
                }
            )
        sfx.append(item)
    return sfx


def local_sfx_attribution(sfx: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not sfx:
        return []
    local_items = [item for item in sfx if item.get("source") != "pixabay"]
    if not local_items:
        return []
    return [
        {
            "kind": "sfx",
            "source": "local-generated",
            "creator": "render-talking-video skill",
            "license": "Generated locally; no external asset license",
            "requires_attribution": False,
            "attribution_text": "",
            "items": sorted({item["path"] for item in local_items}),
        }
    ]


def pixabay_attribution(media_items: list[dict[str, Any]], asset_index: dict[str, Any]) -> list[dict[str, Any]]:
    if not media_items:
        return []
    license_info = asset_license(asset_index)
    seen: set[str] = set()
    entries: list[dict[str, Any]] = []
    for item in media_items:
        if item.get("source") != "pixabay":
            continue
        key = str(item.get("source_url") or item.get("path") or item.get("title"))
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "kind": item.get("kind", "audio"),
                "source": "pixabay",
                "title": item.get("title", ""),
                "creator": item.get("creator", ""),
                "license": license_info.get("name", "Pixabay Content License"),
                "license_url": license_info.get("url", "https://pixabay.com/service/license-summary/"),
                "requires_attribution": bool(license_info.get("requires_attribution", False)),
                "source_url": item.get("source_url", ""),
                "attribution_text": item.get("attribution_text", ""),
            }
        )
    return entries


def infer_bgm_style(words: list[dict[str, Any]], plan_payload: Any, explicit_style: str | None = None) -> str:
    if explicit_style:
        return explicit_style
    planned = plan_bgm_style(plan_payload)
    if planned:
        return planned
    text = clean_text("".join(str(word["text"]) for word in words))
    scores = {
        "tech_product": phrase_score(text, ["产品", "品牌", "车型", "汽车", "SUV", "发布", "上市", "登场", "安全", "价格", "性能"]),
        "lifestyle_light": phrase_score(text, ["生活", "好物", "旅行", "美食", "年轻", "颜值", "轻松", "日常", "适合"]),
        "knowledge_calm": phrase_score(text, ["教程", "知识", "方法", "步骤", "分析", "为什么", "如何", "原因", "原理"]),
        "risk_tension": phrase_score(text, ["风险", "问题", "避坑", "不要", "千万", "注意", "失败", "亏", "警惕"]),
        "emotional_inspiring": phrase_score(text, ["梦想", "成长", "坚持", "改变", "故事", "感动", "热爱", "未来"]),
    }
    return max(scores.items(), key=lambda item: item[1])[0] if max(scores.values()) > 0 else "tech_product"


def plan_bgm_style(plan_payload: Any) -> str | None:
    if not isinstance(plan_payload, dict):
        return None
    candidates = [
        plan_payload.get("bgm_style"),
        plan_payload.get("music_style"),
        (plan_payload.get("audio") or {}).get("bgm_style") if isinstance(plan_payload.get("audio"), dict) else None,
        (plan_payload.get("audio") or {}).get("style") if isinstance(plan_payload.get("audio"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def phrase_score(text: str, phrases: list[str]) -> int:
    return sum(1 for phrase in phrases if phrase in text)


def select_bgm(asset_index: dict[str, Any], style: str, duration_ms: int) -> dict[str, Any] | None:
    bgm_assets = [item for item in asset_index.get("bgm", []) or [] if isinstance(item, dict)]
    if not bgm_assets:
        return None
    asset = next((item for item in bgm_assets if item.get("style") == style), None)
    if asset is None:
        asset = next((item for item in bgm_assets if item.get("style") == "tech_product"), bgm_assets[0])
    return {
        "kind": "bgm",
        "path": asset["path"],
        "volume": float(asset.get("volume", 0.12)),
        "start_ms": 0,
        "end_ms": duration_ms,
        "style": asset.get("style", style),
        "source": asset.get("source", "pixabay"),
        "title": asset.get("title", ""),
        "creator": asset.get("creator", ""),
        "source_url": asset.get("source_url", ""),
        "attribution_text": asset.get("attribution_text", ""),
    }


def semantic_bonus(semantic_type: str) -> int:
    return {"number": 6, "proof": 8, "risk": 10, "action": 5, "benefit": 4, "emotion": 4, "entity": 0}.get(
        semantic_type, 0
    )


def clean_text(text: str) -> str:
    return PUNCTUATION_RE.sub("", text)


def trim_entity_phrase(phrase: str) -> str:
    phrase = clean_text(phrase)
    changed = True
    while changed:
        changed = False
        for boundary in ENTITY_BOUNDARY_WORDS:
            if boundary in phrase and not phrase.startswith(boundary) and not phrase.endswith(boundary):
                left, right = phrase.split(boundary, 1)
                phrase = left if re.search(r"[A-Za-z0-9]", left) else right
                changed = True
            if phrase.startswith(boundary):
                phrase = phrase[len(boundary) :]
                changed = True
            if phrase.endswith(boundary):
                phrase = phrase[: -len(boundary)]
                changed = True
    return phrase


def is_weak_number_phrase(phrase: str, semantic_type: str) -> bool:
    if semantic_type != "number":
        return False
    return bool(re.fullmatch(r"[一二三四五六七八九十两0-9]+(?:个|台|辆|只|位|条|款|件)", phrase))


def overlap_ratio(left: tuple[int, int], right: tuple[int, int]) -> float:
    start = max(left[0], right[0])
    end = min(left[1], right[1])
    overlap = max(0, end - start)
    shorter = max(1, min(left[1] - left[0], right[1] - right[0]))
    return overlap / shorter


def clamp_events(events: list[dict[str, Any]], duration_ms: int) -> list[dict[str, Any]]:
    clamped: list[dict[str, Any]] = []
    for event in events:
        start = max(0, min(int(event["start_ms"]), duration_ms))
        end = max(start + 1, min(int(event["end_ms"]), duration_ms))
        if start >= duration_ms:
            continue
        updated = dict(event)
        updated["start_ms"] = start
        updated["end_ms"] = end
        clamped.append(updated)
    return clamped


def find_phrase_span(words: list[dict[str, Any]], phrase: str) -> tuple[int, int] | None:
    for index in range(len(words)):
        text = ""
        for end_index in range(index, len(words)):
            text += clean_text(words[end_index]["text"])
            if text == phrase:
                return words[index]["start_ms"], words[end_index]["end_ms"]
            if not phrase.startswith(text):
                break
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Remotion manifest from alignment and cut-plan JSON.")
    parser.add_argument("--clean-video", type=Path, required=True)
    parser.add_argument("--video-public-path")
    parser.add_argument("--alignment", type=Path, required=True)
    parser.add_argument("--cut-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--script-file", type=Path)
    parser.add_argument("--highlight-plan", type=Path)
    parser.add_argument("--max-highlights", type=int, default=5)
    parser.add_argument("--sfx-prefix", default="sfx")
    parser.add_argument("--asset-index", type=Path, default=DEFAULT_ASSET_INDEX)
    parser.add_argument("--no-pixabay-assets", action="store_true")
    parser.add_argument("--no-keyword-sfx", action="store_true")
    parser.add_argument("--bgm-style")
    parser.add_argument("--no-bgm", action="store_true")
    parser.add_argument("--theme", default="notion")
    args = parser.parse_args()

    alignment = json.loads(args.alignment.read_text(encoding="utf-8"))
    cut_plan = json.loads(args.cut_plan.read_text(encoding="utf-8"))
    plan_payload = load_plan_payload(args.highlight_plan)
    asset_index = load_asset_index(args.asset_index, disabled=args.no_pixabay_assets)
    media = probe_video(args.clean_video)
    source_words = load_words(alignment)
    if args.script_file:
        source_words = annotate_subtitle_breaks_from_script(
            source_words,
            args.script_file.read_text(encoding="utf-8"),
        )
    words = remap_words(source_words, cut_plan["keep_segments"])
    subtitles = clamp_events(group_subtitles(words), media["duration_ms"])
    highlights = clamp_events(
        visual_events(words, load_highlight_plan(args.highlight_plan), args.max_highlights),
        media["duration_ms"],
    )
    packaging = {"hook": packaging_hook(words, subtitles, highlights, plan_payload, media["duration_ms"])}
    sfx = [] if args.no_keyword_sfx else keyword_sfx(highlights, args.sfx_prefix, media["duration_ms"], asset_index)
    bgm_style = infer_bgm_style(words, plan_payload, args.bgm_style)
    bgm = None if args.no_bgm else select_bgm(asset_index, bgm_style, media["duration_ms"])
    audio: dict[str, Any] = {"sfx": sfx}
    if bgm:
        audio["bgm"] = bgm
    attribution_media = [dict(item, kind="sfx") for item in sfx]
    if bgm:
        attribution_media.append(bgm)
    manifest = {
        "version": 1,
        "output": {
            "width": media["width"],
            "height": media["height"],
            "fps": media["fps"],
            "duration_ms": media["duration_ms"],
        },
        "video": {"path": args.video_public_path or str(args.clean_video.resolve()), "start_ms": 0},
        "subtitles": subtitles,
        "visual_events": highlights,
        "packaging": packaging,
        "audio": audio,
        "theme": args.theme,
        "attribution": pixabay_attribution(attribution_media, asset_index) + local_sfx_attribution(sfx),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
