# Local Talking-Head Video Skill Design

## Goal

Create a Codex skill that turns one or more talking-head videos plus a script into a finished MP4 without depending on Coze or CapCut/Jianying draft generation.

The skill should preserve the useful workflow logic from the reference Coze package while replacing platform nodes with local scripts, ffmpeg processing, Volcengine speech alignment, LLM planning, and Remotion rendering.

## Non-Goals

- Do not generate Jianying/CapCut drafts.
- Do not require the user to choose horizontal or vertical output manually.
- Do not build a batch operations dashboard in the first version.
- Do not depend on a single third-party music or sound-effects catalog.
- Do not silently use media assets without recording source and license metadata.

## User-Facing Interface

The skill should trigger when the user asks to create, edit, or render a talking-head video from source footage and a script.

Minimum inputs:

- Source video path or paths.
- Script/caption text.
- Optional output path.
- Optional style preset.
- Optional BGM or sound-effect preference.

The skill detects source orientation by probing the first usable video stream:

- `width >= height`: horizontal template.
- `height > width`: vertical template.

The first implementation should accept local files. Remote URLs can be downloaded in a later version after adding explicit safety and size limits.

## Architecture

Use a two-layer implementation:

1. Python and ffmpeg preprocessing.
2. Remotion final rendering.

Python owns deterministic media operations:

- Validate input files.
- Probe video metadata.
- Concatenate source videos when needed.
- Extract audio.
- Call Volcengine speech alignment.
- Build word-level and subtitle-level timelines.
- Detect pauses, filler regions, and repeated stutters.
- Generate keep segments.
- Cut and concatenate clean video.
- Prepare a JSON render manifest for Remotion.
- Resolve BGM and sound effects.

Remotion owns visual composition:

- Burn subtitles.
- Render hook text, key phrases, data highlights, and term cards.
- Place lightweight sticker-like visual elements.
- Add timed sound effects and BGM.
- Render the final MP4.

ffmpeg remains the underlying media utility for probing, audio extraction, cutting, concat, normalization, and muxing.

## Data Flow

1. Probe source media.
2. Concatenate source videos into a normalized working input if more than one file is provided.
3. Extract audio.
4. Submit audio and script to Volcengine automatic subtitle alignment.
5. Poll alignment results.
6. Flatten `utterances[].words[]` into a word timeline.
7. Use utterances for subtitle grouping only.
8. Generate pause and stutter cut candidates from word-level gaps and repeated tokens.
9. Confirm cut candidates with silence or low-energy detection.
10. Convert cut candidates into keep segments with short padding.
11. Cut and concatenate video.
12. Rebuild subtitles against the cleaned timeline.
13. Ask an LLM to identify hook text, key phrases, numbers, term highlights, and BGM style.
14. Search or select BGM and sound effects.
15. Write a render manifest.
16. Render final MP4 with Remotion.
17. Write sidecar metadata for source files, asset licenses, settings, and timing decisions.

## Volcengine Alignment Requirements

The Coze workflow used sentence-level `utterance.start_time` and `utterance.end_time` for cutting. That misses pauses and stutters inside a single sentence.

This skill must use word-level timing as the primary edit signal:

- Use `utterances[].words[]` for cut detection.
- Use `utterances[]` for readable subtitle grouping.
- Do not treat a full utterance as a mandatory keep segment.

Pause detection:

- Compare `word[i].end_time` and `word[i + 1].start_time`.
- If the gap exceeds a configurable threshold, create a cut candidate.
- Default thresholds:
  - `min_pause_ms`: 350 ms.
  - `hard_pause_ms`: 700 ms.
  - `pre_roll_ms`: 80 ms.
  - `post_roll_ms`: 120 ms.

Validation:

- Confirm medium-length gaps with audio energy or ffmpeg silence detection.
- Always cut hard pauses unless the surrounding words are too close to a segment boundary.
- Keep a minimum resulting clip length to avoid jumpy micro-cuts.

Stutter detection:

- Detect adjacent repeated words or characters, such as `我 我`, `这 这个`, or repeated filler particles.
- Only remove a stutter region when timing and transcript evidence agree.
- Prefer conservative cuts over aggressive deletion in MVP.

The implementation should keep the original alignment payload for diagnostics.

## Asset Sources

Use an adapter layer for BGM and sound effects. Each provider returns a common asset object:

- `id`
- `kind`: `bgm` or `sfx`
- `title`
- `creator`
- `source`
- `download_url`
- `preview_url`
- `duration_ms`
- `license`
- `requires_attribution`
- `attribution_text`
- `tags`

Recommended MVP providers:

- Local asset library: safest default for production and repeatable rendering.
- Freesound API: good for sound effects, with license filtering and attribution metadata.
- Openverse API: useful for broad Creative Commons audio search.

Optional later providers:

- Pixabay API for music and sound effects, subject to its API and content license terms.
- Jamendo API for music discovery, subject to track-specific licensing.
- User-provided commercial libraries.

Provider rules:

- Never use an asset if the license is unknown.
- Prefer assets marked safe for commercial use when the user does not specify licensing.
- Store source and attribution in a sidecar JSON file.
- Do not assume that "free to download" means "free for all commercial use."
- Allow users to disable external search and use only local assets.

## LLM Planning

The LLM should produce structured JSON only. It should not directly edit video.

Expected outputs:

- BGM style keyword.
- Hook text with timing.
- Key phrases with timing and style.
- Number highlights with timing.
- Term highlights with timing.
- Optional sound-effect cues.
- Optional visual theme preset.

All LLM timing suggestions must be clamped to valid subtitle or word ranges before rendering.

## Remotion Render Manifest

The preprocessing layer writes a render manifest consumed by Remotion:

- Output dimensions and fps.
- Cleaned video path.
- Duration.
- Subtitle timeline.
- Visual event timeline.
- BGM file and volume envelope.
- Sound-effect files and timing.
- Theme preset.
- Attribution metadata.

Remotion should render from this manifest without calling external APIs.

## Error Handling

- Missing input video: fail fast.
- Missing script: fail fast unless the user explicitly asks for ASR-only generation.
- Volcengine authentication failure: fail with setup instructions.
- Alignment result has no word timings: fall back to utterance-level subtitle grouping, but do not perform precision pause cutting.
- Asset provider failure: continue with local assets or no BGM/SFX.
- Remotion render failure: preserve the render manifest and intermediate files for debugging.

## Testing

Use small fixture videos for local validation.

Test cases:

- Horizontal source auto-selects horizontal render.
- Vertical source auto-selects vertical render.
- Multi-video input concatenates correctly.
- Word-level gap creates a cut candidate.
- Sentence-internal pause is removed.
- Short natural pause is preserved.
- Repeated stutter is conservatively detected.
- Missing Volcengine credentials fails clearly.
- Render manifest validates before Remotion starts.
- Asset metadata includes source and license.

## Open Assumptions

- The first version can require local Volcengine credentials from environment variables.
- MVP visual effects can be simple but polished.
- External BGM/SFX search is optional and should not block rendering.
- The first version can prioritize Chinese talking-head videos, while keeping the code extensible for other languages.

