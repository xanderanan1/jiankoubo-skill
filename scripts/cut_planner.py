#!/usr/bin/env python3
"""Plan pause and stutter cuts from Volcengine-like word timings."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable


FILLERS = {"嗯", "呃", "啊", "额", "那个", "这个", "就是", "然后"}


@dataclass
class Word:
    text: str
    start_ms: int
    end_ms: int


@dataclass
class Cut:
    start_ms: int
    end_ms: int
    reason: str
    confidence: str
    detail: str


def _to_ms(value: Any) -> int:
    if value is None:
        return 0
    number = float(value)
    return int(round(number))


def normalize_token(text: str) -> str:
    return re.sub(r"[\s，。！？,.!?、；;：:]+", "", text or "")


def flatten_words(payload: dict[str, Any]) -> list[Word]:
    words: list[Word] = []
    for utt in payload.get("utterances", []) or []:
        for raw in utt.get("words", []) or []:
            text = str(raw.get("text") or raw.get("word") or "").strip()
            start = raw.get("start_time", raw.get("start_ms", raw.get("start")))
            end = raw.get("end_time", raw.get("end_ms", raw.get("end")))
            if text and start is not None and end is not None:
                start_ms = _to_ms(start)
                end_ms = _to_ms(end)
                if end_ms >= start_ms:
                    words.append(Word(text=text, start_ms=start_ms, end_ms=end_ms))
    words.sort(key=lambda item: (item.start_ms, item.end_ms))
    return words


def is_repeat_or_stutter(left: str, right: str) -> bool:
    a = normalize_token(left)
    b = normalize_token(right)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) == 1 and b.startswith(a):
        return True
    if a in FILLERS and b in FILLERS:
        return True
    return False


def plan_cuts(
    words: list[Word],
    duration_ms: int = 0,
    min_pause_ms: int = 350,
    hard_pause_ms: int = 700,
    pre_roll_ms: int = 80,
    post_roll_ms: int = 120,
    min_cut_ms: int = 180,
    stutter_max_ms: int = 550,
) -> list[Cut]:
    cuts: list[Cut] = []
    if words:
        leading_end = words[0].start_ms - post_roll_ms
        if leading_end >= min_cut_ms:
            cuts.append(
                Cut(
                    start_ms=0,
                    end_ms=leading_end,
                    reason="leading_silence",
                    confidence="high",
                    detail=f"first_word={words[0].text}",
                )
            )
        if duration_ms:
            trailing_start = words[-1].end_ms + pre_roll_ms
            if duration_ms - trailing_start >= min_cut_ms:
                cuts.append(
                    Cut(
                        start_ms=trailing_start,
                        end_ms=duration_ms,
                        reason="trailing_silence",
                        confidence="high",
                        detail=f"last_word={words[-1].text}",
                    )
                )
    for current, nxt in zip(words, words[1:]):
        gap = nxt.start_ms - current.end_ms
        if gap >= min_pause_ms:
            start = current.end_ms + pre_roll_ms
            end = nxt.start_ms - post_roll_ms
            if end - start >= min_cut_ms:
                cuts.append(
                    Cut(
                        start_ms=start,
                        end_ms=end,
                        reason="pause",
                        confidence="high" if gap >= hard_pause_ms else "medium",
                        detail=f"gap_ms={gap} after={current.text} before={nxt.text}",
                    )
                )
        if is_repeat_or_stutter(current.text, nxt.text):
            duration = current.end_ms - current.start_ms
            if 0 < duration <= stutter_max_ms:
                start = current.start_ms
                end = min(current.end_ms, nxt.start_ms)
                if end - start >= min_cut_ms:
                    cuts.append(
                        Cut(
                            start_ms=start,
                            end_ms=end,
                            reason="stutter",
                            confidence="low",
                            detail=f"repeat={current.text}|{nxt.text}",
                        )
                    )
    return merge_cuts(cuts)


def merge_cuts(cuts: Iterable[Cut], merge_gap_ms: int = 80) -> list[Cut]:
    ordered = sorted(cuts, key=lambda item: (item.start_ms, item.end_ms))
    merged: list[Cut] = []
    for cut in ordered:
        if not merged or cut.start_ms > merged[-1].end_ms + merge_gap_ms:
            merged.append(cut)
            continue
        prev = merged[-1]
        prev.end_ms = max(prev.end_ms, cut.end_ms)
        prev.reason = prev.reason if prev.reason == cut.reason else "mixed"
        prev.confidence = "high" if "high" in {prev.confidence, cut.confidence} else prev.confidence
        prev.detail = f"{prev.detail}; {cut.detail}"
    return merged


def keep_segments(cuts: list[Cut], duration_ms: int, min_keep_ms: int = 500) -> list[dict[str, int]]:
    segments: list[dict[str, int]] = []
    cursor = 0
    for cut in cuts:
        start = max(0, min(cut.start_ms, duration_ms))
        end = max(start, min(cut.end_ms, duration_ms))
        if start - cursor >= min_keep_ms:
            segments.append({"start_ms": cursor, "end_ms": start})
        cursor = max(cursor, end)
    if duration_ms - cursor >= min_keep_ms:
        segments.append({"start_ms": cursor, "end_ms": duration_ms})
    return segments


def infer_duration_ms(words: list[Word], payload: dict[str, Any]) -> int:
    explicit = payload.get("duration_ms") or payload.get("duration")
    if explicit:
        return _to_ms(explicit)
    if words:
        return max(item.end_ms for item in words)
    return 0


def build_plan(payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    words = flatten_words(payload)
    duration_ms = args.duration_ms or infer_duration_ms(words, payload)
    cuts = plan_cuts(
        words,
        duration_ms=duration_ms,
        min_pause_ms=args.min_pause_ms,
        hard_pause_ms=args.hard_pause_ms,
        pre_roll_ms=args.pre_roll_ms,
        post_roll_ms=args.post_roll_ms,
        min_cut_ms=args.min_cut_ms,
    )
    return {
        "version": 1,
        "duration_ms": duration_ms,
        "words": [asdict(item) for item in words],
        "cut_candidates": [asdict(item) for item in cuts],
        "keep_segments": keep_segments(cuts, duration_ms, min_keep_ms=args.min_keep_ms),
        "settings": {
            "min_pause_ms": args.min_pause_ms,
            "hard_pause_ms": args.hard_pause_ms,
            "pre_roll_ms": args.pre_roll_ms,
            "post_roll_ms": args.post_roll_ms,
            "min_cut_ms": args.min_cut_ms,
            "min_keep_ms": args.min_keep_ms,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan cuts from word-level alignment JSON.")
    parser.add_argument("alignment_json", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--duration-ms", type=int, default=0)
    parser.add_argument("--min-pause-ms", type=int, default=350)
    parser.add_argument("--hard-pause-ms", type=int, default=700)
    parser.add_argument("--pre-roll-ms", type=int, default=80)
    parser.add_argument("--post-roll-ms", type=int, default=120)
    parser.add_argument("--min-cut-ms", type=int, default=180)
    parser.add_argument("--min-keep-ms", type=int, default=500)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = json.loads(args.alignment_json.read_text(encoding="utf-8"))
    plan = build_plan(payload, args)
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
