# jiankoubo-skill

`jiankoubo-skill` is a Codex skill for turning talking-head videos and scripts into finished MP4 files locally.

It is built for a very specific workflow:

- take one or more local talking-head videos
- align them against a target script
- cut pauses and stutters at word level
- rebuild subtitles and emphasis cues
- add highlights, BGM, and sound effects
- render a final short-video deliverable with Remotion

This repository only keeps the skill itself.

## What It Does

The skill is designed for creator-style talking-head editing, especially Chinese 口播 workflows where sentence-level cutting is not enough.

Core capabilities:

- Volcengine ATA first, FunASR fallback alignment
- word-level pause and stutter cutting
- clean video generation with ffmpeg
- manifest-based Remotion rendering
- subtitle, flower-text, and semantic emphasis planning
- local curated BGM and SFX support
- post-render QA and sidecar metadata output

## Structure

```text
.
├── SKILL.md
├── README.md
├── .gitignore
├── agents/
│   └── openai.yaml
├── references/
│   ├── agent-runbook.md
│   ├── alignment-options.md
│   ├── asset-providers.md
│   ├── dependencies.md
│   ├── highlight-planning.md
│   ├── pipeline.md
│   ├── remotion-manifest.md
│   └── volcengine-alignment.md
├── scripts/
│   ├── apply_cut_plan.py
│   ├── build_manifest.py
│   ├── cut_planner.py
│   ├── export_attribution.py
│   ├── funasr_align.py
│   ├── manifest_to_ass.py
│   ├── post_render_check.py
│   ├── prepare_alignment_for_cuts.py
│   ├── prepare_remotion_project.py
│   ├── probe_media.py
│   ├── select_script_span.py
│   ├── validate_manifest.py
│   └── volcengine_align.py
└── assets/
    ├── audio/
    └── remotion-template/
```

## Key Inputs

The skill expects:

- a local video path
- the target script text you want to keep

Without both, the full render workflow should not start.

## Main Workflow

1. Probe source media with `ffprobe`
2. Run alignment with Volcengine ATA first
3. Build word-level timing data
4. Plan and apply pause/stutter cuts
5. Rebuild subtitle and highlight timing
6. Generate a render manifest
7. Render final MP4 with the bundled Remotion template
8. Run post-render QA

## Dependencies

Required local tools:

- `ffmpeg`
- `ffprobe`
- `python3`
- `node`
- `npm`

Optional but recommended:

- Volcengine ATA credentials
- OpenCV for richer post-render QA

See [references/dependencies.md](/Users/gaoan/Documents/剪辑skill/references/dependencies.md) and [references/agent-runbook.md](/Users/gaoan/Documents/剪辑skill/references/agent-runbook.md) for operational details.

## Notes

- Credentials must stay in environment variables, not in repository files.
- Local run artifacts are intentionally ignored.
- This repository is meant to contain the reusable skill, not generated outputs.
