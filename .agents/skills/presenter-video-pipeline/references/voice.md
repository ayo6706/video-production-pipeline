# Voice / narration reference

## Provider options

- HeyGen (MCP): narration is synthesized with the HeyGen MCP `create_speech` tool using a recipient-owned/authorized voice ID.
- FAL Chatterbox: optional provider driven by the `FAL_KEY` environment variable and a reference clip at `voice/reference.wav` (or `reference_audio_url`).

FAL-generated audio is local and cannot be passed to HeyGen as a local path. To lip-sync it, use HeyGen's supported audio-asset upload flow and the installed tool's `audioAssetId` input only after explicit authorization to transmit that audio; otherwise use HeyGen-generated narration.

## HeyGen narration flow (real workflow)

1. Run `python .agents/skills/presenter-video-pipeline/scripts/tts.py jobs/<slug> --todo` to list segments that still need audio.
2. For each listed segment, call the HeyGen MCP `create_speech` tool with the segment's narration text and a recipient-confirmed HeyGen voice ID.
3. Save the returned audio to `jobs/<slug>/audio/<id>.mp3`.
4. Install `video-studio` dependencies once (`cd video-studio && npm ci`), return to the repository root, then run `python .agents/skills/presenter-video-pipeline/scripts/tts.py jobs/<slug> --import` to convert the saved audio to WAV and write the narration manifest.
5. Use the public audio URL returned by `create_speech` with `create_video_from_avatar` and a recipient-confirmed avatar look ID. The exact output property name comes from the installed HeyGen tool schema.
6. Save the completed video to `jobs/<slug>/presenter/<id>.mp4`.
7. Poll `get_video` for completion; never resubmit. A failed or timed-out call needs fresh approval before retrying.

## Tool schemas

Do not rely on this document for exact MCP tool schemas. Inspect the schema of the HeyGen MCP tools installed on your host before calling them. Parameter names, required fields, and response properties are defined by the installed server, not by this repo.

## Approval gates

Obtain explicit approval before each billable HeyGen tool call, specifying the exact script/voice or avatar/audio/output. Approval for one `create_speech` call does not authorize another segment, alternate, batch, or retry; a failed or timed-out call needs fresh approval. FAL Chatterbox generation can process multiple segments in one command; approve the exact segment set and verified cost before running it. If the FAL rate is unknown, generation is blocked. Setup, scaffolding, validation, and synthetic tests never call HeyGen or incur charges.

## Rights and disclosure

- Configure only voices you own or are authorized to use. Never use a default cloned voice or anyone else's likeness.
- Voice IDs are local, ignored configuration (see `personas/<your-id>/persona.json`, gitignored). Never commit real IDs and never paste keys or IDs in chat.
- Add an on-screen/video disclosure that narration is AI-synthesized where applicable (see references/qa-disclosure.md).

## FAL_KEY setup (FAL provider only)

Set `FAL_KEY` in the environment before running `tts.py`. Never pass an API key on the command line and never store it in a committed file.

- Windows: add `FAL_KEY` through the OS Environment Variables UI (System → Environment Variables), then restart your terminal/editor.
- macOS/Linux: use your OS environment-variables UI or a secret manager; do not write `FAL_KEY=...` commands in chat or docs.

Example content in this reference is synthetic and neutral; replace it with your own approved narration.
