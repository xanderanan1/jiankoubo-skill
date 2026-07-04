# Local Talking-Head Video Pipeline

## Purpose

Replace the Coze workflow with a local pipeline that outputs a finished MP4 directly.

## Stages

1. Validate that the user provided both local video paths and target script text.
2. Probe the first video stream with `ffprobe`.
3. Infer render orientation:
   - `width >= height`: horizontal.
   - `height > width`: vertical.
4. Normalize or concatenate inputs with ffmpeg.
5. Extract audio as WAV for analysis/alignment.
6. Run Volcengine ATA automatic subtitle alignment, or consume a saved word-level alignment JSON.
7. Use local FunASR only as an explicit fallback; use local Whisper only as the last resort.
8. Flatten `utterances[].words[]`.
9. Prepare the alignment with `scripts/prepare_alignment_for_cuts.py`: use Volcengine ATA output directly, but script-match full-video ASR fallbacks.
10. Use the prepared alignment for cut planning so provider-aligned script timing and ASR fallback slicing share the same downstream path.
11. Generate pause and stutter cut candidates.
12. Confirm cuts with audio-energy or silence checks where available.
13. Generate keep segments.
14. Cut and concatenate the clean video.
15. Rebuild subtitle timings against the cleaned timeline with `scripts/build_manifest.py`.
16. Ask an LLM for structured visual and audio cues.
17. Resolve BGM/SFX through local assets and configured providers.
18. Write a Remotion render manifest.
19. Render final MP4 with Remotion.
20. Write attribution and diagnostic sidecar JSON.

## Suggested Working Directory

Use a per-render folder:

```text
output/
  work/
    source-normalized.mp4
    source.wav
    full-alignment.json
    selected-alignment.json
    script-match.json
    cut-plan.json
    clean.mp4
    manifest.json
    attribution.json
  final.mp4
```

## Editing Presets

Aggressive talking-head default:

- `min_pause_ms`: 350
- `hard_pause_ms`: 700
- `pre_roll_ms`: 80
- `post_roll_ms`: 120
- `min_keep_ms`: 500
- `min_cut_ms`: 180

Conservative preset:

- `min_pause_ms`: 600
- keep the other defaults unchanged

Use the aggressive preset for short-video口播 where pace matters. Use the conservative preset for interviews, formal explainers, or emotionally sensitive delivery.

## Base Defaults

- `min_pause_ms`: 350
- `hard_pause_ms`: 700
- `pre_roll_ms`: 80
- `post_roll_ms`: 120
- `min_keep_ms`: 500
- `min_cut_ms`: 180

Adjust thresholds per video style. Faster social clips can use lower pause thresholds; formal interviews should be less aggressive.
