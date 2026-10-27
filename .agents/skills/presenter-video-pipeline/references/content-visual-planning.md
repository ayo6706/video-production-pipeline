# Content and visual planning

Use this reference before scaffolding or generating media. It keeps the story, evidence, and visual plan aligned while leaving each creator's voice and subject matter configurable.

## 1. Choose the story

- Pick one viewer problem, decision, or useful question. Avoid a broad topic that cannot be explained in one short video.
- For a case study, make the main thread: the operational friction, what the system actually does, what changed in the workflow, and the reported result. Keep limitations proportionate, but never omit a qualification that changes the meaning of a result.
- Give each spoken line a job: establish the problem, explain the mechanism, show the outcome, or land a practical implication. Remove lines that do none of those.
- Prefer a concrete observation over a grand claim. Do not turn a single example into a universal rule or imply that a reported result is independently verified when it is not.

## 2. Lock the evidence

Before writing polished narration, create a small claim ledger in the job notes or lane source:

| Claim | Source | Evidence wording / location | Qualification |
| --- | --- | --- | --- |
| The specific fact or number | Stable URL or authorized asset | Exact sentence, page, or timestamp | Estimate, self-report, pilot, date, or scope |

- Prefer primary sources for what an organization built and reported. Use independent sources to corroborate material impact claims when available.
- Keep facts, source-reported estimates, and interpretation distinct. Attribute estimates in the narration or on-screen copy (for example, “the company estimates”).
- Preserve dates, denominators, units, and scope. Do not combine metrics from separate products, groups, or time periods.
- Every factual narration or on-screen claim should map to a source reference. Use `source_ref` where the scene schema supports it; keep other claim mappings in the job's claim ledger. A reference records the evidence link; it does not prove that the claim is true.
- Never invent a quotation, page, search result, comment, review, or screen capture. If evidence is missing, qualify or remove the claim.

## 3. Write for the configured voice

- Use the local persona's approved voice notes and examples, if present; they take precedence over generic templates.
- Keep spoken copy natural and easy to say aloud. Favor concrete verbs and plain words over corporate or academic throat-clearing.
- Preserve the speaker's actual level of certainty: an observation stays an observation, an estimate stays an estimate, and an opinion stays an opinion.
- Do not paste creator-specific phrases, voice samples, identity, or brand rules into this portable reference. Keep those materials in local, git-ignored persona files.

## 4. Give each line a visual reason

For each narration sentence, make a planning row with three prompts:

- **Thing:** What real object, product, document, process, or result is being discussed? Use the genuine page, asset, or recording when it can be shown.
- **Idea:** What relationship does the sentence mean—before/after, a process, a comparison, a number, or a turning point? Choose a visual that explains that relationship rather than illustrating only a literal noun.
- **Layer:** What single cue directs attention—an exact highlight, short label, pointer, or crop? Avoid piling decorative effects onto the proof.

Map the result to the current schema: `screenshot`, `clip`, `query`, `stat`, `points`, `quote`, `title`, or `cta`. Required fields and limitations are defined in `segment-plan.md` and `scripts/segment-check.py`.

For faceless videos, aim to change the visual about every 1.5–3 seconds when the narration allows it. Keep captions as the only continuous text; keep labels and cards brief. Use close-up examples, real captures, or simple supported scenes instead of a sequence of static presentation slides. A real source page is evidence; a graphic can explain the relationship, but must not replace or alter the evidence.

For screen demonstrations and evidence-heavy shots, reserve a caption band that does not cover the UI or source text. Source evidence must remain legible when the preview is reduced to roughly 360 pixels wide; crop or zoom the content rather than shrinking its text. Let the depicted action complete, then hold the result long enough to read before cutting. Change visuals to clarify a new idea, not merely to add motion; prefer clean cuts or one motivated dissolve over repeated transitions.

The current starter does not implement custom diagram, comparison, reaction, timeline, or animated-chart scene types. Do not write those kinds into `segments.json` or imply they will render. A genuine, licensed reaction clip may use the supported `clip` scene; otherwise omit it or record the missing capability for a separately approved code change. Learn general visual principles from references, but do not reproduce another creator's distinctive wording, jokes, assets, or exact compositions.

## 5. Review the beat sheet

Before narration synthesis or rendering, check:

- Does the opening create curiosity from a real problem without overstating the stakes?
- Can a viewer follow the progression from problem to mechanism to result without extra context?
- Does every number or quotation have a traceable source and the right qualification?
- Does each shot add proof, explain an idea, or direct attention? Replace repetitive filler.
- Are source captures legible, authentic, and cleared for use? Are captions readable in both target layouts?
- Does the final line leave a useful takeaway or genuine question rather than a generic engagement prompt?

Keep this beat sheet in the review notes. The job's `segments.json` remains the machine-readable source of truth and must follow the implemented schema.
