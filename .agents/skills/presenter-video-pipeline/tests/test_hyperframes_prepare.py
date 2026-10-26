import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / ".agents" / "skills" / "presenter-video-pipeline" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _common import text_hash  # noqa: E402
from hyperframes_prepare import narration_audio_markup, prepare_workspace  # noqa: E402


class HyperFramesPrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.job = Path(self.temp.name)
        (self.job / "audio").mkdir()
        (self.job / "audio" / "s01.wav").write_bytes(b"synthetic-audio")
        (self.job / "audio" / "s02.wav").write_bytes(b"synthetic-audio")
        self.voice = {
            "provider": "heygen",
            "heygen_voice_id": "synthetic-voice",
            "pronunciations": {},
        }
        settings = {
            "provider": "heygen",
            "voice_id": "synthetic-voice",
            "pron": {},
        }
        settings_hash = text_hash(json.dumps(settings, sort_keys=True))
        self.plan = {
            "segments": [
                {"id": "s01", "text": "First synthetic line."},
                {"id": "s02", "text": "Second synthetic line."},
            ]
        }
        self.manifest = {
            "s01": {
                "file": "audio/s01.wav", "duration": 1.5,
                "text_hash": text_hash(self.plan["segments"][0]["text"]),
                "settings_hash": settings_hash,
            },
            "s02": {
                "file": "audio/s02.wav", "duration": 2.0,
                "text_hash": text_hash(self.plan["segments"][1]["text"]),
                "settings_hash": settings_hash,
            },
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_builds_ordered_audio_clips_from_current_manifest(self):
        markup = narration_audio_markup(
            self.job, self.plan, self.voice, self.manifest,
            gap_seconds=0.25, max_duration=4.0,
        )
        self.assertIn('id="narration-s01"', markup)
        self.assertIn('src="audio/s01.wav" data-start="0" data-duration="1.5"', markup)
        self.assertIn('src="audio/s02.wav" data-start="1.75" data-duration="2"', markup)
        self.assertLess(markup.index("narration-s01"), markup.index("narration-s02"))

    def test_rejects_stale_text_hash(self):
        stale = dict(self.manifest)
        stale["s01"] = {**stale["s01"], "text_hash": "stale"}
        with self.assertRaisesRegex(ValueError, "text"):
            narration_audio_markup(self.job, self.plan, self.voice, stale, 0.25, 4.0)

    def test_rejects_stale_voice_settings_hash(self):
        stale = dict(self.manifest)
        stale["s01"] = {**stale["s01"], "settings_hash": "stale"}
        with self.assertRaisesRegex(ValueError, "settings"):
            narration_audio_markup(self.job, self.plan, self.voice, stale, 0.25, 4.0)

    def test_rejects_audio_path_escape(self):
        unsafe = dict(self.manifest)
        unsafe["s01"] = {**unsafe["s01"], "file": "audio/../outside.wav"}
        with self.assertRaisesRegex(ValueError, "unsafe"):
            narration_audio_markup(self.job, self.plan, self.voice, unsafe, 0.25, 4.0)

    def test_rejects_missing_audio_file(self):
        missing = dict(self.manifest)
        missing["s01"] = {**missing["s01"], "file": "audio/missing.wav"}
        with self.assertRaisesRegex(ValueError, "missing"):
            narration_audio_markup(self.job, self.plan, self.voice, missing, 0.25, 4.0)

    def test_rejects_narration_that_exceeds_storyboard_duration_including_inter_segment_gap(self):
        # Audio content alone totals 3.5s, but the inserted 0.25s gap pushes it to 3.75s.
        with self.assertRaisesRegex(ValueError, "storyboard duration"):
            narration_audio_markup(self.job, self.plan, self.voice, self.manifest, 0.25, 3.6)

    def test_rejects_audio_directory_symlink_outside_job(self):
        with tempfile.TemporaryDirectory() as outside_directory:
            outside = Path(outside_directory)
            (outside / "s01.wav").write_bytes(b"external audio")
            audio_dir = self.job / "audio"
            for child in audio_dir.iterdir():
                child.unlink()
            audio_dir.rmdir()
            os.symlink(outside, audio_dir, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "unsafe"):
                narration_audio_markup(
                    self.job,
                    {"segments": [self.plan["segments"][0]]},
                    self.voice,
                    {"s01": self.manifest["s01"]},
                    0.25,
                    4.0,
                )

    def test_rejects_project_directory_symlink_outside_job(self):
        with tempfile.TemporaryDirectory() as outside_directory, tempfile.TemporaryDirectory() as workspace_directory:
            (self.job / "index.html").write_text("<div></div>", encoding="utf-8")
            os.symlink(outside_directory, self.job / "assets", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "outside the job"):
                prepare_workspace(self.job, Path(workspace_directory) / "build", "")

    def test_silent_job_needs_no_persona_or_audio_manifest(self):
        self.assertEqual(
            narration_audio_markup(self.job, {"segments": []}, {}, {}, 0.25, 3.0),
            "",
        )


if __name__ == "__main__":
    unittest.main()
