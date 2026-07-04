# Remotion Render Manifest

## Purpose

The preprocessing layer writes a JSON manifest. Remotion reads the manifest and renders without calling external APIs.

## Minimal Schema

```json
{
  "version": 1,
  "output": {
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "duration_ms": 30000
  },
  "video": {
    "path": "clean.mp4",
    "start_ms": 0
  },
  "subtitles": [
    {
      "text": "字幕",
      "start_ms": 0,
      "end_ms": 1800
    }
  ],
  "visual_events": [
    {
      "type": "key_phrase",
      "text": "重点",
      "start_ms": 1200,
      "end_ms": 3000,
      "semantic_type": "benefit",
      "visual_style": "benefit_glow",
      "style": "benefit_glow",
      "render_mode": "flower",
      "emphasis_level": 3,
      "motion_preset": "softGlow"
    }
  ],
  "packaging": {
    "hook": {
      "enabled": true,
      "text": "开场钩子",
      "start_ms": 0,
      "end_ms": 1350,
      "semantic_type": "benefit",
      "visual_style": "benefit_glow",
      "emphasis_level": 3,
      "motion_preset": "hookSnap"
    }
  },
  "audio": {
    "bgm": {
      "path": "/absolute/path/to/bgm.mp3",
      "volume": 0.18,
      "start_ms": 0,
      "end_ms": 30000
    },
    "sfx": [
      {
        "path": "/absolute/path/to/pop.wav",
        "start_ms": 1200,
        "volume": 0.6,
        "semantic_type": "number",
        "for_text": "重点数字"
      }
    ]
  },
  "theme": "notion",
  "attribution": []
}
```

## Rules

- Use public-relative paths for Remotion `staticFile()` assets when rendering from the starter template.
- Keep absolute source paths in preprocessing metadata when needed, but do not pass absolute paths to `staticFile()`.
- Clamp all events to `[0, duration_ms]`.
- Keep Remotion deterministic; do not fetch remote assets during render.
- Store license and attribution metadata in `attribution`.
- For flower text/highlights, classify keywords by general semantic function, not by video domain:
  `entity`, `number`, `benefit`, `proof`, `risk`, `action`, or `emotion`.
- Map semantic types to reusable visual components with `visual_style`. Keep `style` as a compatibility alias when useful.
- Default mapping: `entity_title`, `number_burst`, `benefit_glow`, `proof_underline`, `risk_alert`, `action_arrow`, `emotion_pop`.
- Treat subtitles, flower text, and the opening hook as one emphasis system:
  - `emphasis_level: 1` or `2` may render inline through caption highlighting.
  - `emphasis_level: 3` normally renders as flower text.
  - `render_mode` can explicitly choose `caption` or `flower`.
  - Caption highlighting only uses `render_mode: caption`; `render_mode: flower` stays in the flower/card layer to avoid duplicate emphasis.
- Supported motion presets use GSAP-like timing ideas but are implemented with deterministic Remotion frame math:
  `cardRise`, `numberBurst`, `softGlow`, `stampIn`, `warningShake`, `slideSnap`, `popElastic`, `underlineSweep`, `hookSnap`.
- `packaging.hook` is optional. When enabled, the starter template renders it as the opening hook layer and reuses the same semantic colors and motion language as flower text.
- Flower text size and decorative details scale from the output short side. `1080` keeps the base size; higher-resolution outputs scale up automatically.
- Keyword SFX should start at the same timestamp as the corresponding visual event unless a deliberate offset is specified.
- The starter template applies a 1.5x playback boost to SFX manifest volumes and caps the rendered value at `1.0`.
- The starter template includes local generated SFX under `public/sfx/`; use manifest paths such as `sfx/number_pop.wav` when rendering through Remotion `staticFile()`.
- When the curated Pixabay library is available, use public-relative paths such as
  `audio/pixabay/sfx/number_pop_pixabay.wav` and
  `audio/pixabay/bgm/tech_product_corporate_upbeat.mp3`.
- Store all Pixabay source metadata in `attribution`, even when attribution is not required.

## Starter Template Command

Prefer `scripts/prepare_remotion_project.py` instead of manually copying the template. It rewrites absolute video paths to public-relative paths and verifies audio assets:

```bash
python3 scripts/prepare_remotion_project.py \
  --manifest work/manifest.json \
  --video work/clean.mp4 \
  --project-dir work/remotion-project \
  --overwrite
```

Then render:

```bash
cd work/remotion-project
npm install
npx remotion render src/index.tsx TalkingVideo out/final.mp4 --props manifest.json --overwrite
```

The starter template passes `manifest.json` through Remotion props:

```bash
remotion render src/index.tsx TalkingVideo out/final.mp4 --props manifest.json
```
