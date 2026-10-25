"""Narration for every segment, in the persona's voice.

Usage:
  python tts.py <job> [--dry-run] [--only s01,s03] [--force] [--default-voice]
  python tts.py <job> --todo      (heygen voice) list segments that need audio, as JSON
  python tts.py <job> --import    (heygen voice) register files saved as audio/<id>.mp3|wav

  --dry-run        print what would be generated and the estimated cost, make no calls
  --only           just these segment ids
  --force          redo even if text and voice settings are unchanged
  --default-voice  fal only: stock voice (for testing before the reference clip exists)

Providers (persona.json voice.provider):
  heygen          audio comes from the HeyGen MCP create_speech tool. The agent calls it and saves
                  the files, then --import converts them to WAV and writes the manifest.
  fal-chatterbox  this script calls fal directly. Needs FAL_KEY in the environment.

Writes audio/<id>.wav and audio/manifest.json (duration, word timings, hashes).
Never pass an API key on the command line.
"""
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (ROOT, load_config, load_manifest, load_persona, load_plan,  # noqa: E402
                     persona_dir, read_wav, resolve_job, save_json, text_hash, wav_duration, write_wav)

AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac")


def estimate_tts_cost(char_count: int, cfg: dict) -> float | None:
    """Return an estimated cost only when the recipient configured a verified rate."""
    rate = cfg.get("tts", {}).get("price_per_1000_chars")
    if rate is None:
        return None
    rate = float(rate)
    if rate < 0:
        raise ValueError("tts.price_per_1000_chars must be non-negative")
    return char_count / 1000 * rate


def chunk_text(text: str, limit: int) -> list[str]:
    """Split at sentence ends, then commas, then spaces, keeping each chunk <= limit."""
    sentences = re.split(r"(?<=[.?!])\s+", text.strip())
    pieces = []
    for s in sentences:
        while len(s) > limit:
            cut = s.rfind(", ", 0, limit)
            cut = cut + 1 if cut > limit // 3 else s.rfind(" ", 0, limit)
            if cut <= 0:
                cut = limit
            pieces.append(s[:cut].strip())
            s = s[cut:].strip()
        if s:
            pieces.append(s)
    chunks, cur = [], ""
    for p in pieces:
        if cur and len(cur) + 1 + len(p) > limit:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def apply_pronunciations(text: str, mapping: dict) -> str:
    for written, spoken in mapping.items():
        text = re.sub(rf"\b{re.escape(written)}\b", spoken, text)
    return text


def estimate_words(text: str, start: float, end: float) -> list[dict]:
    words = text.split()
    weights = [len(w) + 1 for w in words]
    total, t, out = sum(weights) or 1, start, []
    for w, wt in zip(words, weights):
        d = (end - start) * wt / total
        out.append({"text": w, "start": round(t, 3), "end": round(t + d, 3)})
        t += d
    return out


# ---------------- fal Chatterbox ----------------

def http_json(url: str, body: dict, key: str, timeout: int = 300) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Key {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=300) as r:
        return r.read()


def synth_fal_chatterbox(text: str, fal: dict, voice_ref: str | None, key: str) -> bytes:
    body = {
        "text": text,
        "exaggeration": fal.get("exaggeration", 0.5),
        "temperature": fal.get("temperature", 0.7),
        "cfg_scale": fal.get("cfg_scale", 0.5),
    }
    if fal.get("seed") is not None:
        body["seed"] = fal["seed"]
    if voice_ref:
        body["voice"] = voice_ref
        body["custom_audio_language"] = fal.get("language", "english")
    else:
        body["voice"] = fal.get("language", "english")
    last = None
    for attempt in range(3):
        try:
            out = http_json(f"https://fal.run/{fal['model']}", body, key)
            return download(out["audio"]["url"])
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:400]
            if e.code < 500 and e.code != 429:
                sys.exit(f"fal returned {e.code}: {detail}")
            last = f"{e.code}: {detail}"
        except (urllib.error.URLError, TimeoutError, KeyError) as e:
            last = repr(e)
        time.sleep(5 * (attempt + 1))
    sys.exit(f"fal request failed after 3 attempts: {last}")


PROVIDERS = {"fal-chatterbox": synth_fal_chatterbox}


def voice_reference(persona_id: str, fal: dict) -> str:
    if fal.get("reference_audio_url"):
        return fal["reference_audio_url"]
    ref = persona_dir(persona_id) / fal.get("reference_audio", "voice/reference.wav")
    if not ref.is_file():
        sys.exit(f"Voice reference not found: {ref}\nAdd it (see README.md) or run with --default-voice for a test.")
    data = ref.read_bytes()
    if len(data) > 5_000_000:
        print(f"WARN  reference clip is {len(data) / 1e6:.1f} MB; trim to 10-20 s or set reference_audio_url")
    return "data:audio/wav;base64," + base64.b64encode(data).decode()


def fal_audio(a, job, plan, todo, voice, settings_hash, manifest, cfg) -> int:
    if getattr(a, "todo", False):
        sys.exit("--todo is only supported with the HeyGen provider; use --dry-run for FAL.")
    fal, pron = voice.get("fal", {}), voice.get("pronunciations", {})
    chars = sum(len(apply_pronunciations(s["text"], pron)) for s in todo)
    cost = estimate_tts_cost(chars, cfg)
    if cost is None:
        print(f"{len(todo)} segment(s) to generate, {chars} characters, cost unknown (configure a verified tts.price_per_1000_chars rate)")
    else:
        print(f"{len(todo)} segment(s) to generate, {chars} characters, est. ${cost:.3f}")
    if a.dry_run or not todo:
        return 0
    if cost is None:
        sys.exit("FAL cost is unknown. Configure a verified tts.price_per_1000_chars rate before billable generation.")
    key = os.environ.get("FAL_KEY")
    if not key:
        sys.exit("FAL_KEY is not set. See README.md.")
    ref = None if a.default_voice else voice_reference(plan["persona"], fal)
    limit = min(cfg["tts"]["max_chars_per_request"], 300)
    gap = cfg["tts"]["chunk_gap_seconds"]
    for s in todo:
        fmt, pcm, words, t = None, b"", [], 0.0
        for chunk in chunk_text(s["text"], limit):
            spoken = apply_pronunciations(chunk, pron)
            if len(spoken) > 300:
                sys.exit(f"{s['id']}: chunk over 300 chars after pronunciations; shorten the sentence")
            f, rate, block, data = read_wav(synth_fal_chatterbox(spoken, fal, ref, key))
            if fmt is None:
                fmt, srate, sblock = f, rate, block
            elif (rate, block) != (srate, sblock):
                sys.exit(f"{s['id']}: provider returned mixed audio formats")
            if pcm:
                silence = b"\0" * (int(gap * srate) * sblock)
                pcm += silence
                t += len(silence) / (srate * sblock)
            dur = len(data) / (srate * sblock)
            words += estimate_words(chunk, t, t + dur)
            pcm += data
            t += dur
        write_wav(job / "audio" / f"{s['id']}.wav", fmt, pcm)
        manifest[s["id"]] = {
            "file": f"audio/{s['id']}.wav", "duration": round(t, 3), "text_hash": text_hash(s["text"]),
            "settings_hash": settings_hash, "default_voice": bool(a.default_voice),
            "timing": "estimated-within-chunks", "words": words,
        }
        save_json(job / "audio" / "manifest.json", manifest)
        print(f"{s['id']}: {t:.1f}s")
    print("Done. Re-run segment-check.py to see real durations.")
    return 0


# ---------------- HeyGen voice (via MCP) ----------------

def to_wav(src: Path, dst: Path, cfg: dict) -> None:
    """Convert with the ffmpeg that ships with Remotion (npx remotion ffmpeg)."""
    studio = ROOT / cfg["paths"]["studio"]
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx or not (studio / "node_modules" / "remotion").is_dir():
        sys.exit(f"Need Remotion installed to convert {src.name} to WAV (cd {cfg['paths']['studio']} && npm install)")
    tmp = dst.with_name(dst.stem + ".tmp.wav")
    r = subprocess.run([npx, "remotion", "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
                        "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(tmp)], cwd=studio)
    if r.returncode or not tmp.is_file():
        sys.exit(f"ffmpeg could not convert {src}")
    tmp.replace(dst)


def heygen_audio(a, job, todo, voice, settings_hash, manifest, cfg) -> int:
    pron = voice.get("pronunciations", {})
    if not a.import_audio:
        items = [{"id": s["id"], "text": apply_pronunciations(s["text"], pron), "save_as": f"audio/{s['id']}.mp3"}
                 for s in todo]
        if a.todo or a.dry_run:
            print(json.dumps({"voice_id": voice.get("heygen_voice_id"), "segments": items}, indent=2, ensure_ascii=False))
        else:
            paths = ", ".join(i["save_as"] for i in items)
            print(f"{len(items)} segment(s) need audio. Voice provider is heygen: make each with the HeyGen MCP "
                  f"create_speech tool (voice {voice.get('heygen_voice_id') or '<set heygen_voice_id>'}), save each "
                  f"audio file to {paths}, then run with --import. Use --todo for the list.")
        return 0
    if not voice.get("heygen_voice_id"):
        sys.exit("Set voice.heygen_voice_id in persona.json first.")
    done, missing = 0, []
    for s in todo:
        src = next((job / "audio" / f"{s['id']}{e}" for e in AUDIO_EXTS if (job / "audio" / f"{s['id']}{e}").is_file()), None)
        if not src:
            missing.append(s["id"])
            continue
        dst = job / "audio" / f"{s['id']}.wav"
        if src.suffix != ".wav":
            to_wav(src, dst, cfg)
            src.unlink()
        dur = wav_duration(dst)
        manifest[s["id"]] = {
            "file": f"audio/{s['id']}.wav", "duration": round(dur, 3), "text_hash": text_hash(s["text"]),
            "settings_hash": settings_hash, "timing": "estimated-whole-segment",
            "words": estimate_words(apply_pronunciations(s["text"], pron), 0.0, dur),
        }
        done += 1
        print(f"{s['id']}: {dur:.1f}s")
    save_json(job / "audio" / "manifest.json", manifest)
    if missing:
        print(f"Still missing audio for: {', '.join(missing)}")
        return 1
    print(f"Imported {done}. Re-run segment-check.py to see real durations.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--default-voice", action="store_true")
    ap.add_argument("--todo", action="store_true")
    ap.add_argument("--import", dest="import_audio", action="store_true")
    a = ap.parse_args()

    job = resolve_job(a.job)
    plan, cfg = load_plan(job), load_config()
    voice = load_persona(plan["persona"])["voice"]
    prov = voice.get("provider")
    if prov not in ("heygen", *PROVIDERS):
        sys.exit(f"Unknown voice provider '{prov}'. Known: heygen, {', '.join(PROVIDERS)}")
    if prov == "heygen":
        settings = {"provider": prov, "voice_id": voice.get("heygen_voice_id"), "pron": voice.get("pronunciations")}
    else:
        settings = {"provider": prov, "fal": voice.get("fal"), "pron": voice.get("pronunciations"),
                    "default_voice": a.default_voice}
    settings_hash = text_hash(json.dumps(settings, sort_keys=True))
    manifest = load_manifest(job)
    only = set(a.only.split(",")) if a.only else None

    todo = []
    for s in plan["segments"]:
        if only and s["id"] not in only:
            continue
        m = manifest.get(s["id"])
        fresh = (m and m.get("text_hash") == text_hash(s["text"]) and m.get("settings_hash") == settings_hash
                 and (job / m["file"]).is_file())
        if a.force or not fresh:
            todo.append(s)

    if prov == "heygen":
        return heygen_audio(a, job, todo, voice, settings_hash, manifest, cfg)
    return fal_audio(a, job, plan, todo, voice, settings_hash, manifest, cfg)


if __name__ == "__main__":
    sys.exit(main())
