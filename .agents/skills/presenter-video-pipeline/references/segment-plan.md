# Segment plan reference

## Job layout and fields

`new-video.py` creates `jobs/<slug>/segments.json` with:

- `slug`, `title`, `persona`, `lane`: job metadata and local configuration IDs.
- `source`: the lane file path, relative to the repository root.
- `music`, `music_volume`: optional background music asset and mix level.
- `segments`: ordered narration and scene records.

A presenter segment uses `{"id":"s01","type":"presenter","text":"...","on_screen":"..."}`. A screen segment uses `{"id":"s02","type":"screen","text":"...","scene":{"kind":"title","headline":"..."}}`. `text` is narrated; scene fields render on screen.

## Synthetic example

```json
{
  "slug": "synthetic-example",
  "title": "Synthetic sample",
  "persona": "<your-id>",
  "lane": "<lane-id>",
  "source": ".agents/skills/presenter-video-pipeline/lanes/<lane-id>.md",
  "music": "",
  "music_volume": 0.08,
  "segments": [
    {
      "id": "s01",
      "type": "presenter",
      "text": "Hello, this is a synthetic example.",
      "on_screen": "A sample"
    },
    {
      "id": "s02",
      "type": "screen",
      "text": "Here is another synthetic line.",
      "scene": {
        "kind": "title",
        "headline": "Synthetic headline",
        "source_ref": "claim-001"
      }
    }
  ]
}
```

The example is illustrative only; replace the placeholder IDs and copy with your own approved material. For factual on-screen claims, include `scene.source_ref` pointing to a claim ID in the selected lane. The validator requires a `source_ref` for `stat`, `points`, and `quote` scenes; authors should cite all factual claims, including in other scene kinds. The validator checks presence, not whether an ID actually exists in the lane file.

Supported screen scene kinds and their required fields are defined in `scripts/segment-check.py`: `title`, `stat`, `points`, `quote`, `screenshot`, `clip`, `query`, and `cta`.

For faceless or story-led videos, plan a separate line-by-line visual beat sheet using `references/content-visual-planning.md`. Keep it as a planning note; do not add arbitrary `beats` or `shots` properties to `segments.json` unless the validator and Remotion renderer are changed to support them. Map each factual visual to a supported scene kind and the claim ledger; add `source_ref` where that scene kind supports it. The validator checks selected fields for presence, not whether the evidence supports the claim.

## Validation

Run:

```bash
python .agents/skills/presenter-video-pipeline/scripts/segment-check.py jobs/<slug>
```

It checks required metadata, segment IDs and types, spoken-text constraints, configured duration and presenter-share limits, selected scene fields, asset existence, and source-path existence (a missing source path is a warning). It does not verify facts or resolve citation IDs; review sources yourself before rendering.

Job scripts, lane drafts, and media are local and gitignored. Use only material you own or are authorized to use. Examples here are synthetic and neutral.
