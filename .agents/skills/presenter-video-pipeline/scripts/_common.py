"""Shared helpers for the presenter-video-pipeline scripts. Standard library only."""
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


def find_root() -> Path:
    for p in [SKILL_DIR, *SKILL_DIR.parents]:
        if (p / ".agents").is_dir():
            return p
    sys.exit("Could not find the workspace root (folder containing .agents/).")


ROOT = find_root()


def load_config() -> dict:
    cfg_path = SKILL_DIR / "pipeline.config.json"
    if not cfg_path.is_file():
        sys.exit(f"Missing {cfg_path}. Copy pipeline.config.json and configure it for this repo.")
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def persona_dir(persona_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", persona_id or ""):
        sys.exit("Persona ID must use lowercase letters, digits, and hyphens only.")
    d = SKILL_DIR / "personas" / persona_id
    if not d.is_dir():
        sys.exit(f"Persona '{persona_id}' not found in {d.parent}. Copy personas/persona.template.json to {d}/persona.json and fill it in.")
    return d


def load_persona(persona_id: str) -> dict:
    p = persona_dir(persona_id) / "persona.json"
    if not p.is_file():
        sys.exit(f"Persona config not found at {p}. Fill in personas/{persona_id}/persona.json from the template.")
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_job(arg: str) -> Path:
    """Accept a job folder, a segments.json path, or a bare slug."""
    p = Path(arg)
    if p.name == "segments.json":
        p = p.parent
    if not p.is_absolute():
        cand = ROOT / p
        if not cand.exists():
            cand = ROOT / load_config()["paths"]["videos"] / arg
        p = cand
    if not p.is_dir():
        sys.exit(f"Job folder not found: {p}")
    if not (p / "segments.json").is_file():
        sys.exit(f"No segments.json in {p}")
    return p


def load_plan(job_dir: Path) -> dict:
    try:
        return json.loads((job_dir / "segments.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"segments.json is not valid JSON: {e}")


def load_manifest(job_dir: Path) -> dict:
    f = job_dir / "audio" / "manifest.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def estimate_seconds(text: str, wps: float) -> float:
    return word_count(text) / wps


def segment_seconds(seg: dict, manifest: dict, cfg: dict):
    """Return (seconds, is_real). Real only if audio exists for the current text."""
    m = manifest.get(seg["id"])
    if m and m.get("text_hash") == text_hash(seg.get("text", "")):
        return float(m["duration"]), True
    return estimate_seconds(seg.get("text", ""), cfg["words_per_second"]), False


def heygen_credits(seconds: float, cfg: dict) -> int:
    """Estimate credits only when the recipient configured a verified plan rate."""
    rate = cfg.get("heygen", {}).get("credits_per_minute")
    if rate is None or float(rate) <= 0:
        raise ValueError("Set a verified positive heygen.credits_per_minute before estimating credits.")
    return math.ceil(seconds / 60 * float(rate))


# ---- WAV (PCM or float, any channel count) ----

def read_wav(data: bytes):
    """Return (fmt_chunk_bytes, sample_rate, block_align, pcm_bytes)."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a WAV file")
    pos, fmt, audio = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = body
        elif cid == b"data":
            audio = body
        pos += 8 + size + (size & 1)
    if fmt is None or audio is None:
        raise ValueError("WAV missing fmt or data chunk")
    _, channels, rate, _, block_align, _ = struct.unpack("<HHIIHH", fmt[:16])
    return fmt, rate, block_align, audio


def write_wav(path: Path, fmt: bytes, pcm: bytes) -> None:
    fmt_chunk = b"fmt " + struct.pack("<I", len(fmt)) + fmt + (b"\0" if len(fmt) & 1 else b"")
    data_chunk = b"data" + struct.pack("<I", len(pcm)) + pcm + (b"\0" if len(pcm) & 1 else b"")
    body = b"WAVE" + fmt_chunk + data_chunk
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


def wav_duration(path: Path) -> float:
    _, rate, block_align, pcm = read_wav(path.read_bytes())
    return len(pcm) / (rate * block_align)
