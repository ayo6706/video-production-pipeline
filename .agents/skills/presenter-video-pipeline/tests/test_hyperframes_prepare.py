import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_workspace_copies_job_inputs_so_later_source_changes_are_isolated(self):
        (self.job / "assets").mkdir()
        (self.job / "assets" / "shape.svg").write_text("<svg>original</svg>", encoding="utf-8")
        real_assets = self.job / "assets" / "a"
        real_assets.mkdir()
        (real_assets / "evidence.svg").write_text("<svg>alias</svg>", encoding="utf-8")
        os.symlink(real_assets, self.job / "assets" / "z_alias", target_is_directory=True)
        (self.job / "compositions").mkdir()
        (self.job / "compositions" / "frame.html").write_text("<div>original</div>", encoding="utf-8")
        (self.job / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
        with tempfile.TemporaryDirectory() as workspace_directory:
            workspace = Path(workspace_directory) / "build"
            prepare_workspace(self.job, workspace, "")
            for name in ("assets", "audio", "compositions"):
                self.assertFalse((workspace / name).is_symlink(), f"{name} must be copied, not linked")
            alias_copy = workspace / "assets" / "z_alias"
            self.assertFalse(alias_copy.is_symlink())
            self.assertEqual((alias_copy / "evidence.svg").read_text(encoding="utf-8"), "<svg>alias</svg>")
            (self.job / "assets" / "shape.svg").write_text("<svg>changed</svg>", encoding="utf-8")
            self.assertEqual(
                (workspace / "assets" / "shape.svg").read_text(encoding="utf-8"),
                "<svg>original</svg>",
            )

    def test_workspace_rejects_inputs_changed_during_snapshot_copy(self):
        source_file = self.job / "audio" / "s01.wav"
        source_file.write_bytes(b"reviewed audio")
        (self.job / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
        original_copy = shutil.copy2

        def mutate_during_copy(source, destination, *args, **kwargs):
            if Path(source).resolve() == source_file.resolve():
                source_file.write_bytes(b"unreviewed transient audio")
                result = original_copy(source, destination, *args, **kwargs)
                source_file.write_bytes(b"reviewed audio")
                return result
            return original_copy(source, destination, *args, **kwargs)

        with tempfile.TemporaryDirectory() as workspace_directory:
            workspace = Path(workspace_directory) / "build"
            with patch("hyperframes_prepare.shutil.copy2", side_effect=mutate_during_copy):
                with self.assertRaisesRegex(ValueError, "changed while copying"):
                    prepare_workspace(self.job, workspace, "")

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
