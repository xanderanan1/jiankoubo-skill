# LLM Highlight Planning

## Rule

Use an LLM as the primary keyword selector. Deterministic rules are only a fallback for obvious missed numbers, prices, rankings, certifications, warnings, and actions.

The LLM output should be a small JSON object. It must first infer the content domain from the script and footage context, then choose cross-domain semantic roles. Do not hard-code categories from the example video. A car talking-head, a phone review, a finance explainer, a food recommendation, a tutorial, and a personal story should all use the same semantic contract while choosing different tone, palette, variants, and density.

```json
{
  "creative_direction": {
    "domain": "consumer_product",
    "content_type": "talking_head_review",
    "tone": "confident / useful / product-launch",
    "visual_density": "medium"
  },
  "hook": {
    "text": "7万预算先看这个",
    "component": "hook_title",
    "variant": "punch_number",
    "layout": "top-center",
    "palette": "auto_yellow_black",
    "motion": {"preset": "hookSnap", "intensity": 0.8, "duration_ms": 420},
    "decorations": {"sweep_light": true, "corner_ticks": true}
  },
  "bgm_style": "tech_product",
  "key_phrases": [
    {
      "text": "7万块钱",
      "semantic_type": "number",
      "emphasis_level": 3,
      "render_mode": "flower",
      "component": "metric_card",
      "variant": "giant_number",
      "layout": "upper-right",
      "palette": "auto_yellow_black",
      "motion": {"preset": "impactZoom", "intensity": 0.9, "duration_ms": 380, "sfx": "number_pop"},
      "decorations": {"sweep_light": true, "progress_bar": true},
      "reason": "price point worth emphasizing"
    }
  ]
}
```

Allowed `semantic_type` values:

- `entity`: people, brands, products, places, named topics
- `number`: prices, discounts, quantities, percentages, time spans
- `benefit`: advantages, outcomes, value propositions
- `proof`: rankings, awards, certifications, official claims, data-backed trust
- `risk`: warnings, constraints, pitfalls, negative surprises
- `action`: steps, instructions, calls to action
- `emotion`: reactions, attitudes, surprise, punchlines

Keep plans concise: normally 3-6 highlights for a short vertical video. Prefer complete spoken phrases that can be found in word-level alignment.

Allowed `component` values:

- `metric_card`: numbers, prices, quantities, percentages, rankings, durations
- `spec_chip`: entities, product specs, named concepts, categories, roles
- `benefit_badge`: benefits, outcomes, positive claims, emotional beats
- `callout`: warnings, actions, process steps, things the viewer must notice
- `hook_title`: opening hook only

Allowed variants:

- `metric_card`: `dashboard_glow`, `minimal_clean`, `speedometer`, `giant_number`
- `spec_chip`: `white_label`, `dark_glass`, `neon_pill`, `stacked_specs`
- `benefit_badge`: `scanline_bar`, `left_ribbon`, `glow_label`
- `callout`: `arrow_pointer`, `bracket_focus`, `area_scan`
- `hook_title`: `product_launch`, `punch_number`, `editorial_clean`

Allowed layouts:

- `upper-right`, `upper-left`, `middle-right`, `middle-left`, `lower-right`, `lower-left`, `center`, `top-center`, `lower-third`

Allowed palettes:

- `semantic_auto`: default semantic color system
- `auto_yellow_black`: punchy commerce/product emphasis
- `clean_white_blue`: clean tutorial/business/productivity emphasis
- `neon_cyan_magenta`: tech, entertainment, energy
- `warning_red_black`: risk, warning, urgent contrast
- `fresh_green_dark`: health, lifestyle, benefit-led content
- `editorial_black_white`: documentary, serious commentary, minimal analysis

Allowed decorations:

- `scanline`, `sweep_light`, `corner_ticks`, `progress_bar`, `bracket_focus`, `dot_grid`, `underline`, `arrow`

Allowed motion object:

```json
{"preset": "impactZoom", "intensity": 0.8, "duration_ms": 420, "sfx": "number_pop"}
```

`preset` may be `numberBurst`, `stampIn`, `warningShake`, `slideSnap`, `softGlow`, `cardRise`, `popElastic`, `hookSnap`, `impactZoom`, `chipSlide`, `badgeSweep`, `scanReveal`, `ribbonSnap`, `bracketPop`, or `speedCount`. `intensity` is `0.2` to `1.4`; `duration_ms` is `160` to `900`.

Allowed `bgm_style` values:

- `tech_product`: product launches, tools, cars, devices, business explainers
- `lifestyle_light`: daily life, shopping, travel, food, friendly consumer content
- `knowledge_calm`: tutorials, explainers, analysis, education
- `risk_tension`: warnings, pitfalls, investigations, urgent reminders
- `emotional_inspiring`: stories, motivation, aspiration, reflective content

## Prompt Template

Use this structure when asking an LLM to plan highlights:

```text
You are planning visual keyword highlights and audio cues for a short talking-head video.

Return strict JSON only. Do not include markdown.

Script:
<script>

First infer the likely content domain and content type from the script. The example may be any domain; do not assume automotive unless the script itself says so.

Choose 3-6 key phrases that appear verbatim or nearly verbatim in the script.
Classify each phrase using only these semantic types:
entity, number, benefit, proof, risk, action, emotion.

Also choose one bgm_style from:
tech_product, lifestyle_light, knowledge_calm, risk_tension, emotional_inspiring.

Optionally include a short hook string for the first 1.35 seconds. Keep it under 16 Chinese characters when possible.

You may include emphasis_level 1-3:
1 = caption-only emphasis, 2 = stronger caption emphasis, 3 = flower text / card emphasis.

Output shape:
{
  "creative_direction": {"domain": "...", "content_type": "...", "tone": "...", "visual_density": "low|medium|high"},
  "hook": {"text": "...", "component": "hook_title", "variant": "...", "layout": "top-center", "palette": "...", "motion": {"preset": "hookSnap", "intensity": 0.8, "duration_ms": 420}, "decorations": {"sweep_light": true}},
  "bgm_style": "...",
  "key_phrases": [
    {"text": "...", "semantic_type": "...", "emphasis_level": 3, "render_mode": "flower", "component": "...", "variant": "...", "layout": "...", "palette": "...", "motion": {"preset": "...", "intensity": 0.8, "duration_ms": 420}, "decorations": {"sweep_light": true}, "reason": "..."}
  ]
}
```

Do not ask the LLM for visual positions or exact timestamps unless the alignment step has failed. `build_manifest.py` aligns phrases to word timings and assigns lanes.
Use `layout` only as a preferred placement; the renderer and manifest builder may normalize it to avoid subtitles and common lower UI overlays.

## Manifest Build

Pass the plan into the manifest builder:

```bash
python3 scripts/build_manifest.py \
  --clean-video clean.mp4 \
  --alignment alignment.json \
  --cut-plan cut-plan.json \
  --highlight-plan highlight-plan.json \
  --output manifest.json
```

The script aligns planned phrases to word timings, assigns `visual_style`, `render_mode`, `emphasis_level`, and `motion_preset`, selects BGM, adds keyword SFX at each highlight start, and creates an optional `packaging.hook`.

Default SFX mapping:

- `entity` -> ping / notification emphasis
- `number` -> pop / price emphasis
- `benefit` -> sparkle / positive lift
- `proof` -> chime / trust signal
- `risk` -> snap / warning emphasis
- `action` -> click / action tick
- `emotion` -> boop / playful reaction

The curated Pixabay index supplies public-relative processed assets when available. The generated local SFX files are fallback assets.
