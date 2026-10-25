# HeyGen reference

## MCP setup (same host)

Add HeyGen's remote MCP server on the agent host using OAuth:

```bash
hermes mcp add heygen --url https://mcp.heygen.com/mcp/v1/ --auth oauth
```

Complete authorization on the host that owns the Hermes MCP configuration and callback listener. Restart/reload the agent and verify with `hermes mcp list` and `hermes mcp test heygen`. Never share OAuth callback codes, tokens, or API keys in chat.

## Choose authorized assets

Use the HeyGen dashboard or the installed MCP tools (for example, `list_avatar_groups`, `list_avatar_looks`, and `list_voices`) to select assets you own or are authorized to use. Store IDs only in ignored local `personas/<your-id>/persona.json`:

- `avatar.heygen_avatar_look_id`: exact confirmed avatar look ID.
- `voice.heygen_voice_id`: exact selected voice ID.

The starter has no real avatar or voice IDs. Do not commit local persona files.

## Presenter-video workflow

1. Run `python .agents/skills/presenter-video-pipeline/scripts/tts.py jobs/<slug> --todo` to get the approved narration segments and local save paths.
2. Inspect the installed tool schema. Obtain explicit approval for each exact `create_speech` call (script and voice). Save the returned audio file under `jobs/<slug>/audio/<id>.mp3`.
3. Install Remotion dependencies once, then run `python .agents/skills/presenter-video-pipeline/scripts/tts.py jobs/<slug> --import` to create the local WAV/manifest used by Remotion.
4. Obtain separate explicit approval for each avatar-video call. Use the audio URL returned by `create_speech` as the lip-sync source and the exact confirmed avatar look ID with `create_video_from_avatar`. Follow the installed tool schema; this reference does not guarantee exact parameter names or response fields.
5. Poll `get_video` using the returned video ID until it completes. Do not resubmit a pending/processing request; ask before retrying after failure or timeout. Save the completed MP4 as `jobs/<slug>/presenter/<id>.mp4`.
6. Render with Remotion. The presenter video is muted; the separate narration track is used for audio and captions.

If narration was created with FAL, a local file path cannot be passed to HeyGen. Upload it using HeyGen's supported audio-asset flow only with explicit authorization to transmit the audio, and use the installed tool's asset-ID input if supported. Otherwise use HeyGen-generated narration.

## Cost and approvals

`credit-budget.py` estimates avatar-video credits only and blocks until a verified `credits_per_minute` rate is configured. It does not estimate `create_speech` charges or quota. After speech is complete, get the current balance with `get_current_user`, estimate with `--remaining <balance>`, and capture the before/after balance around avatar-video generation only; pass both to `credit-budget.py log` so speech usage is not mixed into the video estimate. Obtain explicit approval for every billable call. Setup, scaffolding, validation, and synthetic tests make no HeyGen calls and incur no charges.

## Rights and disclosure

- Use only likenesses and voices you own or are authorized to use.
- Disclose AI-generated voice/video where required by law, platform policy, or the audience context.
- Do not send third-party audio or likeness data to HeyGen without the appropriate rights and consent.
- Keep keys, OAuth codes, and local IDs out of chat and version control.
