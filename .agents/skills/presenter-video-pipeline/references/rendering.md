# Rendering reference (Remotion)

## Render flow

1. Install Remotion dependencies: `cd video-studio && npm ci`, then return to the repository root.
2. Render a job: `python .agents/skills/presenter-video-pipeline/scripts/render.py jobs/<slug> [--format landscape|portrait|both] [--preview]`.
3. Outputs go to `jobs/<slug>/out/`.

## Options

- `--format landscape|portrait|both` — output orientation(s).
- `--preview` — quick preview render.
- `--allow-missing` — render placeholders before HeyGen clips exist.
- `--props-only` — write render props without rendering.

## Real workflow (presenter + narration)

`render.py` uses Remotion and mutes the presenter video track while playing the separate narration audio. The presenter video (`jobs/<slug>/presenter/<id>.mp4`) and narration audio (`jobs/<slug>/audio/<id>.mp3`, imported via `tts.py --import`) are combined at render time.

## Approval and charges

Rendering itself is local, but the presenter video it consumes is billable via HeyGen. Get explicit approval before generating the presenter video. Setup and synthetic tests never call HeyGen.
