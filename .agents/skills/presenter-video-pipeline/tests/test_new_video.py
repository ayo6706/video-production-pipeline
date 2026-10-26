import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SKILL = ROOT / ".agents" / "skills" / "presenter-video-pipeline"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _common  # noqa: E402


class NewVideoTests(unittest.TestCase):
    def run_new_video(self, slug, persona="sample", lane="sample"):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "new-video.py"),
                slug,
                "--persona",
                persona,
                "--lane",
                lane,
                "--title",
                "Synthetic test video",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_new_video_uses_configured_lane_path(self):
        slug = f"synthetic-test-{uuid.uuid4().hex[:10]}"
        job = ROOT / "jobs" / slug
        try:
            result = self.run_new_video(slug)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plan = json.loads((job / "segments.json").read_text(encoding="utf-8"))
            config = _common.load_config()
            self.assertEqual(plan["source"], f"{config['paths']['lanes']}/sample.md")
            self.assertEqual(plan["engine"], "hyperframes")
            self.assertEqual(plan["claims"], [])
            storyboard = (job / "STORYBOARD.md").read_text(encoding="utf-8")
            self.assertIn("format: 1080x1920", storyboard)
            self.assertIn("## Frame 01 — Hook", storyboard)
            self.assertIn("status: outline", storyboard)
            root_html = (job / "index.html").read_text(encoding="utf-8")
            self.assertIn("data-composition-src=\"compositions/frames/hook.html\"", root_html)
            self.assertIn("HYPERFRAMES_NARRATION_AUDIO", root_html)
        finally:
            shutil.rmtree(job, ignore_errors=True)

    def test_new_video_rejects_path_traversal_persona_and_lane(self):
        for unsafe_persona, unsafe_lane in (("../outside", "sample"), ("sample", "../outside")):
            slug = f"synthetic-test-{uuid.uuid4().hex[:10]}"
            job = ROOT / "jobs" / slug
            try:
                result = self.run_new_video(slug, unsafe_persona, unsafe_lane)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(job.exists())
            finally:
                shutil.rmtree(job, ignore_errors=True)

    def test_persona_lookup_rejects_path_traversal(self):
        with self.assertRaises(SystemExit):
            _common.persona_dir("../../../../video-studio")


if __name__ == "__main__":
    unittest.main()
