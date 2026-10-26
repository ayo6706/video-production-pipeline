import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SKILL = ROOT / ".agents" / "skills" / "presenter-video-pipeline"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _common import text_hash, write_wav  # noqa: E402


class RenderPropsTests(unittest.TestCase):
    def test_hyperframes_job_dispatches_without_a_persona(self):
        token = uuid.uuid4().hex[:10]
        job = ROOT / "jobs" / f"synthetic-hf-{token}"
        job.mkdir(parents=True)
        try:
            (job / "segments.json").write_text(json.dumps({
                "engine": "hyperframes", "slug": job.name, "title": "Synthetic",
                "segments": [], "claims": [],
            }), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "render.py"), str(job), "--preview"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Missing STORYBOARD.md", result.stdout + result.stderr)
        finally:
            shutil.rmtree(job, ignore_errors=True)

    def test_rejects_unknown_render_engine_before_loading_persona(self):
        token = uuid.uuid4().hex[:10]
        job = ROOT / "jobs" / f"synthetic-unknown-engine-{token}"
        job.mkdir(parents=True)
        try:
            (job / "segments.json").write_text(json.dumps({
                "engine": "unknown", "slug": job.name, "segments": [], "claims": [],
            }), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "render.py"), str(job)],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("unknown engine", (result.stdout + result.stderr).lower())
        finally:
            shutil.rmtree(job, ignore_errors=True)

    def test_props_only_renders_synthetic_job_without_external_services(self):
        token = uuid.uuid4().hex[:10]
        slug = f"synthetic-test-{token}"
        persona_id = f"synthetic-test-{token}"
        persona_dir = SKILL / "personas" / persona_id
        job = ROOT / "jobs" / slug
        props_path = ROOT / "video-studio" / "jobs" / f"{slug}-landscape.props.json"
        text = "A synthetic narration sample."
        persona_dir.mkdir(parents=True)
        try:
            (persona_dir / "persona.json").write_text(
                json.dumps({
                    "id": persona_id,
                    "display_name": "Synthetic Presenter",
                    "avatar": {"heygen_avatar_look_id": ""},
                    "voice": {"provider": "heygen", "heygen_voice_id": "", "pronunciations": {}},
                    "brand": {
                        "bg": "#111827",
                        "fg": "#F9FAFB",
                        "accent": "#3B82F6",
                        "muted": "#9CA3AF",
                        "panel": "#1F2937",
                        "font": "Arial, sans-serif",
                        "show_name": False,
                        "handle": "",
                    },
                }),
                encoding="utf-8",
            )
            (job / "audio").mkdir(parents=True)
            (job / "segments.json").write_text(
                json.dumps({
                    "slug": slug,
                    "title": "Synthetic render check",
                    "persona": persona_id,
                    "lane": "synthetic",
                    "source": "README.md",
                    "segments": [{
                        "id": "s01",
                        "type": "screen",
                        "text": text,
                        "scene": {"kind": "title", "headline": "Synthetic sample"},
                    }],
                }),
                encoding="utf-8",
            )
            rate = 44100
            block_align = 2
            fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * block_align, block_align, 16)
            write_wav(job / "audio" / "s01.wav", fmt, b"\0" * rate * block_align)
            settings = {"provider": "heygen", "voice_id": "", "pron": {}}
            settings_hash = text_hash(json.dumps(settings, sort_keys=True))
            (job / "audio" / "manifest.json").write_text(
                json.dumps({"s01": {"file": "audio/s01.wav", "duration": 4.0, "text_hash": text_hash(text), "settings_hash": settings_hash, "words": []}}),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "render.py"), str(job), "--format", "landscape", "--props-only"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            props = json.loads(props_path.read_text(encoding="utf-8"))
            self.assertEqual(props["slug"], slug)
            self.assertEqual(props["layout"], "landscape")
            self.assertEqual(props["segments"][0]["audio"], f"jobs/{slug}/audio/s01.wav")
        finally:
            shutil.rmtree(job, ignore_errors=True)
            shutil.rmtree(persona_dir, ignore_errors=True)
            props_path.unlink(missing_ok=True)

    def _make_render_fixture(self, token, manifest_overrides=None, audio_present=True):
        slug = f"synthetic-test-{token}"
        persona_id = f"synthetic-test-{token}"
        persona_dir = SKILL / "personas" / persona_id
        job = ROOT / "jobs" / slug
        persona_dir.mkdir(parents=True)
        (persona_dir / "persona.json").write_text(
            json.dumps({
                "id": persona_id, "display_name": "Synthetic Presenter",
                "avatar": {"heygen_avatar_look_id": ""},
                "voice": {"provider": "heygen", "heygen_voice_id": "", "pronunciations": {}},
                "brand": {
                    "bg": "#111827", "fg": "#F9FAFB", "accent": "#3B82F6",
                    "muted": "#9CA3AF", "panel": "#1F2937", "font": "Arial, sans-serif",
                    "show_name": False, "handle": "",
                },
            }),
            encoding="utf-8",
        )
        (job / "audio").mkdir(parents=True)
        text = "Hello world."
        (job / "segments.json").write_text(
            json.dumps({
                "slug": slug, "title": "T", "persona": persona_id, "lane": "synthetic",
                "source": "README.md",
                "segments": [{"id": "s01", "type": "screen", "text": text,
                              "scene": {"kind": "title", "headline": "Synthetic sample"}}],
            }),
            encoding="utf-8",
        )
        settings = {"provider": "heygen", "voice_id": "", "pron": {}}
        settings_hash = text_hash(json.dumps(settings, sort_keys=True))
        manifest = {"s01": {"file": "audio/s01.wav", "duration": 4.0,
                            "text_hash": text_hash(text), "settings_hash": settings_hash, "words": []}}
        if manifest_overrides:
            manifest["s01"].update(manifest_overrides)
        (job / "audio" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        rate = 44100
        block_align = 2
        fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * block_align, block_align, 16)
        pcm = b"\0" * rate * block_align
        if audio_present:
            write_wav(job / "audio" / "s01.wav", fmt, pcm)
        props_path = ROOT / "video-studio" / "jobs" / f"{slug}-landscape.props.json"
        return job, persona_dir, props_path

    def _run_props_only(self, job):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "render.py"), str(job), "--format", "landscape", "--props-only"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )

    def test_render_accepts_valid_manifest_and_audio(self):
        token = uuid.uuid4().hex[:10]
        job, persona_dir, props_path = self._make_render_fixture(token)
        try:
            result = self._run_props_only(job)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            shutil.rmtree(job, ignore_errors=True)
            shutil.rmtree(persona_dir, ignore_errors=True)
            props_path.unlink(missing_ok=True)

    def test_render_accepts_fal_default_voice_manifest(self):
        token = uuid.uuid4().hex[:10]
        job, persona_dir, props_path = self._make_render_fixture(token)
        try:
            persona_path = persona_dir / "persona.json"
            persona = json.loads(persona_path.read_text(encoding="utf-8"))
            fal_settings = {"model": "synthetic-model", "language": "english"}
            persona["voice"] = {"provider": "fal-chatterbox", "fal": fal_settings, "pronunciations": {}}
            persona_path.write_text(json.dumps(persona), encoding="utf-8")
            settings = {
                "provider": "fal-chatterbox", "fal": fal_settings,
                "pron": {}, "default_voice": True,
            }
            manifest_path = job / "audio" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["s01"].update({
                "settings_hash": text_hash(json.dumps(settings, sort_keys=True)),
                "default_voice": True,
            })
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self._run_props_only(job)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            shutil.rmtree(job, ignore_errors=True)
            shutil.rmtree(persona_dir, ignore_errors=True)
            props_path.unlink(missing_ok=True)

    def test_render_rejects_stale_settings_manifest(self):
        token = uuid.uuid4().hex[:10]
        job, persona_dir, props_path = self._make_render_fixture(
            token, manifest_overrides={"settings_hash": "stale-hash"}
        )
        try:
            result = self._run_props_only(job)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("settings", (result.stdout + result.stderr).lower())
        finally:
            shutil.rmtree(job, ignore_errors=True)
            shutil.rmtree(persona_dir, ignore_errors=True)
            props_path.unlink(missing_ok=True)

    def test_render_rejects_missing_audio_file(self):
        token = uuid.uuid4().hex[:10]
        job, persona_dir, props_path = self._make_render_fixture(token, audio_present=False)
        try:
            result = self._run_props_only(job)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("audio", (result.stdout + result.stderr).lower())
        finally:
            shutil.rmtree(job, ignore_errors=True)
            shutil.rmtree(persona_dir, ignore_errors=True)
            props_path.unlink(missing_ok=True)

    def test_render_rejects_unsafe_audio_path(self):
        token = uuid.uuid4().hex[:10]
        job, persona_dir, props_path = self._make_render_fixture(
            token, manifest_overrides={"file": "../../etc/passwd"}, audio_present=False
        )
        try:
            result = self._run_props_only(job)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("unsafe", (result.stdout + result.stderr).lower())
        finally:
            shutil.rmtree(job, ignore_errors=True)
            shutil.rmtree(persona_dir, ignore_errors=True)
            props_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
