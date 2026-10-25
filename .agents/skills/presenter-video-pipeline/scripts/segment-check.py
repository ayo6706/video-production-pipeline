"""Validate a video plan (segments.json).

Usage: python segment-check.py <job folder | segments.json | slug>
Exit 0 = no FAIL (warnings allowed). Exit 1 = at least one FAIL.
Uses real audio durations from audio/manifest.json when they match the current text,
otherwise estimates from words_per_second.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (load_config, load_manifest, load_plan, resolve_job,  # noqa: E402
                     segment_seconds, word_count, heygen_credits, SKILL_DIR, ROOT)

# kind -> (required fields, {field: max chars}, source_ref required)
SCENE_RULES = {
    "title": (["headline"], {"headline": 60, "kicker": 40}, False),
    "stat": (["value", "label"], {"value": 16, "label": 80, "before": 24}, True),
    "points": (["items"], {"heading": 50}, True),
    "quote": (["text", "attribution"], {"text": 160, "attribution": 80}, True),
    "screenshot": (["image"], {"caption": 90}, False),
    "clip": (["video"], {"caption": 90}, False),
    "query": (["text"], {"text": 90, "label": 40}, False),
    "cta": (["line"], {"line": 90, "handle": 40}, False),
}
SPOKEN_SYMBOLS = re.compile(r"[$%&/#@+=]|\bAUD\b|\bUSD\b")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    job = resolve_job(sys.argv[1])
    plan, cfg, manifest = load_plan(job), load_config(), load_manifest(job)
    fails, warns = [], []

    for key in ("slug", "persona", "lane", "segments"):
        if not plan.get(key):
            fails.append(f"plan: missing '{key}'")
    if plan.get("persona") and not (SKILL_DIR / "personas" / plan["persona"]).is_dir():
        fails.append(f"plan: persona '{plan['persona']}' has no folder in personas/")
    if plan.get("lane") and not (SKILL_DIR / "lanes" / f"{plan['lane']}.md").is_file():
        fails.append(f"plan: lane '{plan['lane']}' has no file in lanes/")
    src = plan.get("source")
    if not src:
        fails.append("plan: missing 'source' (facts must come from a lane source)")
    elif not (ROOT / src).exists():
        warns.append(f"plan: source not found at {src}")

    segs = plan.get("segments") or []
    seen, rows = set(), []
    total = presenter = 0.0
    all_real = True
    credits = 0
    for i, s in enumerate(segs):
        sid = s.get("id", f"#{i + 1}")
        if sid in seen:
            fails.append(f"{sid}: duplicate id")
        seen.add(sid)
        if not re.fullmatch(r"s\d{2,3}[a-z]?", str(sid)):
            warns.append(f"{sid}: id should look like s01")
        text = (s.get("text") or "").strip()
        typ = s.get("type")
        if typ not in ("presenter", "screen"):
            fails.append(f"{sid}: type must be 'presenter' or 'screen'")
        if not text:
            fails.append(f"{sid}: empty text (every segment is narrated)")
        if "—" in text or "–" in text:
            fails.append(f"{sid}: em/en dash in spoken text")
        if re.search(r"\w: \w", text):
            fails.append(f"{sid}: mid-sentence colon in spoken text")
        if SPOKEN_SYMBOLS.search(text):
            warns.append(f"{sid}: symbol/abbreviation in spoken text ({SPOKEN_SYMBOLS.search(text).group()}); write it as spoken")
        if re.search(r"\[(ASK-AUTHOR|VERIFY)", text):
            warns.append(f"{sid}: unresolved placeholder in spoken text")

        secs, real = segment_seconds(s, manifest, cfg)
        all_real &= real
        total += secs
        if typ == "presenter":
            presenter += secs
            if credits is not None:
                try:
                    credits += heygen_credits(secs, cfg)
                except ValueError:
                    credits = None
            if s.get("scene"):
                warns.append(f"{sid}: presenter segment has a scene (ignored)")
            if len(s.get("on_screen", "")) > 60:
                fails.append(f"{sid}: on_screen over 60 chars")
        if secs > cfg["segment_warn_seconds"]:
            warns.append(f"{sid}: {secs:.0f}s is long for one segment; consider splitting")
        if typ == "screen":
            if secs > cfg["screen_segment_warn_seconds"]:
                warns.append(f"{sid}: screen segment {secs:.0f}s may feel static; split the scene")
            sc = s.get("scene") or {}
            kind = sc.get("kind")
            if kind not in SCENE_RULES:
                fails.append(f"{sid}: scene.kind must be one of {', '.join(SCENE_RULES)}")
            else:
                req, limits, need_ref = SCENE_RULES[kind]
                for f in req:
                    if not sc.get(f):
                        fails.append(f"{sid}: {kind} scene missing '{f}'")
                for f, n in limits.items():
                    if isinstance(sc.get(f), str) and len(sc[f]) > n:
                        fails.append(f"{sid}: {kind}.{f} is {len(sc[f])} chars (max {n})")
                if need_ref and not sc.get("source_ref"):
                    fails.append(f"{sid}: {kind} scene needs source_ref (claim ID)")
                if kind == "points":
                    items = sc.get("items") or []
                    if not 1 <= len(items) <= 3:
                        fails.append(f"{sid}: points needs 1-3 items")
                    for it in items:
                        if len(it) > 48:
                            fails.append(f"{sid}: point over 48 chars: '{it[:30]}...'")
                for f in ("image", "video", "video_portrait"):
                    if sc.get(f) and not (job / "assets" / sc[f]).is_file():
                        fails.append(f"{sid}: assets/{sc[f]} not found")
                for v in sc.values():
                    if isinstance(v, str) and "—" in v:
                        fails.append(f"{sid}: em dash in on-screen text")
        rows.append((sid, typ or "?", word_count(text), secs, "real" if real else "est"))

    if segs:
        first = segs[0]
        first_sentence = re.split(r"(?<=[.?!])\s", first.get("text", "").strip())[0]
        if word_count(first_sentence) > cfg["hook_max_words"]:
            warns.append(f"hook: first sentence is {word_count(first_sentence)} words (guide {cfg['hook_max_words']}); fine if it is an approved line")
        if first.get("type") != "presenter":
            warns.append("hook: first segment is not presenter")

    if total > cfg["max_seconds"]:
        fails.append(f"length: {total:.0f}s over the {cfg['max_seconds']}s cap")
    share = presenter / total if total else 0
    if share > cfg["max_presenter_share"]:
        fails.append(f"presenter share {share:.0%} over max {cfg['max_presenter_share']:.0%}")
    elif share > cfg["target_presenter_share"] + 0.05:
        warns.append(f"presenter share {share:.0%} above target {cfg['target_presenter_share']:.0%} (costs more credits)")

    print(f"{'id':<6}{'type':<11}{'words':>6}{'secs':>7}  timing")
    for sid, typ, w, secs, t in rows:
        print(f"{sid:<6}{typ:<11}{w:>6}{secs:>7.1f}  {t}")
    basis = "real audio" if all_real and segs else "estimated"
    credit_label = f"HeyGen credit estimate {credits}" if credits is not None else "HeyGen credit estimate not configured"
    print(f"\nTotal {total:.0f}s ({total / 60:.1f} min, {basis}) | presenter {presenter:.0f}s ({share:.0%}) | {credit_label}")
    for w in warns:
        print(f"WARN  {w}")
    for f in fails:
        print(f"FAIL  {f}")
    print("RESULT:", "FAIL" if fails else "PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
