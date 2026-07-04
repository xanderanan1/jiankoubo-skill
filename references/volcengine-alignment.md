# Volcengine Alignment Notes

## API Path

Use Volcengine ATA automatic subtitle alignment as the default alignment provider. The API flow is:

1. Extract a mono 16 kHz WAV from the source media.
2. Submit the WAV plus the user's target script text to `https://openspeech.bytedance.com/api/v1/vc/ata/submit`.
3. Query `https://openspeech.bytedance.com/api/v1/vc/ata/query` with the returned task id.
4. Normalize the returned `utterances[].words[]` into the schema below.

Credentials come from the current environment:

- `VOLCENGINE_ATA_APPID`
- `VOLCENGINE_ATA_TOKEN`

If the user provides credentials during a conversation, export them for the current command/session only. Do not write them to a credentials file.

## Expected Shape

The automatic subtitle alignment result should contain utterance-level groups and word-level timings. Keep the raw response for diagnostics.

Expected normalized shape:

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

Times are treated as milliseconds by the bundled scripts. If an API response uses seconds or microseconds, normalize before calling the cut planner.

## Cutting Rules

Use word timings as the edit source:

- `gap_ms = next_word.start_ms - current_word.end_ms`
- Create a pause candidate when `gap_ms >= min_pause_ms`.
- Mark it as hard when `gap_ms >= hard_pause_ms`.
- Cut from `current_word.end_ms + pre_roll_ms` to `next_word.start_ms - post_roll_ms`.
- Discard cuts shorter than `min_cut_ms`.
- Merge nearby cuts before converting to keep segments.

Do not keep whole utterances by default. Utterances are useful for readable subtitle grouping but too coarse for precise pause removal.

For short-video口播, use the aggressive preset by default:

```bash
scripts/cut_planner.py alignment.json --output cut-plan.json --duration-ms <duration>
scripts/apply_cut_plan.py source.mp4 cut-plan.json clean.mp4
```

For a calmer edit, raise the pause threshold:

```bash
scripts/cut_planner.py alignment.json --output cut-plan.json --duration-ms <duration> --min-pause-ms 600
```

## Stutter Rules

Detect adjacent repeated or near-repeated tokens:

- exact repeats: `我 我`, `对 对`
- prefix repeats: `这 这个`, `就 就是`
- common filler tokens: `嗯`, `呃`, `啊`, `那个`, `这个`

Only cut a stutter when the repeated token duration is plausible and the resulting keep segments remain long enough.

## Fallbacks

If no word timings exist:

- generate subtitles from utterances
- skip precision cut planning
- tell the user that the alignment response lacks word-level timing
