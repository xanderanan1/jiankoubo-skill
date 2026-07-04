#!/usr/bin/env python3
"""Prepare an alignment payload for cut planning without duplicating provider work."""

from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import select_script_span


PUNCTUATION_RE = re.compile(r"[\s，。！？!?、：:；;“”\"'（）()《》【】\[\]\{\}<>,.]+")


def clean_text(text: str) -> str:
    return PUNCTUATION_RE.sub("", text or "").lower()


def provider_from_payload(payload: dict[str, Any], explicit_provider: str) -> str:
    if explicit_provider != "auto":
        return explicit_provider
    source = str(payload.get("source") or "").lower()
    if source.startswith("volcengine:"):
        return "volcengine"
    if source.startswith("funasr:") or source.startswith("whisper:"):
        return "asr"
    return "asr"


def transcript_from_payload(payload: dict[str, Any]) -> str:
    pieces: list[str] = []
    for utterance in payload.get("utterances", []) or []:
        words = utterance.get("words", []) or []
        if words:
            pieces.extend(str(word.get("text") or word.get("word") or "") for word in words if isinstance(word, dict))
        else:
            pieces.append(str(utterance.get("text") or ""))
    return clean_text("".join(pieces))


def score_alignment(payload: dict[str, Any], target_script: str) -> dict[str, Any]:
    target = clean_text(target_script)
    transcript = transcript_from_payload(payload)
    if not target or not transcript:
        score = 0.0
    elif transcript.find(target) >= 0 or target.find(transcript) >= 0:
        score = 1.0
    else:
        score = SequenceMatcher(None, transcript, target, autojunk=False).ratio()
    return {
        "method": "provider_aligned_guard",
        "score": round(score, 4),
        "target_text": target,
        "matched_text": transcript,
        "message": "provider alignment was used directly; no script span slicing was applied",
    }


def write_json(path: Path | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_provider_alignment(
    payload: dict[str, Any],
    script: str,
    output: Path,
    match_output: Path | None,
    min_score: float,
) -> None:
    diagnostic = score_alignment(payload, script)
    write_json(match_output, diagnostic)
    if diagnostic["score"] < min_score:
        raise SystemExit(f"provider alignment guard score too low: {diagnostic['score']:.3f}")
    payload = dict(payload)
    payload["source"] = str(payload.get("source") or "provider_aligned")
    payload["script_guard"] = diagnostic
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_asr_selection(
    payload: dict[str, Any],
    script: str,
    output: Path,
    match_output: Path | None,
    min_score: float,
) -> None:
    words = select_script_span.flatten_words(payload)
    if not words:
        raise SystemExit("alignment has no word timings")
    transcript, char_to_word = select_script_span.transcript_chars(words)
    target = select_script_span.clean_text(script)
    if not target:
        raise SystemExit("target script is empty after normalization")
    char_start, char_end, score, method = select_script_span.exact_or_fuzzy_span(transcript, target)
    if score < min_score:
        diagnostic = {
            "method": method,
            "score": score,
            "target": target,
            "transcript": transcript,
            "message": "target script was not found confidently in the ASR transcript",
        }
        write_json(match_output, diagnostic)
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
    output_payload = select_script_span.selected_payload(payload, words, start_word, end_word, match)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_json(match_output, match)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare alignment JSON for cut planning.")
    parser.add_argument("alignment_json", type=Path)
    parser.add_argument("--script", help="Target script text to keep.")
    parser.add_argument("--script-file", type=Path, help="Path containing target script text.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--match-output", type=Path)
    parser.add_argument("--provider", choices=["auto", "volcengine", "asr"], default="auto")
    parser.add_argument("--min-score", type=float, default=0.55)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    script = args.script or (args.script_file.read_text(encoding="utf-8") if args.script_file else "")
    payload = json.loads(args.alignment_json.read_text(encoding="utf-8"))
    provider = provider_from_payload(payload, args.provider)
    if provider == "volcengine":
        copy_provider_alignment(payload, script, args.output, args.match_output, args.min_score)
    else:
        run_asr_selection(payload, script, args.output, args.match_output, args.min_score)
    print(args.output)


if __name__ == "__main__":
    main()
