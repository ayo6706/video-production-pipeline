# presenter-video-pipeline

Evidence-led short-form video production with independent visual timing. New editorial jobs use HyperFrames; the Remotion renderer remains available for compatible legacy jobs. Provider-specific narration and avatar generation are optional, require the user's own authorized accounts, and are not used by local tests or CI.

## Repository layout

```
.agents/skills/presenter-video-pipeline/   # this skill (pipeline + scripts)
  SKILL.md                                  # this file
  pipeline.config.json                      # configurable paths, timing, credit budget, TTS pricing
  references/                               # generic workflow and provider references
    content-visual-planning.md              # evidence-led story and visual-beat planning
    voice.md                                # optional voice/TTS providers and workflow
    heygen.md                               # optional HeyGen MCP narration/avatar workflow
    segment-plan.md                         # segments.json, claims, source_ref citations
    hyperframes.md                          # HyperFrames project and rendering workflow
    rendering.md                            # render flow and narration mixing
    qa-disclosure.md                        # final QA, attribution, and rights checklist
  scripts/                                  # reusable Python scripts (standard library)
    _common.py                              # shared helpers
    new-video.py                            # scaffold a new HyperFrames or Remotion job
    storyboard_check.py                     # validate visual timing, refs, and composition mounts
    hyperframes_render.py                   # HyperFrames lint/check/review/render adapter
    editorial_review.py                     # phone-size editorial packet and hash-bound sign-off
    segment-check.py                        # validate narration and claims
    credit-budget.py                        # HeyGen credit estimate/log/status
    tts.py                                  # narration (HeyGen via MCP, or FAL Chatterbox)
    render.py                               # HyperFrames dispatch + Remotion legacy renderer
  tests/                                    # synthetic tests (no paid provider calls)
  personas/                                 # local persona templates (blank, gitignored when filled)
    persona.template.json
  lanes/                                    # content lane templates
    lane.template.md
video-studio/                               # Remotion starter (React + TypeScript)
README.md                                   # setup and use instructions
.gitignore                                  # local credentials and generated media are excluded
```

## Prerequisites

- Python 3.10+ (standard library only for the pipeline scripts)
- Node.js 22.12+ and npm for HyperFrames; `ffmpeg` and `ffprobe` for rendering and output verification
- Optional: a HeyGen account and an authorized MCP connection for narration/avatar workflows
- Optional: a FAL account and `FAL_KEY` environment variable for FAL Chatterbox narration

## How to use

### 1. Optional: connect HeyGen

Only needed for HeyGen narration/avatar steps; local planning, validation, examples, tests, and synthetic CI renders do not connect to or charge a provider.

Configure the HeyGen remote MCP server through your agent client's supported OAuth flow. For Hermes, the server URL is `https://mcp.heygen.com/mcp/v1/`; other clients should follow their own current setup instructions. Complete authorization on the host that runs the client. Do not share OAuth callback codes or credentials in chat or commit them to files.

### 2. Create or select your own avatar and voice

Choose an avatar look and voice that you own or are authorized to use. Use the HeyGen dashboard or installed MCP tools (such as `list_avatar_groups`, `list_avatar_looks`, and `list_voices`) to select them. `create_speech` synthesizes approved text with a selected voice; it does not create an avatar or voice. Create or clone assets only when you have the required rights and consent.

Fill your local persona settings:

1. Copy `personas/persona.template.json` to `personas/<your-id>/persona.json`.
2. Set `avatar.heygen_avatar_look_id` to your confirmed HeyGen avatar look ID.
3. Set `voice.heygen_voice_id` to your HeyGen voice ID (HeyGen provider), or configure `voice.fal` with your own reference clip at `voice/reference.wav` and set `FAL_KEY` (FAL provider).
4. Adjust `brand` colors/display name/handle to neutral values you choose.

Never commit `persona.json` with real IDs — it is gitignored and stays local.

### Plan the story and visuals before scaffolding

Before creating a job, use `references/content-visual-planning.md` to choose one viewer problem, verify factual claims, and write a concise claim ledger. Plan narration and visuals separately: one narration segment may span several independently timed storyboard frames. Use relevant product/source captures, concrete actions, diagrams, or purposeful motion graphics; avoid generic stock filler and slide-only sequences. Attribute estimates and preserve the source's qualifications.

The Remotion renderer supports only the scene kinds listed in `references/segment-plan.md`. HyperFrames uses HTML compositions described by `STORYBOARD.md`; do not imply unsupported Remotion scene effects are automatically converted.

### 3. Scaffold a new video job

```
python .agents/skills/presenter-video-pipeline/scripts/new-video.py <slug> \
    --persona <your-id> --lane <lane-id> --title "Your title"
```

New jobs default to HyperFrames; pass `--engine remotion` for a legacy-compatible job. The HyperFrames scaffold includes `segments.json`, `STORYBOARD.md`, a root `index.html` with a hook mount and narration marker, plus `audio/`, `assets/`, and `compositions/frames/`. Create each frame composition, set its storyboard status to `animated`, and keep root mounts and frame IDs/timing in sync before rendering. The scaffold is an outline, not a render-ready video.

### 4. Validate the plan

For narration-bearing jobs, run:

```
python .agents/skills/presenter-video-pipeline/scripts/segment-check.py jobs/<slug>
```

Every job, including silent visual-only jobs, must pass the storyboard check:

```
python .agents/skills/presenter-video-pipeline/scripts/storyboard_check.py jobs/<slug> --require-ready
```

The storyboard validator checks frame timing, source/segment references, project-relative media paths, required HyperFrames mounts, and render-ready status. A missing or unsupported composition blocks rendering.

### 5. Generate narration audio

HeyGen narration uses the installed MCP `create_speech` tool. First run `python .agents/skills/presenter-video-pipeline/scripts/tts.py jobs/<slug> --todo` to list the exact segments. After explicit approval for each synthesis call, create one audio file per approved segment and save it to `jobs/<slug>/audio/<id>.mp3`. Install Remotion dependencies if needed (`cd video-studio && npm ci`), return to the repository root, then run `python .agents/skills/presenter-video-pipeline/scripts/tts.py jobs/<slug> --import` to convert files and write the manifest.

FAL Chatterbox is optional. Set `FAL_KEY` with the Windows Environment Variables UI or a secret manager/OS environment UI; never put it in a command, chat, or committed file. Preview with `python .agents/skills/presenter-video-pipeline/scripts/tts.py jobs/<slug> --dry-run`. If the rate is `null`, a dry run reports cost as unknown and billable generation is blocked. Enter only a verified rate and obtain explicit approval for the exact segment set and cost before each invocation.

### 6. Estimate video credits and approve avatar generation

After narration audio has been generated, read the current balance with HeyGen `get_current_user` and estimate the presenter-video credits:

```
python .agents/skills/presenter-video-pipeline/scripts/credit-budget.py estimate jobs/<slug> --remaining <balance>
```

The rate and monthly allowance fields default to `null`. Configure only values verified for your plan; the estimator blocks if `credits_per_minute` is unset. This estimate covers avatar-video credits only, not speech synthesis. Get explicit approval before each billable tool call. Record the balance immediately before avatar-video calls, then log the change after they complete:

```
python .agents/skills/presenter-video-pipeline/scripts/credit-budget.py log jobs/<slug> --before <balance_before_video> --remaining <balance_after_video>
```

Capture the before balance after narration generation so speech usage is not mixed into the avatar-video estimate. Never retry a failed or timed-out call without asking.

### 7. Optional: generate presenter video for Remotion jobs

This avatar-video step is part of the compatible legacy Remotion path, not the HyperFrames audio-track adapter. After separate approval, lip-sync narration to the selected authorized avatar using the installed HeyGen MCP `create_video_from_avatar` tool. Inspect the installed schema for exact fields; use the narration URL returned by HeyGen or upload through the documented asset flow only with authorization. Save the completed video under the job's ignored presenter directory and poll `get_video` with its returned ID until complete. HyperFrames does not automatically convert presenter footage into a composition.

### 8. Preview, review, and render

For the default HyperFrames path:

```
python .agents/skills/presenter-video-pipeline/scripts/render.py jobs/<slug> --preview
```

Open `jobs/<slug>/out/editorial-review.html` and inspect the preview at phone size. Watch the entire video; check every frame for caption/source overlap, phone readability, completed actions, and story relevance. Listen end-to-end for audio timing and levels; review visual variety and restrained transitions. Record the checklist with:

```
python .agents/skills/presenter-video-pipeline/scripts/editorial_review.py jobs/<slug> --record
python .agents/skills/presenter-video-pipeline/scripts/editorial_review.py jobs/<slug> --check
```

The saved sign-off binds both preview SHA-256 and a fingerprint of the storyboard, all job files, active persona, and pinned pipeline/config inputs. HyperFrames renders from an isolated copy of local assets, audio, and compositions and verifies the copy; changed inputs invalidate sign-off or cause the in-flight output to be discarded. The workflow assumes the job is not concurrently edited while the workspace is being assembled; it is not an OS-level lock over every job file. Avoid edits during that phase, and create a fresh preview and review after source changes. The checklist is a human self-attestation: reviewer identity is not authenticated and the local JSON record is editable, not cryptographic proof of viewing. The fingerprint does not cover installed `node_modules` bytes, OS/browser/FFmpeg versions, or remote resources referenced by composition code. Bundle resources locally and keep the runtime unchanged between preview and delivery. A blocked render leaves any older delivery file untouched. Per-video review remains manual; a code/pipeline review is not editorial approval. Failed or missing checks block delivery through the normal workflow:

```
python .agents/skills/presenter-video-pipeline/scripts/render.py jobs/<slug> --approved
```

This editorial sign-off does not verify factual accuracy, rights, or permission to publish; those remain separate review gates.

For compatible legacy Remotion jobs, install the locked dependencies and select the engine explicitly:

```
npm ci --ignore-scripts --prefix video-studio --no-audit --no-fund
python .agents/skills/presenter-video-pipeline/scripts/render.py jobs/<slug> --engine remotion --format portrait [--preview]
```

Outputs and generated media stay under ignored job output directories. The HyperFrames path verifies canvas, duration, and the narration audio stream with `ffprobe`; provider/avatar operation requires separate approval and is not part of local rendering or CI.

## Generic references

See `.agents/skills/presenter-video-pipeline/references/`:

- `voice.md` — voice/TTS providers and the HeyGen narration flow
- `heygen.md` — HeyGen MCP setup, avatar/voice, presenter video flow
- `content-visual-planning.md` — evidence-led storytelling and visual beat planning
- `segment-plan.md` — segments.json, claims, source_ref citations, validation
- `hyperframes.md` — HyperFrames project, timing, and render workflow
- `rendering.md` — Remotion compatibility and narration mixing
- `qa-disclosure.md` — final QA checklist, disclosure and rights reminders

## Approval gates and charges

Explicit approval is required before each class of billable HeyGen call (narration audio `create_speech`, presenter video `create_video_from_avatar`). Setup, scaffolding, validation, and synthetic tests never call HeyGen and never incur charges.

## Privacy

- No credentials, API keys, real avatar/voice IDs, names, handles, or personal brand in committed files.
- No generated audio/video, voice samples, or avatar source images are committed.
- Each recipient configures only assets and likenesses they own or are authorized to use.
- Do not generate videos or incur charges as part of setup.
