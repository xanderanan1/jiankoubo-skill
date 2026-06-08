# Local Talking-Head Video Skill Implementation Plan

## Skill Location

Create the discoverable skill at:

`/Users/gaoan/.codex/skills/render-talking-video`

Use the current repository for design and implementation notes.

## Milestones

1. Scaffold the skill with `SKILL.md`, `agents/openai.yaml`, `scripts/`, `references/`, and `assets/`.
2. Add concise skill instructions that tell Codex when to use the skill and how to run the bundled pipeline.
3. Add reference docs for:
   - local video pipeline
   - Volcengine word-level alignment
   - BGM and sound-effect providers
   - Remotion manifest schema
4. Add Python scripts for deterministic preprocessing:
   - media probing
   - word timeline normalization
   - pause and stutter candidate detection
   - keep segment generation
   - render manifest validation
5. Add a minimal Remotion template asset that can consume the render manifest.
6. Validate the skill with `quick_validate.py`.
7. Run representative script tests on synthetic timing data.

## First Build Scope

The first build should be a usable skill foundation, not a full production renderer.

Include:

- A clear workflow for local talking-head MP4 creation.
- A robust word-level cut planner that can be tested without external APIs.
- Manifest schema and validation.
- A Remotion starter template with simple subtitle and highlight composition.
- Provider guidance for local assets, Freesound, and Openverse.

Defer:

- Live Volcengine API client implementation if credentials are unavailable.
- Full Remotion dependency installation.
- Complex sticker libraries.
- Commercial music integrations.
- Database or content-management features.

## Validation

Run:

- Skill metadata validation.
- Python unit-style checks for pause detection and keep segment generation.
- JSON manifest validation on a tiny synthetic example.

