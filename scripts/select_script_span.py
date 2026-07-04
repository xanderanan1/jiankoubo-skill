#!/usr/bin/env python3
"""Select the spoken span matching the user's target script from full ASR alignment."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


PUNCTUATION_RE = re.compile(r"[\s，。！？!?、：:；;“”\"'（）()《》【】\[\]\{\}<>,.]+")


@dataclass
class Word:
    text: str
    start_ms: int
    end_ms: int


def to_ms(value: Any) -> int:
    return int(round(float(value)))


def clean_text(text: str) -> str:
    return PUNCTUATION_RE.sub("", text or "").lower()


def flatten_words(payload: dict[str, Any]) -> list[Word]:
    words: list[Word] = []
    for utterance in payload.get("utterances", []) or []:
        for raw in utterance.get("words", []) or []:
            text = str(raw.get("text") or raw.get("word") or "").strip()
            start = raw.get("start_time", raw.get("start_ms", raw.get("start")))
            end = raw.get("end_time", raw.get("end_ms", raw.get("end")))
            if not text or start is None or end is None:
                continue
            start_ms = to_ms(start)
            end_ms = to_ms(end)
            if end_ms >= start_ms:
                words.append(Word(text=text, start_ms=start_ms, end_ms=end_ms))
    words.sort(key=lambda item: (item.start_ms, item.end_ms))
    return words


def transcript_chars(words: list[Word]) -> tuple[str, list[int]]:
    chars: list[str] = []
    char_to_word: list[int] = []
    for word_index, word in enumerate(words):
        cleaned = clean_text(word.text)
        for char in cleaned:
            chars.append(char)
            char_to_word.append(word_index)
    return "".join(chars), char_to_word


def exact_or_fuzzy_span(transcript: str, target: str) -> tuple[int, int, float, str]:
    exact_index = transcript.find(target)
    if exact_index >= 0:
        return exact_index, exact_index + len(target), 1.0, "exact"

    if not transcript or not target:
        return 0, 0, 0.0, "empty"

    target_len = len(target)
    min_len = max(1, int(target_len * 0.55))
    max_len = min(len(transcript), max(min_len, int(target_len * 1.65)))
    step = max(1, target_len // 18)
    lengths = sorted(
        {
            min(max_len, max(min_len, int(target_len * ratio)))
            for ratio in (0.65, 0.8, 0.95, 1.0, 1.15, 1.35, 1.55)
        }
    )
    best = (0, min(len(transcript), target_len), 0.0)
    for length in lengths:
        if length > len(transcript):
            continue
        last_start = len(transcript) - length
        for start in range(0, last_start + 1, step):
            window = transcript[start : start + length]
            score = SequenceMatcher(None, window, target, autojunk=False).ratio()
            if score > best[2]:
                best = (start, start + length, score)
        if last_start % step:
            window = transcript[last_start : last_start + length]
            score = SequenceMatcher(None, window, target, autojunk=False).ratio()
            if score > best[2]:
                best = (last_start, last_start + length, score)
    return best[0], best[1], best[2], "fuzzy"


def selected_payload(
    source_payload: dict[str, Any],
    words: list[Word],
    start_word: int,
    end_word: int,
    match: dict[str, Any],
) -> dict[str, Any]:
    selected_words = words[start_word : end_word + 1]
    utterance = {
        "text": "".join(word.text for word in selected_words),
        "start_time": selected_words[0].start_ms,
        "end_time": selected_words[-1].end_ms,
        "words": [
            {"text": word.text, "start_time": word.start_ms, "end_time": word.end_ms}
            for word in selected_words
        ],
    }
    return {
        "duration_ms": source_payload.get("duration_ms") or source_payload.get("duration"),
        "source": "selected_script_span",
        "match": match,
        "utterances": [utterance],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Select target-script word span from a full ASR alignment JSON.")
    parser.add_argument("alignment_json", type=Path)
    parser.add_argument("--script", help="Target script text to keep.")
    parser.add_argument("--script-file", type=Path, help="Path containing target script text.")
    parser.add_argument("--output", type=Path, required=True, help="Selected alignment JSON output.")
    parser.add_argument("--match-output", type=Path, help="Write match diagnostics JSON.")
    parser.add_argument("--min-score", type=float, default=0.55)
    args = parser.parse_args()

    target_script = args.script or (args.script_file.read_text(encoding="utf-8") if args.script_file else "")
    target = clean_text(target_script)
    if not target:
        raise SystemExit("target script is empty after normalization")

    payload = json.loads(args.alignment_json.read_text(encoding="utf-8"))
    words = flatten_words(payload)
    if not words:
        raise SystemExit("alignment has no word timings")

    transcript, char_to_word = transcript_chars(words)
    if not transcript:
        raise SystemExit("alignment transcript is empty after normalization")

    char_start, char_end, score, method = exact_or_fuzzy_span(transcript, target)
    if score < args.min_score:
        diagnostic = {
            "method": method,
            "score": score,
            "target": target,
            "transcript": transcript,
            "message": "target script was not found confidently in the ASR transcript",
        }
        if args.match_output:
            args.match_output.parent.mkdir(parents=True, exist_ok=True)
            args.match_output.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(f"target script match score too low: {score:.3f}")

    char_end = max(char_start + 1, min(char_end, len(char_to_word)))
    start_word = char_to_word[char_start]
    end_word = char_to_word[char_end - 1]
    match = {
        "method": method,
        "score": round(score, 4),
        "target_text": target,
        "matched_text": transcript[char_start:char_end],
        "start_ms": words[start_word].start_ms,
        "end_ms": words[end_word].end_ms,
        "start_word_index": start_word,
        "end_word_index": end_word,
    }
    output_payload = selected_payload(payload, words, start_word, end_word, match)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.match_output:
        args.match_output.parent.mkdir(parents=True, exist_ok=True)
        args.match_output.write_text(json.dumps(match, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
