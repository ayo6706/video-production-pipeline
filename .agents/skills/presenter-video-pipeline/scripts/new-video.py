"""Create a new video job from a generic template.

Usage:
  python new-video.py <slug> [--persona <id>] [--lane <id>] [--title "Title"]

Creates jobs/<slug>/segments.json plus empty audio/ and assets/ directories.
Persona and lane are left empty when not given; the recipient fills them in.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, load_config, save_json  # noqa: E402

TEMPLATE = {
    "slug": "<slug>",
    "title": "<title>",
    "persona": "<persona-id>",
    "lane": "<lane-id>",
    "source": "lanes/<lane-id>.md",
    "music": "",
    "music_volume": 0.08,
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
    plan["slug"] = a.slug
    plan["title"] = a.title or a.slug
    plan["persona"] = a.persona or ""
    plan["lane"] = a.lane or ""
    plan["source"] = f"{cfg['paths']['lanes']}/{a.lane}.md" if a.lane else f"{cfg['paths']['lanes']}/<lane-id>.md"

    (job / "audio").mkdir(parents=True, exist_ok=True)
    (job / "assets").mkdir(parents=True, exist_ok=True)
    save_json(job / "segments.json", plan)
    print(f"Created {job.relative_to(ROOT)}")
    print("Next: fill jobs/<slug>/segments.json with your approved narration, then run segment-check.py")
    return 0


def re_slug(s: str) -> bool:
    import re
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]*", s or ""))


if __name__ == "__main__":
    sys.exit(main())
