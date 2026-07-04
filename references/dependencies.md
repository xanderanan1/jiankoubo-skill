# Dependencies

Use this list before running the skill on a new machine or handing it to another agent.

## Required System Binaries

- `python3`: runs preprocessing, manifest, project preparation, and attribution scripts.
- `ffmpeg`: applies cuts, extracts frames when needed, and analyzes audio for cut planning.
- `ffprobe`: probes media metadata before rendering.
- `node`: runs the Remotion toolchain.
- `npm`: installs Remotion template dependencies.

## Python Dependencies

Most bundled Python scripts use only the Python standard library:

- `argparse`
- `json`
- `pathlib`
- `re`
- `shutil`
- `subprocess`
- `dataclasses`
- `typing`

No `pip install` step is required for the deterministic preprocessing/render helper scripts.

Runtime-installed post-render visual QA dependency:

- `opencv-python` enables sampled frame extraction, debug-frame drawing, contact-sheet generation, and automatic face occlusion checks in `scripts/post_render_check.py`. Non-face key subjects such as products, screens, food, or logos can be protected with explicit `--focus-box` regions.
- `scripts/post_render_check.py` automatically installs `opencv-python` with the current Python interpreter when `cv2` is missing. Use `--no-auto-install-opencv` only when the machine must not install Python packages.
- If automatic installation fails because pip/network/build access is unavailable, the skill can still render, but post-render QA is degraded to manifest/layout checks and should be followed by a manual frame review. The JSON report records `opencv_auto_install_attempted` and `opencv_install_error`.

Manual equivalent of the automatic install:

```bash
python3 -m pip install -U opencv-python
```

Default API alignment:

- Volcengine ATA automatic subtitle alignment.
- Current-run environment variables: `VOLCENGINE_ATA_APPID`, `VOLCENGINE_ATA_TOKEN`.
- User-provided credentials may be passed with `--appid` and `--token`; the script stores them only in the current process environment.

Optional local alignment fallback:

- `funasr`, `modelscope`, and `soundfile` for Chinese ASR / forced alignment
- `openai-whisper` or another local Whisper-compatible package
- `faster-whisper` is acceptable when installed locally and able to produce usable timestamps

Install FunASR when local Chinese alignment is required:

```bash
python3 -m pip install -U funasr modelscope soundfile
```

Install Whisper only when Volcengine/FunASR are unavailable or the user explicitly asks for it:

```bash
python3 -m pip install -U openai-whisper
```

or:

```bash
python3 -m pip install -U faster-whisper
```

Whisper fallback quality depends on model choice and whether word timestamps are available. Prefer Volcengine ATA for Chinese口播, with FunASR as the local fallback.

## NPM Dependencies

Declared in `assets/remotion-template/package.json`:

```json
{
  "dependencies": {
    "@remotion/cli": "^4.0.0",
    "remotion": "^4.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "typescript": "^5.0.0"
  }
}
```

Install them inside the prepared Remotion project:

```bash
npm install
```

Remotion may download a compatible headless Chrome shell on first render.

## External Services

The default Chinese口播 path requires Volcengine ATA credentials for API alignment. Do not store credentials in project files; use current-run environment variables or per-command arguments.

Fallback when Volcengine ATA is not available:

- local FunASR transcription/alignment
- local Whisper transcription/alignment as a last resort

Optional:

- LLM access for semantic highlight planning.
- Freesound/Openverse/Jamendo providers for future asset expansion.

## Bundled Runtime Assets

The skill includes:

- `assets/remotion-template/`: Remotion renderer template.
- `assets/audio/pixabay/index.json`: curated Pixabay asset index.
- `assets/audio/pixabay/sfx/processed/*.wav`: short keyword SFX.
- `assets/audio/pixabay/bgm/*.mp3`: curated BGM presets.

When copying the Remotion template manually, ensure the audio files are available under `public/audio/pixabay/...`. Prefer `scripts/prepare_remotion_project.py`, which copies the template and validates public audio asset paths.

## Version Notes

- The MVP has been verified with Remotion 4.x.
- Keep generated `node_modules/`, `package-lock.json`, rendered MP4s, and run directories outside the reusable skill package unless intentionally shipping an example bundle.
