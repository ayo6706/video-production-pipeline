import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from shutil import rmtree
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / ".agents" / "skills" / "presenter-video-pipeline" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from editorial_review import (  # noqa: E402
    FRAME_CHECKS,
    GLOBAL_CHECKS,
    create_review_packet,
    main,
    preview_sha256,
    record_review,
    render_input_fingerprint,
    validate_review,
)


class EditorialReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.job = Path(self.temp.name)
        (self.job / "out").mkdir()
        self.preview = self.job / "out" / "sample-9x16-preview.mp4"
        self.preview.write_bytes(b"synthetic preview bytes")
        (self.job / "STORYBOARD.md").write_text(
            "---\nformat: 1080x1920\nfps: 30\nduration: 6s\n---\n\n"
            "## Frame 01 — Signal enters\n"
            "- id: signal\n- start: 0s\n- duration: 3s\n"
            "## Frame 02 — Handoff path\n"
            "- id: flow\n- start: 3s\n- duration: 3s\n",
            encoding="utf-8",
        )
        self.frames = [
            {"id": "signal", "title": "Signal enters", "start": 0.0, "duration": 3.0},
            {"id": "flow", "title": "Handoff path", "start": 3.0, "duration": 3.0},
        ]

    def tearDown(self):
        self.temp.cleanup()

    def _checks(self, names):
        return {name: True for name in names}

    def _record(self, **overrides):
        global_checks = self._checks(GLOBAL_CHECKS)
        frame_checks = {
            frame["id"]: self._checks(FRAME_CHECKS) for frame in self.frames
        }
        global_checks.update(overrides.get("global_checks", {}))
        for frame_id, checks in overrides.get("frame_checks", {}).items():
            frame_checks[frame_id].update(checks)
        create_review_packet(self.job, self.preview, self.frames)
        packet = json.loads((self.job / "out" / "editorial-review-packet.json").read_text(encoding="utf-8"))
        return record_review(
            self.job,
            self.preview,
            self.frames,
            reviewer="QA tester",
            global_checks=global_checks,
            frame_checks=frame_checks,
            expected_preview_sha256=packet["preview_sha256"],
            expected_render_inputs_sha256=packet["render_inputs_sha256"],
        )

    def test_review_packet_embeds_phone_size_preview_and_frame_checks(self):
        packet = create_review_packet(self.job, self.preview, self.frames)
        html = packet.read_text(encoding="utf-8")
        self.assertIn('<video', html)
        self.assertIn('max-width:360px', html)
        self.assertIn('Signal enters', html)
        self.assertIn('captions_clear_of_key_content', html)
        self.assertIn('audio_sync_and_levels', html)
        packet_data = json.loads((self.job / "out" / "editorial-review-packet.json").read_text(encoding="utf-8"))
        self.assertEqual(packet_data["preview_sha256"], preview_sha256(self.preview))
        self.assertEqual(len(packet_data["render_inputs_sha256"]), 64)

    def test_review_packet_refuses_symlinked_output_files(self):
        output_dir = self.job / "out"
        for filename in ("editorial-review-packet.json", "editorial-review.html"):
            for generated in output_dir.iterdir():
                if generated != self.preview:
                    generated.unlink()
            outside = self.job.parent / f"external-{uuid.uuid4().hex}"
            outside.write_text("keep this file unchanged", encoding="utf-8")
            destination = output_dir / filename
            destination.symlink_to(outside)
            try:
                with self.subTest(filename=filename):
                    with self.assertRaisesRegex(ValueError, "(?i)must not be a symlink"):
                        create_review_packet(self.job, self.preview, self.frames)
                    self.assertEqual(outside.read_text(encoding="utf-8"), "keep this file unchanged")
                    if filename == "editorial-review.html":
                        self.assertFalse((output_dir / "editorial-review-packet.json").exists())
            finally:
                destination.unlink(missing_ok=True)
                outside.unlink(missing_ok=True)

    def test_missing_review_record_blocks_delivery(self):
        create_review_packet(self.job, self.preview, self.frames)
        errors = validate_review(self.job, self.preview, self.frames)
        self.assertTrue(any("missing" in error.lower() for error in errors), errors)

    def test_complete_review_record_passes(self):
        self._record()
        self.assertEqual(validate_review(self.job, self.preview, self.frames), [])

    def test_failed_frame_check_blocks_delivery(self):
        self._record(frame_checks={"flow": {"captions_clear_of_key_content": False}})
        errors = validate_review(self.job, self.preview, self.frames)
        self.assertTrue(any("flow" in error and "captions_clear_of_key_content" in error for error in errors), errors)

    def test_stale_preview_hash_invalidates_review(self):
        self._record()
        self.preview.write_bytes(b"a newer preview")
        errors = validate_review(self.job, self.preview, self.frames)
        self.assertTrue(any("changed" in error.lower() or "stale" in error.lower() for error in errors), errors)

    def test_missing_frame_check_cannot_be_approved(self):
        self._record(frame_checks={"flow": {"captions_clear_of_key_content": False}})
        review_path = self.job / "out" / "editorial-review.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        del review["frames"]["flow"]["action_completes_before_cut"]
        review_path.write_text(json.dumps(review), encoding="utf-8")
        errors = validate_review(self.job, self.preview, self.frames)
        self.assertTrue(any("action_completes_before_cut" in error for error in errors), errors)

    def test_render_input_fingerprint_changes_when_storyboard_timing_changes(self):
        before = render_input_fingerprint(self.job)
        storyboard = self.job / "STORYBOARD.md"
        storyboard.write_text(storyboard.read_text().replace("start: 3s", "start: 2s"), encoding="utf-8")
        self.assertNotEqual(before, render_input_fingerprint(self.job))

    def test_render_input_fingerprint_changes_when_directory_alias_is_retargeted(self):
        assets = self.job / "assets"
        first = assets / "a"
        second = assets / "b"
        first.mkdir(parents=True)
        second.mkdir()
        (first / "evidence.svg").write_text("<svg>A</svg>", encoding="utf-8")
        (second / "evidence.svg").write_text("<svg>B</svg>", encoding="utf-8")
        alias = assets / "z_alias"
        os.symlink(first, alias, target_is_directory=True)
        (self.job / "index.html").write_text('<img src="assets/z_alias/evidence.svg">', encoding="utf-8")
        before = render_input_fingerprint(self.job)
        alias.unlink()
        os.symlink(second, alias, target_is_directory=True)
        self.assertNotEqual(before, render_input_fingerprint(self.job))

    def test_render_input_fingerprint_includes_the_active_persona_settings(self):
        persona_id = f"editorial-review-test-{uuid.uuid4().hex[:8]}"
        skill_dir = ROOT / ".agents" / "skills" / "presenter-video-pipeline"
        persona_dir = skill_dir / "personas" / persona_id
        persona_dir.mkdir(parents=True)
        persona_path = persona_dir / "persona.json"
        persona_path.write_text(json.dumps({"voice": {"voice_id": "first"}}), encoding="utf-8")
        segments_path = self.job / "segments.json"
        segments_path.write_text(json.dumps({"persona": persona_id, "segments": []}), encoding="utf-8")
        try:
            before = render_input_fingerprint(self.job)
            persona_path.write_text(json.dumps({"voice": {"voice_id": "second"}}), encoding="utf-8")
            self.assertNotEqual(before, render_input_fingerprint(self.job))
        finally:
            rmtree(persona_dir, ignore_errors=True)

    def test_storyboard_title_change_invalidates_review_without_preview_change(self):
        self._record()
        storyboard = self.job / "STORYBOARD.md"
        storyboard.write_text(storyboard.read_text().replace("Signal enters", "Different title"), encoding="utf-8")
        errors = validate_review(self.job, self.preview, self.frames)
        self.assertTrue(any("input" in error.lower() or "source" in error.lower() for error in errors), errors)

    def test_review_record_rejects_preview_replaced_after_review_snapshot(self):
        create_review_packet(self.job, self.preview, self.frames)
        expected_preview = preview_sha256(self.preview)
        expected_inputs = render_input_fingerprint(self.job)
        self.preview.write_bytes(b"replacement preview")
        with self.assertRaisesRegex(ValueError, "(?i)preview changed"):
            record_review(
                self.job, self.preview, self.frames, reviewer="QA tester",
                global_checks=self._checks(GLOBAL_CHECKS),
                frame_checks={frame["id"]: self._checks(FRAME_CHECKS) for frame in self.frames},
                expected_preview_sha256=expected_preview,
                expected_render_inputs_sha256=expected_inputs,
            )

    def test_interactive_review_rejects_render_input_change_during_prompts(self):
        create_review_packet(self.job, self.preview, self.frames)
        changed = False

        def answer(_prompt):
            nonlocal changed
            if not changed:
                storyboard = self.job / "STORYBOARD.md"
                storyboard.write_text(storyboard.read_text(encoding="utf-8").replace("Signal enters", "Changed during review"), encoding="utf-8")
                changed = True
            return True

        with patch("builtins.input", return_value="QA tester"), patch(
            "editorial_review._ask", side_effect=answer
        ):
            result = main([str(self.job), "--record"])
        self.assertNotEqual(result, 0)
        self.assertFalse((self.job / "out" / "editorial-review.json").exists())

    def test_interactive_review_rejects_preview_replaced_during_prompts(self):
        create_review_packet(self.job, self.preview, self.frames)
        prompt_count = 0

        def answer(_prompt):
            nonlocal prompt_count
            prompt_count += 1
            if prompt_count == 1:
                self.preview.write_bytes(b"replaced while reviewing")
            return True

        with patch("builtins.input", return_value="QA tester"), patch(
            "editorial_review._ask", side_effect=answer
        ):
            result = main([str(self.job), "--record"])
        self.assertNotEqual(result, 0)
        errors = validate_review(self.job, self.preview, self.frames)
        self.assertTrue(errors, "a preview replaced during review must not leave a passing record")


if __name__ == "__main__":
    unittest.main()
