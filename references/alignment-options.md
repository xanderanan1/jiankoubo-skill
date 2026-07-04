# Alignment Options

Use this reference before generating subtitles, cuts, or highlight timings.

## Entry Contract

The user must provide both:

- source video path
- target script text for the section to keep

If either is missing, pause and ask for the missing input. Do not rely on ASR to invent the script for production renders. The target script may be only part of the full source video; spoken content outside the matched target span should be trimmed away.

## Default Choice

After video and script are available, use Volcengine ATA automatic subtitle alignment first for Chinese口播. The target script may be only part of the full source video; Volcengine ATA aligns the provided script to the audio, and the downstream selector/cut planner still uses word timings to trim away content outside the matched script span.

If the user provides Volcengine credentials in chat, export them into the current command/session environment as:

```bash
export VOLCENGINE_ATA_APPID="..."
export VOLCENGINE_ATA_TOKEN="..."
```

Do not write these values to files. If a tool call cannot inherit a prior shell environment, pass `--appid` and `--token` directly to `scripts/volcengine_align.py`; the script copies them into `os.environ` for that process only.

Accepted alternatives:

- Existing alignment JSON: validate it against `references/volcengine-alignment.md` and continue.
- Use local FunASR fallback only when the user explicitly asks for it or accepts falling back after Volcengine fails.
- Use local Whisper fallback only if both Volcengine and FunASR are unavailable and the user accepts lower Chinese accuracy.

## Preferred Path: Volcengine ATA Alignment

Use `scripts/volcengine_align.py` for API-based Chinese script alignment. It normalizes the API response into the schema consumed by the rest of the skill:

```bash
python3 scripts/volcengine_align.py source.mp4 \
  --script-file script.txt \
  --output full-alignment.json \
  --raw-output volcengine-raw.json \
  --submit-output volcengine-submit.json \
  --work-dir work
```

When credentials are available only in the current user message, pass them for this run:

```bash
python3 scripts/volcengine_align.py source.mp4 \
  --script-file script.txt \
  --appid "$VOLCENGINE_ATA_APPID" \
  --token "$VOLCENGINE_ATA_TOKEN" \
  --output full-alignment.json
```

Expected normalized output:

```json
{
  "utterances": [
    {
      "text": "示例句子",
      "start_time": 0,
      "end_time": 1200,
      "words": [
        {"text": "示例", "start_time": 0, "end_time": 500},
        {"text": "句子", "start_time": 700, "end_time": 1200}
      ]
    }
  ]
}
```

Times must be milliseconds. Preserve the raw API response separately when practical, but only feed the normalized shape into bundled scripts.

## Fallback Path: FunASR Local Alignment

Use `scripts/funasr_align.py` only as an explicit fallback. It normalizes FunASR output into the same schema:

```bash
python3 scripts/funasr_align.py source.mp4 \
  --mode asr \
  --output full-alignment.json \
  --raw-output funasr-raw.json \
  --work-dir work
```

Use `--mode force-align --script-file script.txt` only when the audio is already trimmed to the script or the script covers the whole source video. If the source contains extra speech, run ASR over the full video and select the target span after ASR.

## Target Script Selection

Before cut planning, prepare the alignment according to its source. Volcengine ATA output is already aligned to the provided target script, so use it directly and write a lightweight guard diagnostic. Full-video ASR fallbacks still need script-span selection:

```bash
python3 scripts/prepare_alignment_for_cuts.py full-alignment.json \
  --script-file script.txt \
  --output selected-alignment.json \
  --match-output script-match.json
```

Use `selected-alignment.json` for `cut_planner.py` and `build_manifest.py`. With Volcengine ATA, this file is effectively the provider alignment plus guard metadata. With ASR fallbacks, this file contains the selected script span.

## Last-Resort Path: Local Whisper

Use local Whisper only when Volcengine and FunASR are unavailable or fail and the user accepts the fallback.

Requirements:

- local Python `whisper` package or another local Whisper-compatible tool
- word timestamps if supported by the local implementation

If local Whisper cannot produce word-level timings:

- create utterance-level timing as a degraded fallback
- tell the user that gas-mouth/stutter cuts will be less precise
- avoid claiming sentence-internal stutter removal is fully reliable

## No Alignment Available

If neither Volcengine ATA nor local fallback tools can produce usable timing:

- do not proceed with precision subtitle/highlight timing
- ask the user to provide alignment JSON or enable an alignment method
- optionally offer a rough no-subtitle/no-highlight cut only if the user accepts lower quality

## Run Artifacts

Keep only alignment payloads, manifests, attribution, and diagnostics.
