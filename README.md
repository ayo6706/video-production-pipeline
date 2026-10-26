# HeyGen + Remotion Presenter Video Pipeline

A reusable, private starter repository for generating presenter videos with your own HeyGen avatar/voice and Remotion rendering. It inherits no personal or third-party profile, content lane, examples, assets, or voice.

## Repository layout

```
.agents/skills/presenter-video-pipeline/   # this skill (pipeline + scripts)
  SKILL.md                                  # full skill reference
  pipeline.config.json                      # configurable paths, timing, credit budget, TTS pricing
  references/                               # generic workflow references (content/visual planning, voice, HeyGen, segment plan, rendering, QA/disclosure)
    voice.md
    heygen.md
    content-visual-planning.md
    segment-plan.md
    rendering.md
    qa-disclosure.md
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

- Python 3.10+ (the pipeline scripts use the standard library only)
- Node.js 18+ and npm (for Remotion installation and rendering)
- A HeyGen account and access to the HeyGen remote MCP server
- Optional: a FAL account and the `FAL_KEY` environment variable (FAL Chatterbox voice provider)

## Setup

### 1. Add the HeyGen remote MCP server (OAuth)

On the agent host, add HeyGen's remote MCP server using OAuth:

```
hermes mcp add heygen --url https://mcp.heygen.com/mcp/v1/ --auth oauth
```

You must then complete authorization on the MCP host when prompted, and reload/restart the agent host so the MCP server is picked up. OAuth is configured on the same host that runs the pipeline scripts. A callback opened on a different computer or in a remote browser may not reach the local callback listener; complete it in the browser on the MCP host or use that MCP client's documented remote callback/forwarding flow. For non-Hermes MCP clients, add `https://mcp.heygen.com/mcp/v1/` as a remote MCP server and use that client's OAuth authorization flow; exact setup and callback handling are client-specific. Never share OAuth callback codes or secrets in chat, and never write credentials to a file.

### 2. Create or select your own avatar and voice

Choose an avatar look and voice that you own or are authorized to use. Use the HeyGen dashboard or your installed MCP tools (such as `list_avatar_groups`, `list_avatar_looks`, and `list_voices`) to select them. `create_speech` synthesizes the approved text with a selected voice; it does not create an avatar or voice. Create or clone assets only when you have the required rights and consent.

Fill your local persona settings:

1. Copy `.agents/skills/presenter-video-pipeline/personas/persona.template.json` to
   `.agents/skills/presenter-video-pipeline/personas/<your-id>/persona.json`.
2. Set `avatar.heygen_avatar_look_id` to your confirmed HeyGen avatar look ID.
3. Set `voice.heygen_voice_id` to your HeyGen voice ID (HeyGen provider), or configure `voice.fal` with your own reference clip at `voice/reference.wav` and set `FAL_KEY` (FAL provider).
4. Adjust `brand` colors, display name, and handle to neutral values you choose.

Never commit `persona.json` with real IDs — it is gitignored and stays local. Never put credentials in files or chat.

### 3. Configure the pipeline

Review `.agents/skills/presenter-video-pipeline/pipeline.config.json` for paths, timing limits, and rate settings. HeyGen credit rates, monthly allowance, warning floor, and optional FAL TTS price default to `null` intentionally; enter only values verified for your current plan. The credit tool estimates avatar-video credits only, not `create_speech` usage. Until rates are configured, it will refuse to estimate; do not treat missing estimates as free usage.

## Real workflow

Before scaffolding, define the story and line-by-line visual beats with `.agents/skills/presenter-video-pipeline/references/content-visual-planning.md`. Keep factual claims tied to source references, mark company-reported estimates as estimates, and use only scene kinds the current validator and renderer support.

1. **Scaffold** a new video job with `new-video.py <slug> --persona <your-id> --lane <lane-id> --title "Your title"`. This creates `jobs/<slug>/segments.json` plus empty `audio/` and `assets/` directories.
2. **Fill** `segments.json` with your approved narration and scenes. Map every factual claim to the claim ledger; add `source_ref` in scene kinds that support the field.
3. **Validate** the plan with `segment-check.py jobs/<slug>`.
4. **Generate narration audio after explicit approval.** For HeyGen, run `python .agents/skills/presenter-video-pipeline/scripts/tts.py jobs/<slug> --todo` to list segments. Confirm the exact text and voice for each `create_speech` call, then save the returned audio under `jobs/<slug>/audio/<id>.mp3`. FAL Chatterbox is optional: set `FAL_KEY` via the OS Environment Variables UI or a secret manager, preview with `tts.py jobs/<slug> --dry-run`, and do not run billable generation while its rate is unknown. Explicitly approve each FAL invocation's segment set and verified cost before generation. For FAL audio, use the supported HeyGen asset-upload flow only with explicit permission; a local file path cannot be used as an avatar video's audio source.
5. **Import narration.** From the repository root, install `video-studio` dependencies once (`cd video-studio && npm ci`), then return to the repository root and run `python .agents/skills/presenter-video-pipeline/scripts/tts.py jobs/<slug> --import` to convert audio and write the manifest.
6. **Estimate avatar-video credits after narration is complete.** Read the current balance with HeyGen `get_current_user`, then run `python .agents/skills/presenter-video-pipeline/scripts/credit-budget.py estimate jobs/<slug> --remaining <balance>`. The estimator requires a verified `credits_per_minute` rate and covers avatar-video calls only, not speech synthesis. If it blocks, do not treat that as free usage.
7. **Approve each avatar-video call separately.** Confirm the exact avatar look, narration audio, output settings, and cost implications. Record the balance immediately before the video calls.
8. **Generate presenter video.** Use the public audio URL returned by HeyGen `create_speech` with the installed `create_video_from_avatar` schema and the confirmed avatar look ID. Save each completed MP4 as `jobs/<slug>/presenter/<id>.mp4`. Poll `get_video` using its returned video ID until complete; never resubmit to check progress. Ask before retrying any failure or timeout.
9. **Log actual avatar-video use.** After the videos finish, read the current balance and run `python .agents/skills/presenter-video-pipeline/scripts/credit-budget.py log jobs/<slug> --before <balance_before_video> --remaining <balance_after_video>`. Capture the before balance after narration generation so speech usage is not mixed into the video estimate.
10. **Render** with Remotion: `python .agents/skills/presenter-video-pipeline/scripts/render.py jobs/<slug> [--format landscape|portrait|both] [--preview]`. `render.py` mutes the presenter video and uses the separate narration audio. Outputs go to `jobs/<slug>/out/`.

Inspect the installed HeyGen MCP tool schema before calling tools; this repo does not define tool schemas. Setup and synthetic tests never call HeyGen and never incur charges.

## Render with Remotion

```
cd video-studio && npm ci
cd ..  # back to repo root
python .agents/skills/presenter-video-pipeline/scripts/render.py jobs/<slug> [--format landscape|portrait|both] [--preview]
```

Outputs go to `jobs/<slug>/out/`. Use `--allow-missing` to render placeholders before HeyGen clips exist. Use `--props-only` to write props without rendering.

## Generic references

See `.agents/skills/presenter-video-pipeline/references/`:

- `voice.md` — voice/TTS providers and the HeyGen narration flow
- `heygen.md` — HeyGen MCP setup, avatar/voice, presenter video flow
- `content-visual-planning.md` — evidence-led storytelling and visual beat planning
- `segment-plan.md` — segments.json, claims, source_ref citations, validation
- `rendering.md` — Remotion render flow and presenter/narration mixing
- `qa-disclosure.md` — final QA checklist, disclosure and rights reminders

## Dependency security note

The locked Remotion 4.0.538 packages request Zod 4.5.4, which is affected by GHSA-mrhx-c7xc-m3w5. `video-studio/package.json` overrides Zod to 4.6.7, the patched release. Remotion warns that its expected and installed Zod versions differ. Typecheck, composition listing, and a synthetic render were verified with this override, but it remains an upstream compatibility workaround. Recheck after Remotion updates its Zod pin; keep or remove the override only after confirming the resolved version is patched and rerunning the audit and render checks.

## Privacy

- No credentials, API keys, real avatar/voice IDs, names, handles, or personal brand in committed files.
- No generated audio/video, voice samples, or avatar source images are committed (see `.gitignore`).
- Creator-specific voice profiles, private notes, and brand guidance stay local; the portable workflow remains neutral.
- Each recipient configures only assets and likenesses they own or are authorized to use.
- Do not generate videos or incur charges as part of setup.

See `.agents/skills/presenter-video-pipeline/SKILL.md` for the full skill reference.
