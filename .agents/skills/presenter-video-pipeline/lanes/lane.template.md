# Lane: <lane-id>

# Replace <lane-id> with a neutral name and copy this file to lanes/<lane-id>.md.
# A lane groups approved facts/claims for one topic. Each claim carries a source_ref
# (claim ID) so on-screen claims can be traced back to the lane source.

source: lanes/<lane-id>.md

# Claims usable in screen segments. id is referenced by scene.source_ref.
claims:
  - id: claim-001
    text: "<neutral example claim>"
    source_ref: "source-001"

# Notes for the person building the video (not spoken on camera).
notes: |
  Fill in only facts you are authorized to use. Do not include personal or
  third-party profile material, real names, or private content drafts.
