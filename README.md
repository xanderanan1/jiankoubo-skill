# jiankoubo-skill

## 中文

`jiankoubo-skill` 是一个用于本地生成口播成片的 Codex skill。

它解决的是一条非常具体的工作流：

- 输入一个或多个本地口播视频
- 输入目标文案
- 做词级对齐
- 裁掉停顿和卡壳
- 重建字幕和重点信息
- 补充花字、BGM、音效
- 用 Remotion 渲染最终 MP4

这个仓库只保留 skill 本体，不包含过程文档、运行产物或临时调试文件。

### 效果展示

- 演示视频，[demo/jiankoubo-demo.mp4](demo/jiankoubo-demo.mp4)

### 功能概览

这个 skill 主要面向创作者口播剪辑场景，尤其适合中文口播，因为很多停顿和卡壳发生在句子内部，句子级处理不够细。

核心能力包括：

- 优先使用火山 ATA 对齐，FunASR 作为回退方案
- 基于词级时间戳做气口和卡壳剪辑
- 用 ffmpeg 生成 clean video
- 基于 manifest 的 Remotion 渲染
- 字幕、花字、语义高亮规划
- 本地整理的 BGM 和音效素材
- 渲染后的 QA 检查和 sidecar 元数据输出

### 目录结构

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

### 关键输入

运行这个 skill 至少需要两样东西：

- 本地视频路径
- 你希望保留的目标文案

如果缺少其中任意一个，就不应该启动完整渲染流程。

### 主流程

1. 用 `ffprobe` 探测视频信息
2. 优先使用 Volcengine ATA 做对齐
3. 构建词级时间线
4. 规划并执行停顿 / 卡壳剪辑
5. 重建字幕和高亮时间信息
6. 生成 render manifest
7. 用内置 Remotion 模板渲染 MP4
8. 执行 post-render QA

### 依赖

必需的本地工具：

- `ffmpeg`
- `ffprobe`
- `python3`
- `node`
- `npm`

推荐但非强制：

- Volcengine ATA 鉴权
- OpenCV，用于更完整的 post-render QA

更详细的运行说明见：

- `references/dependencies.md`
- `references/agent-runbook.md`

### 说明

- 所有鉴权信息都应保存在环境变量中，不能写进仓库文件
- 本地运行产物已通过 `.gitignore` 排除
- 这个仓库的目标是保留可复用的 skill，而不是保存生成结果

---

## English

`jiankoubo-skill` is a Codex skill for producing finished talking-head videos locally.

It is built around a very specific workflow:

- take one or more local talking-head videos
- provide the target script text
- perform word-level alignment
- cut pauses and stutters
- rebuild subtitles and emphasis timing
- add highlights, BGM, and sound effects
- render the final MP4 with Remotion

This repository only keeps the skill itself. It does not include process notes, run outputs, or temporary debugging artifacts.

### Demo

- Demo video, [demo/jiankoubo-demo.mp4](demo/jiankoubo-demo.mp4)

### Overview

The skill is designed for creator-style talking-head editing, especially for Chinese spoken-video workflows where sentence-level cutting is not precise enough.

Core capabilities:

- Volcengine ATA first, FunASR fallback
- word-level pause and stutter cutting
- clean video generation with ffmpeg
- manifest-based Remotion rendering
- subtitle, flower-text, and semantic emphasis planning
- curated local BGM and sound-effect assets
- post-render QA and sidecar metadata output

### Repository Structure

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

### Required Inputs

The skill expects at least:

- a local video path
- the target script text to keep

Without both, the full render workflow should not start.

### Main Workflow

1. Probe media with `ffprobe`
2. Run alignment with Volcengine ATA first
3. Build word-level timing data
4. Plan and apply pause / stutter cuts
5. Rebuild subtitle and emphasis timing
6. Generate a render manifest
7. Render the final MP4 with the bundled Remotion template
8. Run post-render QA

### Dependencies

Required local tools:

- `ffmpeg`
- `ffprobe`
- `python3`
- `node`
- `npm`

Optional but recommended:

- Volcengine ATA credentials
- OpenCV for richer post-render QA

For operational details, see:

- `references/dependencies.md`
- `references/agent-runbook.md`

### Notes

- Credentials must stay in environment variables, never in repository files
- Local run artifacts are intentionally ignored by `.gitignore`
- This repository is meant to preserve the reusable skill, not generated outputs
