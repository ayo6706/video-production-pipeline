import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SKILL = ROOT / ".agents" / "skills" / "presenter-video-pipeline"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

from storyboard_check import validate_storyboard  # noqa: E402


VALID_STORYBOARD = """---
format: 1080x1920
fps: 30
duration: 6s
message: A synthetic process example
---

## Frame 01 — Hook
- id: hook
- start: 0s
- duration: 3s
- status: built
- src: compositions/frames/01-hook.html
- scene: Close-up of a component moving into position
- voiceover_segment_id: s01
- source_refs: claim-001
- assets: assets/component.svg
- transition_in: cut

## Frame 02 — Result
- id: result
- start: 3s
- duration: 3s
- status: built
- src: compositions/frames/02-result.html
- scene: The completed process shown in context
- voiceover_segment_id: s02
- source_refs: claim-001
- assets: assets/result.svg
- transition_in: cut
"""


class StoryboardCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.job = Path(self.temp.name)
        (self.job / "compositions" / "frames").mkdir(parents=True)
        (self.job / "assets").mkdir()
        for path in (
            "compositions/frames/01-hook.html",
            "compositions/frames/02-result.html",
            "assets/component.svg",
            "assets/result.svg",
        ):
            (self.job / path).write_text("synthetic fixture", encoding="utf-8")
        (self.job / "segments.json").write_text(
            json.dumps({
                "segments": [
                    {"id": "s01", "text": "We start with the component."},
                    {"id": "s02", "text": "Then the process is complete."},
                ],
                "claims": [{"id": "claim-001", "text": "Synthetic claim"}],
            }),
            encoding="utf-8",
        )
        self.storyboard_path = self.job / "STORYBOARD.md"
        self.storyboard_path.write_text(VALID_STORYBOARD, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_accepts_valid_hyperframes_storyboard_and_job_references(self):
        self.assertEqual(validate_storyboard(self.job), [])

    def test_rejects_missing_built_scene_composition(self):
        (self.job / "compositions/frames/02-result.html").unlink()
        errors = validate_storyboard(self.job)
        self.assertTrue(any("02-result.html" in error for error in errors), errors)

    def test_rejects_missing_asset(self):
        (self.job / "assets/result.svg").unlink()
        errors = validate_storyboard(self.job)
        self.assertTrue(any("assets/result.svg" in error for error in errors), errors)

    def test_rejects_path_traversal_asset(self):
        self.storyboard_path.write_text(
            VALID_STORYBOARD.replace("assets/result.svg", "../../outside.svg"),
            encoding="utf-8",
        )
        errors = validate_storyboard(self.job)
        self.assertTrue(any("unsafe" in error.lower() for error in errors), errors)

    def test_rejects_duplicate_frame_ids(self):
        self.storyboard_path.write_text(
            VALID_STORYBOARD.replace("- id: result", "- id: hook"),
            encoding="utf-8",
        )
        errors = validate_storyboard(self.job)
        self.assertTrue(any("duplicate" in error.lower() for error in errors), errors)

    def test_rejects_unmapped_narration_segment(self):
        self.storyboard_path.write_text(
            VALID_STORYBOARD.replace("voiceover_segment_id: s02", "voiceover_segment_id: s99"),
            encoding="utf-8",
        )
        errors = validate_storyboard(self.job)
        self.assertTrue(any("s99" in error for error in errors), errors)

    def test_rejects_unmapped_claim_reference(self):
        self.storyboard_path.write_text(
            VALID_STORYBOARD.replace("source_refs: claim-001", "source_refs: claim-999"),
            encoding="utf-8",
        )
        errors = validate_storyboard(self.job)
        self.assertTrue(any("claim-999" in error for error in errors), errors)

    def test_rejects_invalid_or_overlapping_timing(self):
        self.storyboard_path.write_text(
            VALID_STORYBOARD.replace("start: 3s", "start: 2s"),
            encoding="utf-8",
        )
        errors = validate_storyboard(self.job)
        self.assertTrue(any("overlap" in error.lower() for error in errors), errors)

    def test_render_ready_requires_a_valid_hyperframes_root_composition(self):
        self.storyboard_path.write_text(
            VALID_STORYBOARD.replace("status: built", "status: animated"),
            encoding="utf-8",
        )
        errors = validate_storyboard(self.job, require_ready=True)
        self.assertTrue(any("index.html" in error for error in errors), errors)

    def test_render_ready_rejects_root_canvas_mismatch(self):
        self.storyboard_path.write_text(
            VALID_STORYBOARD.replace("status: built", "status: animated"),
            encoding="utf-8",
        )
        (self.job / "index.html").write_text(
            '<div id="root" data-composition-id="main" data-start="0" data-width="1920" '
            'data-height="1080" data-duration="6"></div>',
            encoding="utf-8",
        )
        errors = validate_storyboard(self.job, require_ready=True)
        self.assertTrue(any("canvas" in error.lower() for error in errors), errors)

    def test_render_ready_accepts_root_canvas_matching_storyboard(self):
        self.storyboard_path.write_text(
            VALID_STORYBOARD.replace("status: built", "status: animated"),
            encoding="utf-8",
        )
        (self.job / "index.html").write_text(
            '<div id="root" data-composition-id="main" data-start="0" '
            'data-width="1080" data-height="1920" data-duration="6">'
            '<div id="hook" data-composition-id="hook" data-composition-src="compositions/frames/01-hook.html" '
            'data-start="0" data-duration="3" data-width="1080" data-height="1920"></div>'
            '<div id="result" data-composition-id="result" data-composition-src="compositions/frames/02-result.html" '
            'data-start="3" data-duration="3" data-width="1080" data-height="1920"></div>'
            '</div>',
            encoding="utf-8",
        )
        self.assertEqual(validate_storyboard(self.job, require_ready=True), [])

    def test_render_ready_reports_root_and_frame_mount_errors_together(self):
        self.storyboard_path.write_text(
            VALID_STORYBOARD.replace("status: built", "status: animated"),
            encoding="utf-8",
        )
        (self.job / "index.html").write_text(
            '<div id="root" data-composition-id="main" data-start="0" '
            'data-width="1080" data-height="1920" data-duration="3">'
            '<div id="hook" data-composition-id="hook" data-composition-src="compositions/frames/01-hook.html" '
            'data-start="1" data-duration="3" data-width="1080" data-height="1920"></div></div>',
            encoding="utf-8",
        )
        errors = validate_storyboard(self.job, require_ready=True)
        self.assertTrue(any("root data-duration" in error for error in errors), errors)
        self.assertTrue(any("hook" in error and "data-start" in error for error in errors), errors)
        self.assertTrue(any("result" in error and "mount" in error for error in errors), errors)

    def test_render_ready_rejects_a_storyboard_frame_not_mounted_in_the_root(self):
        self.storyboard_path.write_text(
            VALID_STORYBOARD.replace("status: built", "status: animated"),
            encoding="utf-8",
        )
        (self.job / "index.html").write_text(
            '<div id="root" data-composition-id="main" data-start="0" '
            'data-width="1080" data-height="1920" data-duration="6"></div>',
            encoding="utf-8",
        )
        errors = validate_storyboard(self.job, require_ready=True)
        self.assertTrue(any("hook" in error and "mount" in error.lower() for error in errors), errors)

    def test_render_ready_rejects_a_root_mount_with_an_empty_time_attribute(self):
        self.storyboard_path.write_text(
            VALID_STORYBOARD.replace("status: built", "status: animated"),
            encoding="utf-8",
        )
        (self.job / "index.html").write_text(
            '<div id="root" data-composition-id="main" data-start="0" '
            'data-width="1080" data-height="1920" data-duration="6">'
            '<div id="hook" data-composition-id="hook" data-composition-src="compositions/frames/01-hook.html" '
            'data-start data-duration="3" data-width="1080" data-height="1920"></div>'
            '<div id="result" data-composition-id="result" data-composition-src="compositions/frames/02-result.html" '
            'data-start="3" data-duration="3" data-width="1080" data-height="1920"></div></div>',
            encoding="utf-8",
        )
        errors = validate_storyboard(self.job, require_ready=True)
        self.assertTrue(any("data-start" in error for error in errors), errors)

    def test_render_ready_rejects_outline_frames(self):
        self.storyboard_path.write_text(
            VALID_STORYBOARD.replace("status: built", "status: outline", 1),
            encoding="utf-8",
        )
        errors = validate_storyboard(self.job, require_ready=True)
        self.assertTrue(any("outline" in error.lower() for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
