"""Create a video job with narration plan and a HyperFrames visual storyboard.

Usage:
  python new-video.py <slug> [--persona <id>] [--lane <id>] [--title "Title"]
                         [--format portrait|landscape] [--engine hyperframes|remotion]

New jobs default to HyperFrames. Choose Remotion explicitly for a legacy-compatible job.
"""
import argparse
from html import escape
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, load_config, save_json  # noqa: E402

TEMPLATE = {
    "engine": "hyperframes",
    "slug": "<slug>",
    "title": "<title>",
    "persona": "<persona-id>",
    "lane": "<lane-id>",
    "source": "lanes/<lane-id>.md",
    "music": "",
    "music_volume": 0.08,
    "claims": [],
    "segments": [
        {"id": "s01", "type": "presenter", "text": "", "on_screen": ""},
        {"id": "s02", "type": "screen", "text": "", "scene": {"kind": "title", "headline": "", "source_ref": ""}}
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("--persona", default="")
    ap.add_argument("--lane", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--format", choices=["portrait", "landscape"], default="portrait")
    ap.add_argument("--engine", choices=["hyperframes", "remotion"], default="hyperframes")
    a = ap.parse_args()

    if not re_slug(a.slug):
        sys.exit("slug must be lowercase letters, digits and hyphens (e.g. my-video)")
    for label, value in (("persona", a.persona), ("lane", a.lane)):
        if value and not re_slug(value):
            sys.exit(f"{label} ID must use lowercase letters, digits and hyphens only.")
    cfg = load_config()
    videos_dir = ROOT / cfg["paths"]["videos"]
    job = videos_dir / a.slug
    if job.exists():
        sys.exit(f"Job already exists: {job}")

    plan = dict(TEMPLATE)
    plan["engine"] = a.engine
    plan["slug"] = a.slug
    plan["title"] = " ".join((a.title or a.slug).split())
    plan["persona"] = a.persona or ""
    plan["lane"] = a.lane or ""
    plan["source"] = f"{cfg['paths']['lanes']}/{a.lane}.md" if a.lane else f"{cfg['paths']['lanes']}/<lane-id>.md"

    width, height = (1080, 1920) if a.format == "portrait" else (1920, 1080)
    (job / "audio").mkdir(parents=True, exist_ok=True)
    (job / "assets").mkdir(parents=True, exist_ok=True)
    (job / "compositions" / "frames").mkdir(parents=True, exist_ok=True)
    save_json(job / "segments.json", plan)
    storyboard_lines = [
        "---",
        f"format: {width}x{height}",
        f"fps: {cfg.get('fps', 30)}",
        "duration: 30s",
        "---",
        "",
        f"# {plan['title']}",
        "",
        "## Frame 01 — Hook",
        "- id: hook",
        "- start: 0s",
        "- duration: 3s",
        "- status: outline",
        "- scene: Replace with a specific visual action that supports the opening line.",
        "- voiceover_segment_id:",
        "- source_refs:",
        "- assets:",
        "- transition_in: cut",
    ]
    (job / "STORYBOARD.md").write_text(chr(10).join(storyboard_lines) + chr(10), encoding="utf-8")
    if a.engine == "hyperframes":
        root_html = f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={width}, height={height}" />
    <title>{escape(plan["title"])}</title>
    <style>
      html, body {{ margin: 0; width: {width}px; height: {height}px; background: #10191d; }}
      #root {{ position: relative; width: {width}px; height: {height}px; overflow: hidden; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="30" data-width="{width}" data-height="{height}" data-no-timeline>
      <div id="hook" data-composition-id="hook" data-composition-src="compositions/frames/hook.html" data-start="0" data-duration="3" data-track-index="1" data-width="{width}" data-height="{height}"></div>
      <!-- HYPERFRAMES_NARRATION_AUDIO -->
    </div>
  </body>
</html>
'''
        (job / "index.html").write_text(root_html, encoding="utf-8")
    print(f"Created {job.relative_to(ROOT)}")
    print("Next: add narration and claim IDs to segments.json, plan every visual beat in STORYBOARD.md, then run segment-check.py and storyboard-check.py")
    return 0


def re_slug(s: str) -> bool:
    import re
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]*", s or ""))


if __name__ == "__main__":
    sys.exit(main())
