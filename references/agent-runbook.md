# Agent Runbook

Use this runbook when another agent needs to reproduce the MVP effect from a local talking-head video.

## Required Inputs

- Source video path.
- Target script text: the spoken section the user wants to keep. It may be only a subset of the full source video.
- Optional user preference: `aggressive`, `standard`, or `conservative` cut pacing.

Video and target script are mandatory. If either is missing, ask for it before starting the render flow.

After both are present, use Volcengine ATA first for Chinese口播 alignment. If the user provides `appid` and `access token` in the conversation, export them into the current run environment and do not write them to disk. Use FunASR only when the user explicitly accepts the local fallback. See `references/alignment-options.md`.

## Output Contract

Each run should produce:

- final MP4
- raw alignment JSON
- cut-plan JSON
- highlight-plan JSON
- render manifest JSON
- attribution JSON
- post-render-check JSON
- post-render-check contact sheet and sampled debug frames

Use one run directory per source video.

## Minimal Command Sequence

Set these paths first:

```bash
SKILL=/Users/gaoan/.codex/skills/render-talking-video
RUN=/path/to/run-dir
VIDEO=/path/to/source.mp4
FULL_ALIGNMENT=$RUN/full-alignment.json
ALIGNMENT=$RUN/selected-alignment.json
SCRIPT_TEXT=/path/to/script.txt
```

Probe the video:

```bash
python3 "$SKILL/scripts/probe_media.py" "$VIDEO" > "$RUN/probe.json"
```

If the user has just provided Volcengine credentials, make them available to this run without persisting them:

```bash
export VOLCENGINE_ATA_APPID="..."
export VOLCENGINE_ATA_TOKEN="..."
```

If alignment is not already available, obtain word-level alignment from Volcengine ATA and save the normalized result to `$FULL_ALIGNMENT`:

```bash
python3 "$SKILL/scripts/volcengine_align.py" "$VIDEO" \
  --script-file "$SCRIPT_TEXT" \
  --output "$FULL_ALIGNMENT" \
  --raw-output "$RUN/volcengine-raw.json" \
  --submit-output "$RUN/volcengine-submit.json" \
  --work-dir "$RUN"
```

When credentials cannot be inherited by the shell/tool call, pass them only for this process:

```bash
python3 "$SKILL/scripts/volcengine_align.py" "$VIDEO" \
  --script-file "$SCRIPT_TEXT" \
  --appid "$VOLCENGINE_ATA_APPID" \
  --token "$VOLCENGINE_ATA_TOKEN" \
  --output "$FULL_ALIGNMENT" \
  --raw-output "$RUN/volcengine-raw.json" \
  --submit-output "$RUN/volcengine-submit.json" \
  --work-dir "$RUN"
```

Use FunASR only as an explicit fallback:

```bash
python3 "$SKILL/scripts/funasr_align.py" "$VIDEO" \
  --mode asr \
  --output "$FULL_ALIGNMENT" \
  --raw-output "$RUN/funasr-raw.json" \
  --work-dir "$RUN"
```

For audio already trimmed to the user's exact script, or when the script covers the whole source video, FunASR forced alignment can be used instead after fallback approval:

```bash
python3 "$SKILL/scripts/funasr_align.py" "$VIDEO" \
  --mode force-align \
  --script-file "$SCRIPT_TEXT" \
  --output "$FULL_ALIGNMENT" \
  --raw-output "$RUN/funasr-fa-raw.json" \
  --work-dir "$RUN"
```

If Volcengine credentials are missing, ask the user for the appid and access token. After the user provides them, export them for the current run. If Volcengine fails and the user does not want fallback, stop and keep any intermediate files. If FunASR is not installed and the user does not want to install it, use local Whisper fallback only after explicit approval and normalize its output to the same `utterances[].words[]` shape. If word-level timings are unavailable, stop and explain that precision gas-mouth/stutter cutting requires word timings unless the user accepts a degraded rough cut.

Prepare the alignment for cut planning. Volcengine ATA output is already provider-aligned to the user's script, so it is used directly with a lightweight transcript guard. Full-video ASR fallbacks are sliced with script-span selection:

```bash
python3 "$SKILL/scripts/prepare_alignment_for_cuts.py" "$FULL_ALIGNMENT" \
  --script-file "$SCRIPT_TEXT" \
  --output "$ALIGNMENT" \
  --match-output "$RUN/script-match.json"
```

If the match/guard score is low, stop and report that the target script was not found confidently in the alignment. Ask for a closer transcript, a different source video, or a manually supplied alignment.

Plan cuts from words, not utterances:

```bash
python3 "$SKILL/scripts/cut_planner.py" "$ALIGNMENT" \
  --output "$RUN/cut-plan.json" \
  --duration-ms "$(python3 -c 'import json,sys;print(round(float(json.load(open(sys.argv[1]))["duration"])*1000))' "$RUN/probe.json")"
```

For conservative pacing, add `--min-pause-ms 600`. For aggressive short-video pacing, keep the default.

Apply cuts:

```bash
python3 "$SKILL/scripts/apply_cut_plan.py" "$VIDEO" "$RUN/cut-plan.json" "$RUN/clean.mp4"
```

Ask an LLM for `highlight-plan.json` using `references/highlight-planning.md`. The plan should choose 3-6 semantic highlights, an optional short opening hook, and, when useful, a `bgm_style`.

Build the Remotion manifest:

```bash
python3 "$SKILL/scripts/build_manifest.py" \
  --clean-video "$RUN/clean.mp4" \
  --alignment "$ALIGNMENT" \
  --cut-plan "$RUN/cut-plan.json" \
  --highlight-plan "$RUN/highlight-plan.json" \
  --output "$RUN/manifest.json"
```

Validate the manifest:

```bash
python3 "$SKILL/scripts/validate_manifest.py" "$RUN/manifest.json"
```

Prepare a renderable Remotion project. This copies the template, audio assets, and clean video into `public/`, then rewrites `video.path` to a public-relative path:

```bash
python3 "$SKILL/scripts/prepare_remotion_project.py" \
  --manifest "$RUN/manifest.json" \
  --video "$RUN/clean.mp4" \
  --project-dir "$RUN/remotion-project" \
  --overwrite
```

Render:

```bash
cd "$RUN/remotion-project"
npm install
node node_modules/@remotion/cli/remotion-cli.js render src/index.tsx TalkingVideo "$RUN/final.mp4" --props manifest.json --overwrite
```

Export attribution:

```bash
python3 "$SKILL/scripts/export_attribution.py" "$RUN/remotion-project/manifest.json" \
  --output "$RUN/attribution.json"
```

Run post-render visual QA:

```bash
python3 "$SKILL/scripts/post_render_check.py" \
  --video "$RUN/final.mp4" \
  --manifest "$RUN/remotion-project/manifest.json" \
  --output "$RUN/post-render-check.json" \
  --frames-dir "$RUN/post-render-check-frames" \
  --contact-sheet "$RUN/post-render-check.png"
```

This command automatically installs `opencv-python` through the current Python interpreter when `cv2` is missing. If package installation is not allowed on the machine, add `--no-auto-install-opencv`; QA will then run in degraded layout-only mode and the report will include the OpenCV import/install status.

For non-face-led videos or product demos, add one or more protected key visual regions. Coordinates may be normalized `0..1` or pixels:

```bash
python3 "$SKILL/scripts/post_render_check.py" \
  --video "$RUN/final.mp4" \
  --manifest "$RUN/remotion-project/manifest.json" \
  --output "$RUN/post-render-check.json" \
  --focus-box "product:0.16,0.28,0.48,0.42"
```

If the command exits with `status: fail`, inspect the contact sheet and sampled debug frames before handing back the render. Fix the director plan, component `layout`, component `variant`, subtitle safe-area position, or render template geometry, then rerender and rerun QA. If the command returns `status: warn`, report the warning and use the contact sheet to decide whether a rerender is needed. Common warnings include missing OpenCV face detection or no frontal face detected in a sampled frame.

## LLM Planning Rules

- Prefer LLM-selected semantic keywords over deterministic rules.
- Do not use domain-specific keyword classes such as car model, price, or safety as primary types.
- Allowed semantic types: `entity`, `number`, `benefit`, `proof`, `risk`, `action`, `emotion`.
- Prefer phrases that appear verbatim in the alignment words.
- Keep highlight count low enough to avoid overlapping flower text.
- Use `bgm_style` when the script clearly suggests one of the curated styles.

## Visual Defaults

- Subtitles have no translucent background and no punctuation.
- Subtitle text is smaller than the flower text and can highlight active key phrases inline.
- Flower text, inline subtitle emphasis, and the opening hook share one semantic emphasis system.
- Flower text positions are independent from subtitle line count.
- Flower text scales from the video short side, so 2K/4K renders keep the same visual weight as 1080p outputs.
- Reusable flower-text styles map to semantic types rather than the sample video's industry.
- GSAP-like motion presets are implemented with deterministic Remotion frame math, not runtime GSAP timelines.
- Every finished render must run post-render visual QA. The QA samples hook, flower-text, and subtitle timings; estimates the rendered boxes from manifest layout metadata; detects component-to-component overlap; checks subtitle safe area and lower platform overlay band; uses OpenCV face detection when available to flag obvious face occlusion; and can protect manually supplied `--focus-box` regions for products, screens, food, logos, or other key visual elements. Treat it as a guardrail, then use the generated contact sheet for final human judgment.

## Audio Defaults

- Keyword SFX start at `visual_events[].start_ms`.
- The starter Remotion template boosts keyword SFX playback volume by 50%, capped at `1.0`.
- Use the curated Pixabay index first when available.
- Use low BGM volume, normally `0.10` to `0.13`.
- Preserve attribution metadata even when attribution is not required.

## Failure Recovery

- If Volcengine/FunASR or any supplied alignment lacks word timings, skip precision gas-mouth cuts and report the limitation.
- If the LLM plan fails, `build_manifest.py` falls back to deterministic keyword candidates.
- If Pixabay assets are missing, use `--no-pixabay-assets` to fall back to generated local SFX.
- If BGM feels distracting, rebuild with `--no-bgm`.
- If Remotion rejects an absolute video path, rerun `prepare_remotion_project.py` and render from its rewritten manifest.
- If post-render QA fails because visual components overlap or block faces/key subjects, adjust `layout`, `variant`, `emphasis_level`, or the director plan and rerender. Do not simply ignore a `fail` report.

## Completion

After the Remotion render command and post-render QA finish successfully, hand back the final MP4 path and QA status. Preserve the manifest, cut plan, alignment payload when available, highlight plan, attribution JSON, post-render-check JSON, contact sheet, and sampled debug frames in the run directory for traceability and future edits.
