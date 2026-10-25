"""Render a video job with Remotion in 16:9, 9:16 or both.

Usage:
  python render.py <job> [--format landscape|portrait|both] [--preview] [--allow-missing] [--keep] [--props-only]

  --preview        half resolution, faster, for checking layout
  --allow-missing  render placeholders where presenter clips are missing (before HeyGen)
  --keep           keep the copied assets in video-studio/public/jobs/<slug>
  --props-only     write the props files and stop (no render)

Outputs: <job>/out/<slug>-16x9.mp4 and/or <slug>-9x16.mp4
"""
import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (ROOT, load_config, load_manifest, load_persona, load_plan,  # noqa: E402
                     resolve_job, save_json, text_hash)

COMPS = {"landscape": ("Landscape", "16x9"), "portrait": ("Portrait", "9x16")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    ap.add_argument("--format", default="both", choices=["landscape", "portrait", "both"])
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--allow-missing", action="store_true")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--props-only", action="store_true")
    a = ap.parse_args()

    job = resolve_job(a.job)
    plan, cfg, manifest = load_plan(job), load_config(), load_manifest(job)
    persona = load_persona(plan["persona"])
    voice = persona["voice"]
    prov = voice.get("provider")
    if prov == "heygen":
        render_settings = {"provider": prov, "voice_id": voice.get("heygen_voice_id"), "pron": voice.get("pronunciations")}
    else:
        render_settings = {"provider": prov, "fal": voice.get("fal"), "pron": voice.get("pronunciations")}
    studio = ROOT / cfg["paths"]["studio"]
    slug, fps = plan["slug"], cfg["fps"]
    pub = f"jobs/{slug}"
    dest = studio / "public" / "jobs" / slug

    problems, segs = [], []
    for s in plan["segments"]:
        m = manifest.get(s["id"])
        if not m or m.get("text_hash") != text_hash(s["text"]):
            problems.append(f"{s['id']}: no audio for the current text (run tts.py)")
            continue
        settings = render_settings
        if prov != "heygen":
            settings = {**render_settings, "default_voice": bool(m.get("default_voice", False))}
        render_settings_hash = text_hash(json.dumps(settings, sort_keys=True))
        if m.get("settings_hash") != render_settings_hash:
            problems.append(f"{s['id']}: manifest voice/settings changed since import (re-run tts.py --import)")
            continue
        audio_file = m.get("file") or ""
        try:
            resolved_audio = (job / audio_file).resolve()
            resolved_audio.relative_to((job / "audio").resolve())
        except ValueError:
            problems.append(f"{s['id']}: unsafe audio path {audio_file!r}")
            continue
        if not resolved_audio.is_file():
            problems.append(f"{s['id']}: audio file {audio_file} missing (run tts.py --import)")
            continue
        seg = {
            "id": s["id"], "type": s["type"],
            "durationInFrames": math.ceil((m["duration"] + cfg["segment_gap_seconds"]) * fps),
            "audio": f"{pub}/{m['file']}",
            "words": m.get("words", []),
            "onScreen": s.get("on_screen", ""),
        }
        if s["type"] == "presenter":
            clip = job / "presenter" / f"{s['id']}.mp4"
            if clip.is_file():
                seg["video"] = f"{pub}/presenter/{s['id']}.mp4"
            elif not a.allow_missing:
                problems.append(f"{s['id']}: presenter/{s['id']}.mp4 missing (HeyGen step, or use --allow-missing)")
        else:
            scene = dict(s.get("scene") or {})
            for f in ("image", "video", "video_portrait"):
                if scene.get(f):
                    if not (job / "assets" / scene[f]).is_file():
                        problems.append(f"{s['id']}: assets/{scene[f]} missing")
                    scene[f] = f"{pub}/assets/{scene[f]}"
            if scene.get("kind") == "cta" and not scene.get("handle"):
                scene["handle"] = persona["brand"].get("handle", "")
            seg["scene"] = scene
        segs.append(seg)
    music = plan.get("music")
    if music and not (job / "assets" / music).is_file():
        problems.append(f"music: assets/{music} missing")
    if problems:
        print("Cannot render:")
        for p in problems:
            print(f"  - {p}")
        return 1

    total = sum(s["durationInFrames"] for s in segs) / fps
    if total > cfg["max_seconds"]:
        print(f"Cannot render: {total:.0f}s is over the {cfg['max_seconds']}s cap")
        return 1

    b = persona["brand"]
    base = {
        "slug": slug, "title": plan.get("title", ""), "fps": fps,
        "theme": {k: b[k] for k in ("bg", "fg", "accent", "muted", "panel", "font")},
        "personaName": persona["display_name"], "showName": bool(b.get("show_name", False)), "handle": b.get("handle", ""),
        "music": f"{pub}/assets/{music}" if music else "", "musicVolume": plan.get("music_volume", 0.08),
        "segments": segs,
    }

    formats = ["landscape", "portrait"] if a.format == "both" else [a.format]
    props_files = {}
    for fmt in formats:
        pf = studio / "jobs" / f"{slug}-{fmt}.props.json"
        save_json(pf, {**base, "layout": fmt})
        props_files[fmt] = pf
    print(f"Props written for {', '.join(formats)} ({total:.0f}s).")
    if a.props_only:
        return 0

    if not (studio / "node_modules" / "remotion").is_dir():
        print(f"Remotion is not installed. Run once:  cd {cfg['paths']['studio']} && npm install")
        return 1
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        print("npx not found. Install Node.js 18+.")
        return 1

    if dest.exists():
        shutil.rmtree(dest)
    for sub in ("audio", "presenter", "assets"):
        if (job / sub).is_dir():
            shutil.copytree(job / sub, dest / sub, ignore=shutil.ignore_patterns("*.json"))

    (job / "out").mkdir(exist_ok=True)
    code = 0
    try:
        for fmt in formats:
            comp, tag = COMPS[fmt]
            out = job / "out" / f"{slug}-{tag}{'-preview' if a.preview else ''}.mp4"
            cmd = [npx, "remotion", "render", "src/index.ts", comp, str(out), f"--props={props_files[fmt]}"]
            if a.preview:
                cmd.append("--scale=0.5")
            print(" ".join(cmd))
            r = subprocess.run(cmd, cwd=studio)
            if r.returncode:
                print(f"Render failed for {fmt} (exit {r.returncode}).")
                code = 1
                break
            print(f"Wrote {out.relative_to(ROOT)}")
    finally:
        if not a.keep and dest.exists():
            shutil.rmtree(dest)
    return code


if __name__ == "__main__":
    sys.exit(main())
