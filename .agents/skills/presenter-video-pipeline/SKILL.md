# presenter-video-pipeline

Generic HeyGen + Remotion presenter-video pipeline starter. It lets another creator
generate presenter videos with their own HeyGen avatar/voice and Remotion rendering
setup, without inheriting any personal or third-party profile, content lane,
examples, assets, or voice.

## Repository layout

```
.agents/skills/presenter-video-pipeline/   # this skill (pipeline + scripts)
  SKILL.md                                  # this file
  pipeline.config.json                      # configurable paths, timing, credit budget, TTS pricing
  references/                               # generic workflow references
    voice.md                                # voice/TTS providers and HeyGen narration flow
    heygen.md                               # HeyGen MCP setup, avatar/voice, presenter video flow
    segment-plan.md                         # segments.json, claims, source_ref citations
    rendering.md                            # Remotion render flow and presenter/narration mixing
    qa-disclosure.md                        # final QA checklist, disclosure and rights reminders
  scripts/                                  # reusable Python scripts (no external deps)
    _common.py                              # shared helpers
    new-video.py                            # scaffold a new video job
    segment-check.py                        # validate a segments plan
    credit-budget.py                        # HeyGen credit estimate/log/status
    tts.py                                  # narration (HeyGen via MCP, or FAL Chatterbox)
    render.py                               # render with Remotion
  tests/                                    # synthetic tests (no HeyGen, no charges)
  personas/                                 # local persona templates (blank, gitignored when filled)
    persona.template.json
  lanes/                                    # content lane templates
    lane.template.md
video-studio/                               # Remotion starter (React + TypeScript)
README.md                                   # setup and use instructions
.gitignore                                  # local credentials and generated media are excluded
```

## Prerequisites

- Python 3.10+ (standard library only; the pipeline scripts need no packages)
- Node.js 18+ and npm (for Remotion installation/rendering)
- A HeyGen account and access to the HeyGen remote MCP server
- Optional: a FAL account and `FAL_KEY` environment variable if you use the FAL Chatterbox voice provider

## How to use

### 1. Configure HeyGen MCP (OAuth)

Add the HeyGen remote MCP server on the agent host using OAuth:

```
hermes mcp add heygen --url https://mcp.heygen.com/mcp/v1/ --auth oauth
```

Then complete authorization on the MCP host when prompted, and reload/restart the agent host so the MCP server is picked up. OAuth is configured on the same host that runs the pipeline scripts. A callback opened on another computer or remote browser may not reach the local callback listener; complete it in a browser on the MCP host or follow the MCP client's documented callback-forwarding flow. Non-Hermes MCP clients should add the same remote server URL and use their own OAuth flow; exact setup is client-specific. Never share OAuth callback codes or secrets in chat, and never write credentials to a file.

### 2. Create or select your own avatar and voice

Choose an avatar look and voice that you own or are authorized to use. Use the HeyGen dashboard or installed MCP tools (such as `list_avatar_groups`, `list_avatar_looks`, and `list_voices`) to select them. `create_speech` synthesizes approved text with a selected voice; it does not create an avatar or voice. Create or clone assets only when you have the required rights and consent.

Fill your local persona settings:

1. Copy `personas/persona.template.json` to `personas/<your-id>/persona.json`.
2. Set `avatar.heygen_avatar_look_id` to your confirmed HeyGen avatar look ID.
3. Set `voice.heygen_voice_id` to your HeyGen voice ID (HeyGen provider), or configure `voice.fal` with your own reference clip at `voice/reference.wav` and set `FAL_KEY` (FAL provider).
4. Adjust `brand` colors/display name/handle to neutral values you choose.

Never commit `persona.json` with real IDs — it is gitignored and stays local.

### 3. Scaffold a new video job

```
python .agents/skills/presenter-video-pipeline/scripts/new-video.py <slug> \
    --persona <your-id> --lane <lane-id> --title "Your title"
```

This creates `jobs/<slug>/segments.json` from a generic template plus empty `audio/` and `assets/` directories. Fill in `segments.json` with your approved narration text and scenes.

### 4. Validate the plan

```
python .agents/skills/presenter-video-pipeline/scripts/segment-check.py jobs/<slug>
```

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

### 7. Generate presenter video (HeyGen)

After a separate approval, lip-sync the narration to the selected avatar with the installed HeyGen MCP `create_video_from_avatar` tool. Use the narration audio URL returned by HeyGen `create_speech` and the locally configured `avatar.heygen_avatar_look_id`; inspect the installed tool schema for exact fields. If narration came from FAL, do not pass a local file path: upload audio through HeyGen's supported asset flow only with explicit authorization, then use the asset ID if the current schema supports it. Save the completed video as `jobs/<slug>/presenter/<id>.mp4`. Poll `get_video` with the returned video ID until complete; never resubmit to check progress. A timeout or error is not permission to retry.

### 8. Render with Remotion

```
cd video-studio && npm ci
cd ..  # back to repo root
python .agents/skills/presenter-video-pipeline/scripts/render.py jobs/<slug> [--format landscape|portrait|both] [--preview]
```

Outputs go to `jobs/<slug>/out/`. `render.py` uses Remotion and mutes the presenter video while using the separate narration audio. Use `--allow-missing` to render placeholders before HeyGen clips exist. Use `--props-only` to write props without rendering.

## Generic references

See `.agents/skills/presenter-video-pipeline/references/`:

- `voice.md` — voice/TTS providers and the HeyGen narration flow
- `heygen.md` — HeyGen MCP setup, avatar/voice, presenter video flow
- `segment-plan.md` — segments.json, claims, source_ref citations, validation
- `rendering.md` — Remotion render flow and presenter/narration mixing
- `qa-disclosure.md` — final QA checklist, disclosure and rights reminders

## Approval gates and charges

Explicit approval is required before each class of billable HeyGen call (narration audio `create_speech`, presenter video `create_video_from_avatar`). Setup, scaffolding, validation, and synthetic tests never call HeyGen and never incur charges.

## Privacy

- No credentials, API keys, real avatar/voice IDs, names, handles, or personal brand in committed files.
- No generated audio/video, voice samples, or avatar source images are committed.
- Each recipient configures only assets and likenesses they own or are authorized to use.
- Do not generate videos or incur charges as part of setup.
