"""HeyGen credit control.

Usage:
  python credit-budget.py estimate <job> [--remaining N] [--floor N]
      Estimate credits for this video's presenter segments. N = balance from the
      HeyGen MCP get_current_user. Exit 1 = over budget or below the warning floor.
      --floor overrides heygen.warn_below_credits (use 0 on the free plan).
  python credit-budget.py log <job> --remaining N [--before N] [--note "..."]
      Record actual use after the clips finish (before defaults to the balance saved by estimate).
  python credit-budget.py status
      Credits used this month from the ledger.
"""
import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (ROOT, heygen_credits, load_config, load_manifest, load_plan,  # noqa: E402
                     resolve_job, segment_seconds)

FIELDS = ["date", "slug", "presenter_seconds", "estimated_credits", "credits_before", "credits_after", "credits_used", "note"]


def ledger_path(cfg) -> Path:
    return ROOT / cfg["paths"]["videos"] / "credit-ledger.csv"


def month_used(cfg) -> int:
    p, month, used = ledger_path(cfg), dt.date.today().strftime("%Y-%m"), 0
    if p.is_file():
        with p.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["date"].startswith(month) and row["credits_used"]:
                    used += int(float(row["credits_used"]))
    return used


def presenter_estimate(job, cfg):
    plan, manifest = load_plan(job), load_manifest(job)
    secs = credits = 0
    real = True
    for s in plan["segments"]:
        if s.get("type") == "presenter":
            t, r = segment_seconds(s, manifest, cfg)
            secs += t
            if credits is not None:
                try:
                    credits += heygen_credits(t, cfg)
                except ValueError:
                    credits = None
            real &= r
    return plan, secs, credits, real


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["estimate", "log", "status"])
    ap.add_argument("job", nargs="?")
    ap.add_argument("--remaining", type=int)
    ap.add_argument("--before", type=int)
    ap.add_argument("--note", default="")
    ap.add_argument("--floor", type=int)
    a = ap.parse_args()
    cfg = load_config()
    hg = cfg["heygen"]

    if a.cmd == "status":
        used = month_used(cfg)
        if hg.get("monthly_credits") is None:
            print(f"{dt.date.today():%Y-%m}: {used} credits logged; monthly allowance not configured")
        else:
            monthly = int(hg["monthly_credits"])
            print(f"{dt.date.today():%Y-%m}: {used} credits logged of {monthly} ({monthly - used} left by ledger)")
        return 0
    if not a.job:
        sys.exit("job is required")
    job = resolve_job(a.job)
    plan, secs, est, real = presenter_estimate(job, cfg)

    if a.cmd == "estimate":
        if est is None:
            print("BLOCK: configure a verified heygen.credits_per_minute before estimating or generating.")
            return 2
        if a.remaining is not None:
            available, basis = a.remaining, "HeyGen balance (MCP get_current_user)"
        elif hg.get("monthly_credits") is None:
            print("BLOCK: monthly allowance is not configured; pass --remaining with the current HeyGen balance.")
            return 2
        else:
            available, basis = int(hg["monthly_credits"]) - month_used(cfg), "ledger (pass --remaining for the real balance)"
        after = available - est
        print(f"Presenter time {secs:.0f}s ({'real audio' if real else 'estimated'}) -> ~{est} credits at {hg['credits_per_minute']}/min")
        print(f"Available {available} ({basis}) -> {after} after this video")
        (job / "presenter").mkdir(exist_ok=True)
        (job / "presenter" / "budget.json").write_text(json.dumps(
            {"estimated_credits": est, "presenter_seconds": round(secs, 1), "credits_before": a.remaining}), encoding="utf-8")
        if est > available:
            print("BLOCK: not enough credits. Ask the user before generating.")
            return 1
        floor = a.floor if a.floor is not None else hg.get("warn_below_credits")
        if floor is not None and after < floor:
            print(f"BLOCK: would leave fewer than {floor} credits. Ask the user before generating.")
            return 1
        if not real:
            print("Note: estimate uses word count. Run tts.py first for real durations.")
        print("OK")
        return 0

    if a.remaining is None:
        sys.exit("log needs --remaining (balance after the clips finished)")
    before = a.before
    bfile = job / "presenter" / "budget.json"
    if before is None and bfile.is_file():
        before = json.loads(bfile.read_text(encoding="utf-8")).get("credits_before")
    used = (before - a.remaining) if before is not None else ""
    p = ledger_path(cfg)
    new = not p.is_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({"date": dt.date.today().isoformat(), "slug": plan["slug"], "presenter_seconds": round(secs, 1),
                    "estimated_credits": est, "credits_before": before if before is not None else "",
                    "credits_after": a.remaining, "credits_used": used, "note": a.note})
    print(f"Logged: used {used if used != '' else 'unknown (no before balance)'} credits, estimate was {est}")
    if used != "" and est and abs(used - est) / est > 0.25:
        print(f"Actual differs from estimate by more than 25%. Update heygen.credits_per_minute in pipeline.config.json "
              f"(actual rate ~{used / (secs / 60):.1f}/min).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
