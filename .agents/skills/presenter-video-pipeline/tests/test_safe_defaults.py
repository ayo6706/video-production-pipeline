import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
SKILL = ROOT / ".agents" / "skills" / "presenter-video-pipeline"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _common  # noqa: E402
from tts import estimate_tts_cost, fal_audio, heygen_audio  # noqa: E402


class SafeDefaultsTests(unittest.TestCase):
    def test_unverified_cost_and_credit_rates_are_unset(self):
        config = json.loads((SKILL / "pipeline.config.json").read_text(encoding="utf-8"))
        self.assertIsNone(config["heygen"]["credits_per_minute"])
        self.assertIsNone(config["heygen"]["monthly_credits"])
        self.assertIsNone(config["tts"]["price_per_1000_chars"])

    def test_credit_estimate_refuses_missing_rate_with_clear_error(self):
        config = {"heygen": {"credits_per_minute": None}}
        with self.assertRaisesRegex(ValueError, "credits_per_minute"):
            _common.heygen_credits(60, config)

    def test_tts_cost_is_unknown_until_configured(self):
        self.assertIsNone(estimate_tts_cost(1000, {"tts": {"price_per_1000_chars": None}}))
        self.assertAlmostEqual(
            estimate_tts_cost(1000, {"tts": {"price_per_1000_chars": 0.02}}),
            0.02,
        )

    def test_fal_dry_run_labels_unconfigured_cost_as_unknown(self):
        output = io.StringIO()
        with redirect_stdout(output):
            fal_audio(
                SimpleNamespace(dry_run=True, default_voice=False),
                Path("unused"),
                {},
                [{"id": "s01", "text": "Synthetic sample"}],
                {},
                "hash",
                {},
                {"tts": {"price_per_1000_chars": None}},
            )
        self.assertIn("cost unknown", output.getvalue().lower())

    def test_fal_todo_is_non_destructive(self):
        args = SimpleNamespace(dry_run=False, default_voice=False, todo=True)
        with patch.dict(os.environ, {"FAL_KEY": ""}), self.assertRaisesRegex(SystemExit, "--todo"):
            fal_audio(
                args,
                Path("unused"),
                {},
                [{"id": "s01", "text": "Synthetic sample"}],
                {},
                "hash",
                {},
                {"tts": {"price_per_1000_chars": 0.02}},
            )

    def test_fal_generation_requires_verified_price(self):
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(SystemExit, "cost"):
            fal_audio(
                SimpleNamespace(dry_run=False, default_voice=False),
                Path("unused"),
                {},
                [{"id": "s01", "text": "Synthetic sample"}],
                {},
                "hash",
                {},
                {"tts": {"price_per_1000_chars": None}},
            )

    def test_credit_estimate_blocks_when_rate_is_not_configured(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-job-") as job_dir:
            job = Path(job_dir)
            (job / "segments.json").write_text(
                json.dumps({
                    "slug": "synthetic-test",
                    "segments": [{"id": "s01", "type": "presenter", "text": "A short synthetic opening."}],
                }),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "credit-budget.py"), "estimate", str(job)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("credits_per_minute", (result.stdout + result.stderr).lower())

    def test_credit_status_reports_unconfigured_monthly_allowance(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "credit-budget.py"), "status"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("monthly allowance not configured", result.stdout.lower())

    def test_segment_check_does_not_invent_credit_estimate(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-", dir=SKILL / "personas") as persona_dir:
            persona_id = Path(persona_dir).name
            lane_id = f"test-{persona_id}"
            lane_path = SKILL / "lanes" / f"{lane_id}.md"
            lane_path.write_text("Synthetic test lane.\n", encoding="utf-8")
            try:
                with tempfile.TemporaryDirectory(prefix="synthetic-job-") as job_dir:
                    job = Path(job_dir)
                    (job / "segments.json").write_text(
                        json.dumps({
                            "slug": "synthetic-test",
                            "persona": persona_id,
                            "lane": lane_id,
                            "source": "README.md",
                            "segments": [
                                {"id": "s01", "type": "presenter", "text": "A short synthetic opening."},
                                {"id": "s02", "type": "screen", "text": "This generic scene supports it.", "scene": {"kind": "title", "headline": "Sample"}},
                            ],
                        }),
                        encoding="utf-8",
                    )
                    result = subprocess.run(
                        [sys.executable, str(SCRIPTS / "segment-check.py"), str(job)],
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("credit estimate not configured", result.stdout.lower())
            finally:
                lane_path.unlink(missing_ok=True)

    def test_persona_template_uses_empty_recipient_owned_heygen_ids(self):
        template = json.loads(
            (SKILL / "personas" / "persona.template.json").read_text(encoding="utf-8")
        )
        self.assertEqual(template["voice"]["provider"], "heygen")
        self.assertEqual(template["avatar"]["heygen_avatar_look_id"], "")
        self.assertEqual(template["voice"]["heygen_voice_id"], "")

    def test_heygen_import_word_timing_uses_pronunciation_applied_spoken_text(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-job-") as job_dir:
            job = Path(job_dir)
            (job / "audio").mkdir()
            rate = 44100
            block_align = 2
            fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * block_align, block_align, 16)
            pcm = b"\0" * rate * block_align
            _common.write_wav(job / "audio" / "s01.wav", fmt, pcm)
            voice = {"heygen_voice_id": "v1", "pronunciations": {"read": "reed"}}
            manifest = {}
            heygen_audio(
                SimpleNamespace(import_audio=True),
                job,
                [{"id": "s01", "text": "I read it."}],
                voice,
                "hash",
                manifest,
                {},
            )
            self.assertEqual(manifest["s01"]["words"][1]["text"], "reed")

    def test_heygen_todo_output_names_actual_save_path_not_placeholder(self):
        output = io.StringIO()
        with redirect_stdout(output):
            heygen_audio(
                SimpleNamespace(import_audio=False, todo=False, dry_run=False),
                Path("unused"),
                [{"id": "s01", "text": "Hello world."}],
                {"heygen_voice_id": "v1", "pronunciations": {}},
                "hash",
                {},
                {},
            )
        text = output.getvalue()
        self.assertIn("audio/s01.mp3", text)
        self.assertNotIn("save it to save_as", text)

    def test_fal_import_records_default_voice_setting(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-job-") as job_dir:
            job = Path(job_dir)
            (job / "audio").mkdir()
            rate = 44100
            block_align = 2
            fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * block_align, block_align, 16)
            wav_path = job / "fixture.wav"
            _common.write_wav(wav_path, fmt, b"\0" * rate * block_align)
            fal_settings = {"model": "synthetic-model", "language": "english"}
            voice = {"fal": fal_settings, "pronunciations": {}}
            settings = {"provider": "fal-chatterbox", "fal": fal_settings, "pron": {}, "default_voice": True}
            settings_hash = _common.text_hash(json.dumps(settings, sort_keys=True))
            args = SimpleNamespace(dry_run=False, default_voice=True, todo=False)
            with patch.dict(os.environ, {"FAL_KEY": "synthetic-test-key"}), \
                    patch("tts.synth_fal_chatterbox", return_value=wav_path.read_bytes()), \
                    redirect_stdout(io.StringIO()):
                fal_audio(
                    args, job, {}, [{"id": "s01", "text": "Hi."}], voice,
                    settings_hash, {},
                    {"tts": {"price_per_1000_chars": 1.0, "max_chars_per_request": 300, "chunk_gap_seconds": 0.1}},
                )
            manifest = json.loads((job / "audio" / "manifest.json").read_text(encoding="utf-8"))
            self.assertIs(manifest["s01"]["default_voice"], True)


if __name__ == "__main__":
    unittest.main()
