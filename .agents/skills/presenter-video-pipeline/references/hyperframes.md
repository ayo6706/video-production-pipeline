# HyperFrames project format and rendering

The pipeline keeps spoken-story data in `segments.json` and visual timing in `STORYBOARD.md`. A voiceover segment may span several visual frames; changing a visual beat does not require changing narration segmentation.

## Job layout

```text
jobs/<slug>/
├── segments.json
├── STORYBOARD.md
├── index.html                 # root composition
├── audio/                     # generated/imported narration + manifest.json
├── assets/                    # licensed images, fonts, footage, and other media
├── compositions/frames/       # one HTML composition per storyboard frame
└── out/                       # ignored render and QA outputs
```

`new-video.py` creates a HyperFrames root scaffold with a 30-second canvas and a 3-second `hook` mount. The new storyboard is deliberately `outline`; replace the plan with finished compositions before running the render-ready check.

## Root composition

Use one root element with `data-composition-id="main"`, `data-start="0"`, `data-duration`, `data-width`, `data-height`, and `data-no-timeline`. Mount each storyboard frame with a unique `id`, `data-composition-id`, `data-composition-src`, `data-start`, `data-duration`, and matching canvas dimensions. Visual mounts typically use track index `1`; audio uses track index `0`.

The narration insertion point is exactly one comment inside the root element:

```html
<!-- HYPERFRAMES_NARRATION_AUDIO -->
```

For narrated jobs the renderer replaces this marker only in a temporary build workspace. It creates timed `<audio>` clips from the current `audio/manifest.json`, validates text/settings hashes and file paths, and leaves the job's `index.html` unchanged. Silent jobs may keep or omit the marker. Narration must fit within the storyboard duration; stale manifests, missing audio, unsafe paths, or an absent/duplicate marker block rendering.

All local media should live below `assets/` or `audio/`. Composition files should live below `compositions/`. The runner copies the root HTML and small root-level CSS/JS modules and links these three directories into a temporary project. Put any additional project files in the supported directories or extend the workspace adapter deliberately.

## Validate, review, render

```bash
python .agents/skills/presenter-video-pipeline/scripts/storyboard_check.py jobs/<slug> --require-ready
python .agents/skills/presenter-video-pipeline/scripts/render.py jobs/<slug> --preview
```

The HyperFrames runner executes lint, browser/layout/motion/contrast checks, and review snapshot generation before rendering a draft. It persists JSON reports and review artifacts under ignored output directories, then uses `ffprobe` to verify the produced file, canvas dimensions, duration, and narration stream where applicable. Inspect the preview and review snapshots yourself. Only then use `--approved` for a delivery render.

For CLI schema and runtime details, see the [HyperFrames CLI guide](https://hyperframes.heygen.com/developers/cli), [HTML schema](https://hyperframes.heygen.com/reference/html-schema), and [compositions guide](https://hyperframes.heygen.com/concepts/compositions).
