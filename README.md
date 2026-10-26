# HeyGen + HyperFrames Video Production Pipeline (Remotion-compatible)

A reusable workflow for evidence-led scripts, independently timed visual storyboards, motion-graphics compositions, review, and export. New jobs use HyperFrames; existing Remotion jobs remain supported.

## What it includes

- A `segments.json` plan for narration and source-backed claims.
- A separate `STORYBOARD.md` plan for visual beats that can change independently of narration.
- A pinned HyperFrames CLI runtime, structural validation, automated checks, review snapshots, and verified renders.
- An optional HeyGen narration/avatar workflow with explicit approval before paid generation.
- A Remotion renderer for compatible legacy jobs.
- Synthetic examples and tests that do not call HeyGen or incur provider charges.

## Requirements

- Python 3.10 or later.
- Node.js 22.12 or later and npm for HyperFrames. The CLI version is pinned in `tools/hyperframes/package-lock.json`.
- `ffmpeg` and `ffprobe` for media rendering and output verification.
- Optional: a HeyGen account with an authorized MCP connection for narration or avatar video.
- Optional: a FAL account and `FAL_KEY` for the FAL Chatterbox voice provider.
- Legacy Remotion rendering also uses Node.js and the locked dependencies in `video-studio/`.

## Quick start: HyperFrames

Install the pinned local CLI and create a job:

```bash
npm ci --ignore-scripts --prefix tools/hyperframes --no-audit --no-fund
python .agents/skills/presenter-video-pipeline/scripts/new-video.py <slug> \
  --title "Your title" --format portrait
```

Fill in `jobs/<slug>/segments.json` with approved narration and source-backed claim records. Plan each visual beat in `jobs/<slug>/STORYBOARD.md`; give each frame an ID, start, duration, scene action, status, and composition path. The generator creates a root `index.html` with a placeholder hook mount and narration marker: create the matching frame composition and update root mounts to match the finished storyboard. Current narration audio is inserted from the manifest during a temporary render build, without modifying source HTML. Keep voiceover, source references, and on-screen text tied to the specific beat they support.

Validate the plan and render a preview:

```bash
python .agents/skills/presenter-video-pipeline/scripts/segment-check.py jobs/<slug>
python .agents/skills/presenter-video-pipeline/scripts/storyboard_check.py jobs/<slug> --require-ready
python .agents/skills/presenter-video-pipeline/scripts/render.py jobs/<slug> --preview
```

Open the review contact sheets listed in `jobs/<slug>/out/hyperframes-review.json`, inspect the preview at phone size, and resolve any QA findings. Then render the delivery file:

```bash
python .agents/skills/presenter-video-pipeline/scripts/render.py jobs/<slug> --approved
```

`--approved` is an explicit confirmation that a person inspected the preview and review frames. It does not bypass structural checks or automated QA. Outputs and review artifacts stay under the job's ignored `out/` and `.hyperframes/` directories.

The renderer does not silently fall back to Remotion. A missing CLI, invalid storyboard, failed HyperFrames check, or unverifiable output blocks the render with a diagnostic.

## Story and visual planning

Start with one viewer question, then make a claim ledger for factual statements. Keep each claim tied to a source or approved asset; preserve attribution, dates, units, scope, and uncertainty. Label illustrative examples as illustrative.

Plan the spoken story and visual sequence separately. A narration paragraph can continue across multiple shots. Use product captures, relevant footage, diagrams, animated typography, and purposeful motion graphics when they clarify the story. Do not default to a stack of title cards or unrelated stock footage. Reference material may guide abstract choices such as pacing, framing, and type hierarchy; do not copy distinctive scripts, jokes, compositions, identity, or assets.

For frame format, composition structure, and animation behavior, see [`references/hyperframes.md`](.agents/skills/presenter-video-pipeline/references/hyperframes.md) and the [HyperFrames CLI guide](https://hyperframes.heygen.com/developers/cli).

## Optional narration and avatar workflow

The project can use HeyGen `create_speech` for narration and `create_video_from_avatar` for an authorized presenter. It can also use FAL Chatterbox where configured. Provider access and generated media are optional; local planning, validation, tests, and synthetic examples do not call these services.

1. Configure your own local persona by copying `.agents/skills/presenter-video-pipeline/personas/persona.template.json` to `.agents/skills/presenter-video-pipeline/personas/<your-id>/persona.json`. Use only voice/avatar assets you own or are authorized to use. Persona directories with real settings are gitignored.
2. Review the narration and selected voice. Run `tts.py jobs/<slug> --todo` to inspect the exact text before generation.
3. Obtain explicit approval for each billable call, including the exact text, voice/avatar, and scope. Never retry a failed or timed-out paid call without approval.
4. Keep generated audio, avatar footage, source media, and credentials out of commits. Use the HeyGen tool schema and supported upload flow for the active account.

For FAL, keep `FAL_KEY` in a secure environment or secret manager, not in chat or a committed file. A dry run with an unknown rate blocks billable generation; configure only a verified current rate.

## Remotion compatibility

Jobs created before the HyperFrames path remain renderable through the existing Remotion renderer. Jobs without an `engine` field default to Remotion for compatibility. To select the legacy path explicitly:

```bash
npm ci --ignore-scripts --prefix video-studio --no-audit --no-fund
python .agents/skills/presenter-video-pipeline/scripts/render.py jobs/<slug> \
  --engine remotion --format portrait
```

Remotion consumes the supported `segments.json` scene schema and narration manifest; it does not consume the independent HyperFrames storyboard. HyperFrames-only compositions are not converted automatically.

## Development checks

```bash
python3 -m unittest discover -s .agents/skills/presenter-video-pipeline/tests -v
npm ci --ignore-scripts --prefix video-studio --no-audit --no-fund
npm --prefix video-studio run typecheck
npm ci --ignore-scripts --prefix tools/hyperframes --no-audit --no-fund
npm audit --prefix tools/hyperframes
npm audit --prefix video-studio
```

The GitHub Actions workflow runs a synthetic HyperFrames CLI render with system Chromium and FFmpeg in addition to the unit tests. A successful run of that smoke render is a release gate; mocked runner tests alone do not verify the browser/render environment.

## Privacy and rights

- Do not commit API keys, OAuth tokens, private account data, or real avatar/voice IDs.
- Do not commit generated audio/video, voice samples, avatar source images, or private working jobs.
- Use only assets and likenesses you own or have permission to use; check third-party license and attribution requirements.
- Keep source citations in production notes, captions, descriptions, or an end card rather than spoken copy unless requested.

## License

MIT. See [`LICENSE`](LICENSE).
