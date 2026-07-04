---
name: render-talking-video
description: Create finished talking-head MP4 videos from local source footage and scripts without Coze or CapCut/Jianying drafts. Use when Codex needs to edit口播/talking-head videos, cut pauses or stutters, align subtitles with Volcengine ATA/FunASR or word timings, add captions/highlights/BGM/sound effects, prepare a Remotion render manifest, or render a local short-video deliverable.
---

# Render Talking Video

## Overview

Use this skill to turn one or more local talking-head videos plus a script into a finished MP4. Preserve the reference Coze workflow's logic, but replace platform nodes with local Python, ffmpeg, Volcengine ATA/FunASR fallback alignment, structured LLM planning, asset-provider adapters, and Remotion rendering.

When the user wants an actual finished render, read `references/agent-runbook.md` first. It contains the reproducible command sequence and sidecar outputs. Do not rely on hidden conversation context from prior renders.

Video path and target script text are mandatory inputs. The script is the section the user wants to keep, not necessarily the full-video transcript. If either is missing, ask for it before doing alignment, cutting, or rendering. After both are present, use Volcengine ATA automatic subtitle alignment first. If the user provides Volcengine credentials during the conversation, set them as environment variables for the current run (`VOLCENGINE_ATA_APPID`, `VOLCENGINE_ATA_TOKEN`) and do not write them to disk. Use FunASR only when the user explicitly asks for the local fallback or Volcengine is unavailable and the user accepts the lower-quality path.

## Workflow

1. Confirm the user provided both video path and target script text.
2. Use Volcengine ATA first for Chinese script-to-audio alignment. Ask for `appid` and `access token` only when they are not already available in the current environment. Store user-provided credentials only in the current process environment, never in project files. Use FunASR only as an explicit fallback.
3. Probe media with `ffprobe`; infer orientation from the first usable video stream.
4. Use Python and ffmpeg for deterministic preprocessing:
   - normalize/concatenate input clips
   - extract audio
   - call or consume Volcengine ATA alignment
   - optionally call or consume FunASR fallback alignment
   - or consume existing alignment / local Whisper fallback timings
   - build word-level timelines
   - prepare the alignment for cut planning: use Volcengine ATA alignment directly, but run script-span selection for full-video ASR fallbacks
   - plan pause/stutter cuts
   - create a cleaned video
5. Use an LLM for structured creative planning before manifest construction: infer the video domain/content type, then design an opening hook, key phrases, general semantic highlight types, component variants, layout preferences, palette, motion parameters, decorations, BGM style, and optional sound-effect cues.
6. Resolve BGM/SFX through the local curated asset indexes first, then configured external providers.
7. Write a render manifest.
8. Render with Remotion using the bundled starter template or a project-specific template.
9. Run post-render visual QA: sample hook/highlight/subtitle frames, check component overlap, subtitle safe area, lower platform overlay band, automatic face occlusion where OpenCV is available, and optional `--focus-box` key visual regions for products/screens/logos/food/other important scene elements.
10. Preserve intermediate JSON files, attribution metadata, QA report, and QA contact sheet.

## Critical Rule: Cut From Words, Not Sentences

Do not use `utterance.start_time` and `utterance.end_time` as mandatory keep ranges. That misses sentence-internal pauses, repeats, and stutters.

Use `utterances[].words[]` as the primary edit signal:

- Compare each `word.end_time` to the next `word.start_time`.
- Create cut candidates when the gap is long enough.
- Use utterances only to group readable subtitles.
- If the alignment source is Volcengine ATA, use it directly and only run a lightweight script guard; if the source is full-video ASR such as FunASR/Whisper, run script-span selection before cutting.
- Validate medium gaps with audio energy or ffmpeg silence detection before cutting.
- Keep the algorithm conservative for repeated words; only remove stutters when timing and transcript evidence agree.

Run `scripts/cut_planner.py` on an alignment payload to generate cut candidates and keep segments.

Default to the aggressive talking-head preset unless the user asks for a calmer edit:

- aggressive: `min_pause_ms=350`
- conservative: `min_pause_ms=600`

Run `scripts/apply_cut_plan.py` to render a cleaned video from the generated keep segments.

## Bundled Resources

- `references/pipeline.md`: end-to-end local video workflow.
- `references/agent-runbook.md`: reproducible agent handoff and command sequence for finished MP4 renders.
- `references/alignment-options.md`: mandatory input contract, Volcengine-first alignment, and fallback rules.
- `references/dependencies.md`: required system binaries, Python/NPM dependencies, external services, and bundled assets.
- `references/volcengine-alignment.md`: expected alignment structure and word-level cutting rules.
- `references/asset-providers.md`: local, Freesound, Openverse, Pixabay, and Jamendo provider guidance.
- `references/highlight-planning.md`: LLM-first key phrase planning schema, semantic types, and keyword SFX mapping.
- `references/remotion-manifest.md`: render manifest schema consumed by Remotion.
- `scripts/cut_planner.py`: deterministic pause/stutter cut planner for normalized alignment JSON.
- `scripts/volcengine_align.py`: call Volcengine ATA automatic subtitle alignment and normalize timestamps into the skill alignment schema.
- `scripts/funasr_align.py`: run local FunASR ASR or forced alignment as an explicit fallback and normalize timestamps into the skill alignment schema.
- `scripts/prepare_alignment_for_cuts.py`: route provider-aligned payloads directly to cutting, and run script-span selection only for full-video ASR fallbacks.
- `scripts/select_script_span.py`: match the user's target script inside full-video ASR alignment and output selected word timings so extra source-video content can be trimmed.
- `scripts/apply_cut_plan.py`: ffmpeg renderer that applies a cut plan to the source video.
- `scripts/build_manifest.py`: remap alignment timings after cuts and create a Remotion manifest.
- `scripts/prepare_remotion_project.py`: copy the Remotion template, rewrite video paths to public-relative paths, and verify public audio assets.
- `scripts/manifest_to_ass.py`: create an ASS subtitle preview file from a manifest for fast ffmpeg review renders.
- `scripts/validate_manifest.py`: render manifest validator with no third-party dependencies.
- `scripts/post_render_check.py`: post-render visual QA for component overlap, subtitle safe area, lower platform overlay band, face occlusion, and optional key visual focus boxes. Generates a JSON report and contact sheet.
- `scripts/export_attribution.py`: export `manifest.attribution` to a sidecar JSON file.
- `scripts/probe_media.py`: ffprobe wrapper for orientation and duration checks.
- `assets/remotion-template/`: starter Remotion project that renders video, subtitles, highlights, BGM, and SFX from a manifest.

## Highlight Semantics

Do not classify flower-text highlights by a sample video's industry. First ask an LLM to infer the current video's domain/content type and choose cross-domain semantic roles, then let scripts align those phrases to word timings and fill only missing slots with deterministic rules. A car example is only an example; the same flow must work for tutorials, digital products, finance explainers, food/lifestyle recommendations, emotional stories, risk warnings, and other talking-head videos. Use:

- `entity`: people, brands, products, places, named topics
- `number`: prices, discounts, quantities, percentages, time spans
- `benefit`: advantages, effects, outcomes, value propositions
- `proof`: rankings, awards, certifications, official claims, data-backed trust
- `risk`: warnings, constraints, pitfalls, negative surprises
- `action`: steps, instructions, calls to action
- `emotion`: reactions, attitudes, surprise, punchlines

Render manifests should prefer `semantic_type` plus `visual_style`; keep `style` only as a compatibility alias. The bundled Remotion template maps semantic roles to a unified emphasis system: opening hook, inline subtitle emphasis, and flower text all share semantic colors, levels, and motion presets rather than living as separate effects.

Use `component`, `variant`, `layout`, `palette`, `decorations`, `emphasis_level`, `render_mode`, and `motion` to control emphasis. Keep old `motion_preset` as a compatibility alias:

- `emphasis_level: 1`: subtle inline caption highlight
- `emphasis_level: 2`: stronger inline caption highlight, optionally with SFX
- `emphasis_level: 3`: flower text / card emphasis
- `render_mode`: `caption` or `flower`
- `motion_preset`: GSAP-like motion names implemented with Remotion frame math, such as `numberBurst`, `stampIn`, `warningShake`, `slideSnap`, `softGlow`, `cardRise`, `popElastic`, or `hookSnap`

Keyword sound effects should be short, local, and aligned to `visual_events[].start_ms`. The default generated SFX library maps semantic roles to distinct emphasis sounds; do not use external SFX unless license metadata is written into `attribution`.

When `assets/audio/pixabay/index.json` exists, `scripts/build_manifest.py` should prefer its processed public-relative SFX and BGM assets. Use `--no-pixabay-assets` to force the older generated local SFX, `--no-bgm` for speech-only output, or `--bgm-style` to force one of the curated BGM styles.

Before rendering through the starter template, run `scripts/prepare_remotion_project.py`. Remotion `staticFile()` requires public-relative paths; do not pass absolute video paths into the template manifest.

## External Dependencies

Prefer installed local binaries:

- `ffmpeg`
- `ffprobe`
- `python3`
- `node`
- `npm`

`scripts/post_render_check.py` uses OpenCV for sampled frame extraction, contact-sheet drawing, and face occlusion checks. If `cv2` is missing, the script automatically installs `opencv-python` with the current Python interpreter before running QA. Only use `--no-auto-install-opencv` when the machine must not install Python packages; in that case QA degrades to layout-only checks.

Do not require external BGM/SFX search for a successful render. Continue with local assets or no music/sound effects if providers are unavailable.

## Asset License Handling

Every audio asset used in a render must carry metadata:

- source
- creator
- license
- source URL
- attribution text
- whether attribution is required

Never silently use assets with unknown license status. Prefer local curated assets for repeatable production renders.

## Output Expectations

For each render, produce:

- final MP4
- render manifest JSON
- cut-plan JSON
- attribution/metadata JSON
- post-render visual QA JSON
- post-render QA contact sheet / sampled debug frames
- preserved alignment payload when available

When a render fails, keep the manifest and intermediate files so the next Codex turn can debug rather than restart.

## Completion Bar

The skill is complete when Remotion has produced the final MP4, post-render visual QA has run, and the expected sidecar files are preserved in the run directory. If QA status is `fail`, inspect the contact sheet and adjust the director plan, component layout, or subtitle position before handing the result back. If QA status is `warn`, report the warning and decide whether it needs a rerender based on the sampled frames.

Before rendering, `scripts/validate_manifest.py` may be used to catch manifest mistakes. After rendering, run `scripts/post_render_check.py`, report the final MP4 path and QA status, and keep manifest JSON, cut-plan JSON, alignment JSON when available, attribution JSON, post-render QA JSON, and contact sheet alongside it.
