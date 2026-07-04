# BGM and Sound-Effect Providers

## Provider Interface

Each provider should return:

```json
{
  "id": "provider-specific-id",
  "kind": "bgm",
  "title": "Asset title",
  "creator": "Creator name",
  "source": "local|freesound|openverse|pixabay|jamendo",
  "source_url": "https://example.com",
  "download_url": "https://example.com/file.mp3",
  "preview_url": "https://example.com/preview.mp3",
  "duration_ms": 120000,
  "license": "CC0",
  "requires_attribution": false,
  "attribution_text": "",
  "tags": ["upbeat", "short-video"]
}
```

## Recommended MVP Sources

- Local library: use first for repeatable production renders.
- Freesound: strong for SFX; filter by license and duration.
- Openverse: broad Creative Commons audio discovery.
- Curated Pixabay library: use downloaded, indexed assets from `assets/audio/pixabay/index.json` when present.

## Optional Later Sources

- Jamendo: music discovery, subject to track-specific licensing.
- User-provided commercial libraries.

## Safety Rules

- Never use assets with unknown license.
- Prefer commercial-safe assets when user intent is unclear.
- Write attribution metadata for every used asset.
- Allow `--no-external-assets` to force local-only rendering.
- Do not assume "free download" means unlimited commercial use.

## Practical Defaults

For sound effects:

- Prefer the curated Pixabay SFX index when present. It maps the general semantic roles to short processed WAV files:
  `entity`, `number`, `benefit`, `proof`, `risk`, `action`, `emotion`.
- Fall back to local generated keyword SFX when the Pixabay index is missing or `--no-pixabay-assets` is set:
  `entity_ping`, `number_pop`, `benefit_spark`, `proof_chime`, `risk_snap`, `action_tick`, `emotion_boop`.
- Prefer clips under 4 seconds.
- For keyword emphasis, prefer clips under 200 ms.
- Normalize volume before mixing.
- Avoid overly loud UI or meme sounds unless the style preset asks for them.

For BGM:

- Prefer the curated Pixabay BGM index when present.
- Supported default styles: `tech_product`, `lifestyle_light`, `knowledge_calm`, `risk_tension`, `emotional_inspiring`.
- Let the LLM plan provide `bgm_style` when possible. Otherwise infer from the script text.
- Use `--bgm-style <style>` to force a style, or `--no-bgm` for a clean speech-only render.
- Prefer loopable music.
- Duck under speech.
- Fade in/out at segment boundaries.
