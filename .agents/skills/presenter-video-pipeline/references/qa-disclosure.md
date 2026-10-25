# Final QA and disclosure reference

## Before generation

- [ ] The local persona file uses only recipient-owned/authorized avatar and voice IDs and is gitignored.
- [ ] The script and segment plan are approved; factual on-screen claims are traceable to authorized sources.
- [ ] `segment-check.py jobs/<slug>` passes or every warning is reviewed.
- [ ] Speech synthesis cost/quota is checked separately; `credit-budget.py` does not estimate `create_speech` usage.
- [ ] Explicit approval is obtained for each billable speech call, with its exact script and voice.
- [ ] After narration is complete, the current HeyGen balance is read and avatar-video credits are estimated with a verified `credits_per_minute` rate. If the estimate is unavailable, do not treat usage as free.
- [ ] Explicit approval is obtained for each avatar-video call, with exact avatar look, audio, and output settings.
- [ ] Capture the balance immediately before avatar-video generation and after completion; log that delta so speech usage is not mixed into the video estimate.

## After generation

- [ ] Narration is imported with `tts.py jobs/<slug> --import`.
- [ ] Presenter video status is polled with `get_video`; in-flight jobs are never resubmitted.
- [ ] Rendered output in `jobs/<slug>/out/` is watched end-to-end for sync, captions, cuts, cropping, readability, and audio levels.
- [ ] Actual avatar-video usage is logged with `credit-budget.py log`.
- [ ] Titles, captions, claims, rights, and disclosure text are reviewed before distribution.

## Disclosure and rights

- Disclose AI-generated voice or presenter video where required by law, platform policy, or the audience context.
- Use only avatar, voice, and claim material you own or are authorized to use; do not transmit third-party audio or likeness data without consent.
- Do not include personal or third-party profile material, real names, or private drafts in the shared starter.
- Every factual on-screen claim should have a `source_ref` to an authorized source; the validator checks presence for selected scene kinds but does not verify facts or resolve citation IDs.

## Secrets and privacy

- Local persona files, custom lanes, video jobs, and generated media are ignored by Git.
- Never commit API keys, OAuth codes, credentials, real avatar IDs, or voice IDs; never paste them in chat.
- Set `FAL_KEY` through the OS Environment Variables UI or a secret manager, never in a command or committed file.
- Setup, scaffolding, validation, and synthetic tests never call HeyGen or incur charges.
