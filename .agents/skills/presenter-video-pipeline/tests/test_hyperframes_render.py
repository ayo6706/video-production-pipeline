import json
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
SKILL = ROOT / ".agents" / "skills" / "presenter-video-pipeline"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

from hyperframes_render import render_job  # noqa: E402
from _common import text_hash  # noqa: E402


class HyperFramesRenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.job = Path(self.temp.name) / "sample"
        self.job.mkdir()
        self.cli = Path(self.temp.name) / "hyperframes"
        self.ffprobe = Path(self.temp.name) / "ffprobe"
        self.ffprobe.write_text("test double", encoding="utf-8")
        (self.job / "compositions" / "frames").mkdir(parents=True)
        (self.job / "assets").mkdir()
        (self.job / "compositions" / "frames" / "hook.html").write_text(
            "<div class='clip' data-start='0' data-duration='3'>Synthetic frame</div>",
            encoding="utf-8",
        )
        (self.job / "assets" / "shape.svg").write_text("<svg/>", encoding="utf-8")
        (self.job / "index.html").write_text(
            '<div id="root" data-composition-id="main" data-start="0" '
            'data-width="1080" data-height="1920" data-duration="3">'
            '<div id="hook" data-composition-id="hook" data-composition-src="compositions/frames/hook.html" '
            'data-start="0" data-duration="3" data-width="1080" data-height="1920"></div></div>',
            encoding="utf-8",
        )
        (self.job / "segments.json").write_text(
            json.dumps({
                "engine": "hyperframes",
                "slug": "sample",
                "segments": [{"id": "s01", "text": ""}],
                "claims": [{"id": "claim-001", "text": "Synthetic evidence claim."}],
            }),
            encoding="utf-8",
        )
        (self.job / "STORYBOARD.md").write_text(
            "---\nformat: 1080x1920\nfps: 30\nduration: 3s\n---\n\n"
            "## Frame 01 — Hook\n"
            "- id: hook\n"
            "- start: 0s\n"
            "- duration: 3s\n"
            "- status: animated\n"
            "- src: compositions/frames/hook.html\n"
            "- scene: A specific action demonstrating the narrated process.\n"
            "- voiceover_segment_id: s01\n"
            "- source_refs: claim-001\n"
            "- assets: assets/shape.svg\n"
            "- transition_in: cut\n",
            encoding="utf-8",
        )
        self.commands = []

    def tearDown(self):
        self.temp.cleanup()

    def fake_runner(self, command, **kwargs):
        self.commands.append((command, kwargs))
        if command[0] == str(self.ffprobe):
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                "streams": [
                    {"codec_type": "video", "width": 1080, "height": 1920},
                    {"codec_type": "audio"},
                ],
                "format": {"duration": "3.0"},
            }), stderr="")
        action = command[1]
        if action == "lint":
            return SimpleNamespace(returncode=0, stdout=json.dumps({"errorCount": 0, "warningCount": 0}), stderr="")
        if action == "check":
            return SimpleNamespace(returncode=0, stdout=json.dumps({"ok": True, "craft": {"warningCount": 0}}), stderr="")
        if action == "snapshot":
            return SimpleNamespace(returncode=0, stdout=json.dumps({"frames": [], "contactSheets": []}), stderr="")
        if action == "render":
            output = Path(command[command.index("--output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"synthetic-render")
            return SimpleNamespace(returncode=0, stdout="rendered", stderr="")
        self.fail(f"Unexpected command: {command}")

    def test_preview_runs_validation_review_render_and_probes_output(self):
        result = render_job(
            self.job, preview=True, runner=self.fake_runner,
            cli_path=self.cli, ffprobe_path=self.ffprobe,
        )
        self.assertEqual(result, 0)
        output = self.job / "out" / "sample-9x16-preview.mp4"
        self.assertGreater(output.stat().st_size, 0)
        self.assertEqual([entry[0][1] for entry in self.commands[:-1]], ["lint", "check", "snapshot", "render"])
        self.assertEqual(self.commands[-2][0][self.commands[-2][0].index("--quality") + 1], "draft")
        self.assertIn("--no-best-effort", self.commands[-2][0])
        env = self.commands[0][1]["env"]
        self.assertEqual(env["HYPERFRAMES_NO_UPDATE_CHECK"], "1")
        self.assertEqual(env["HYPERFRAMES_NO_TELEMETRY"], "1")
        self.assertEqual(env["HYPERFRAMES_SKIP_SKILLS"], "1")

    def test_narration_is_injected_in_a_temporary_root_without_mutating_the_job(self):
        token = uuid.uuid4().hex[:10]
        persona_id = f"synthetic-hf-{token}"
        persona_dir = SKILL / "personas" / persona_id
        persona_dir.mkdir(parents=True)
        voice_id = "synthetic-voice"
        text = "A synthetic narration line."
        voice = {"provider": "heygen", "heygen_voice_id": voice_id, "pronunciations": {}}
        settings = {"provider": "heygen", "voice_id": voice_id, "pron": {}}
        source_index = self.job / "index.html"
        html = source_index.read_text(encoding="utf-8").replace(
            "</div></div>", "<!-- HYPERFRAMES_NARRATION_AUDIO --></div></div>"
        )
        source_index.write_text(html, encoding="utf-8")
        (self.job / "audio").mkdir()
        (self.job / "audio" / "s01.wav").write_bytes(b"synthetic audio")
        (persona_dir / "persona.json").write_text(json.dumps({"voice": voice}), encoding="utf-8")
        (self.job / "segments.json").write_text(json.dumps({
            "engine": "hyperframes", "slug": "sample", "persona": persona_id,
            "segments": [{"id": "s01", "text": text}],
            "claims": [{"id": "claim-001", "text": "Synthetic evidence claim."}],
        }), encoding="utf-8")
        (self.job / "audio" / "manifest.json").write_text(json.dumps({
            "s01": {
                "file": "audio/s01.wav", "duration": 1.0,
                "text_hash": text_hash(text),
                "settings_hash": text_hash(json.dumps(settings, sort_keys=True)),
            }
        }), encoding="utf-8")

        def inspecting_runner(command, **kwargs):
            if command[0] != str(self.ffprobe):
                built_html = (Path(kwargs["cwd"]) / "index.html").read_text(encoding="utf-8")
                self.assertIn('src="audio/s01.wav" data-start="0" data-duration="1"', built_html)
            return self.fake_runner(command, **kwargs)

        try:
            result = render_job(
                self.job, preview=True, runner=inspecting_runner,
                cli_path=self.cli, ffprobe_path=self.ffprobe,
            )
            self.assertEqual(result, 0)
            self.assertIn("HYPERFRAMES_NARRATION_AUDIO", source_index.read_text(encoding="utf-8"))
            self.assertNotIn('<audio id="narration-s01"', source_index.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(persona_dir, ignore_errors=True)

    def test_preview_reports_warnings_from_quality_checks(self):
        import io
        from contextlib import redirect_stdout

        def warning_runner(command, **kwargs):
            if command[0] == str(self.ffprobe):
                return self.fake_runner(command, **kwargs)
            self.commands.append((command, kwargs))
            if command[1] == "lint":
                return SimpleNamespace(returncode=0, stdout='{"errorCount":0,"warningCount":1}', stderr="")
            if command[1] == "check":
                return SimpleNamespace(returncode=0, stdout='{"ok":true,"craft":{"warningCount":1}}', stderr="")
            return self.fake_runner(command, **kwargs)

        output = io.StringIO()
        with redirect_stdout(output):
            result = render_job(
                self.job, preview=True, runner=warning_runner,
                cli_path=self.cli, ffprobe_path=self.ffprobe,
            )
        self.assertEqual(result, 0)
        self.assertIn("warning", output.getvalue().lower())
        self.assertIn("1", output.getvalue())

    def test_final_render_requires_explicit_approval_before_cli_calls(self):
        result = render_job(
            self.job, approved=False, runner=self.fake_runner,
            cli_path=self.cli, ffprobe_path=self.ffprobe,
        )
        self.assertNotEqual(result, 0)
        self.assertEqual(self.commands, [])


if __name__ == "__main__":
    unittest.main()
