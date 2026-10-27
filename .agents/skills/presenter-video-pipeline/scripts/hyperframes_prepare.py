"""Prepare narration clips for a temporary HyperFrames composition workspace."""
from html import escape
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import re
import shutil

from _common import text_hash

SEGMENT_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
AUDIO_MARKER = "<!-- HYPERFRAMES_NARRATION_AUDIO -->"


def _assert_inside_job(job_dir: Path, path: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(job_dir)
    except ValueError as exc:
        raise ValueError(f"{label} resolves outside the job") from exc
    return resolved


def _copy_directory(job_dir: Path, source: Path, destination: Path, ancestors=frozenset()) -> None:
    """Materialize a job directory, resolving only safe in-job links and rejecting cycles."""
    resolved = _assert_inside_job(job_dir, source, "render input directory")
    if not resolved.is_dir():
        raise ValueError(f"render input directory is missing: {source}")
    stat = resolved.stat()
    identity = (stat.st_dev, stat.st_ino)
    if identity in ancestors:
        raise ValueError(f"render input directory contains a symlink cycle: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    next_ancestors = ancestors | {identity}
    for entry in sorted(resolved.iterdir(), key=lambda path: path.name):
        child = _assert_inside_job(job_dir, entry, f"render input {entry.name}")
        target = destination / entry.name
        if child.is_dir():
            _copy_directory(job_dir, child, target, next_ancestors)
        elif child.is_file():
            shutil.copy2(child, target)


def _digest_tree(job_dir: Path, source: Path, relative: Path, ancestors, digest) -> None:
    resolved = _assert_inside_job(job_dir, source, f"render input {relative}")
    label = relative.as_posix() if relative.parts else "."
    if resolved.is_dir():
        stat = resolved.stat()
        identity = (stat.st_dev, stat.st_ino)
        if identity in ancestors:
            raise ValueError(f"render input directory contains a symlink cycle: {source}")
        digest.update(b"directory\0" + label.encode("utf-8") + b"\0")
        next_ancestors = ancestors | {identity}
        for child in sorted(resolved.iterdir(), key=lambda path: path.name):
            _digest_tree(job_dir, child, relative / child.name, next_ancestors, digest)
        return
    if not resolved.is_file():
        raise ValueError(f"unsupported render input type: {source}")
    digest.update(b"file\0" + label.encode("utf-8") + b"\0")
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    digest.update(b"\0")


def _directory_digest(job_dir: Path, source: Path) -> str:
    digest = hashlib.sha256()
    _digest_tree(job_dir, source, Path(), frozenset(), digest)
    return digest.hexdigest()


def _audio_path(job_dir: Path, relative: str) -> tuple[Path, str]:
    if not isinstance(relative, str):
        raise ValueError("audio manifest file path must be a string")
    normalized = relative.replace("\\", "/")
    candidate = Path(normalized)
    windows = PureWindowsPath(relative)
    parts = normalized.split("/")
    if (
        not normalized
        or candidate.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or parts[0] != "audio"
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ValueError(f"unsafe audio manifest path {relative!r}; audio must stay under audio/")
    try:
        audio_root = _assert_inside_job(job_dir, job_dir / "audio", "audio directory")
        resolved = (job_dir / candidate).resolve(strict=False)
        resolved.relative_to(audio_root)
    except (OSError, ValueError) as exc:
        raise ValueError(f"unsafe audio manifest path {relative!r}; audio must stay under audio/") from exc
    if not resolved.is_file() or resolved.stat().st_size == 0:
        raise ValueError(f"audio file {relative!r} is missing or empty")
    return resolved, normalized


def _expected_settings_hash(voice: dict, entry: dict) -> str:
    provider = voice.get("provider")
    if provider == "heygen":
        settings = {
            "provider": provider,
            "voice_id": voice.get("heygen_voice_id"),
            "pron": voice.get("pronunciations"),
        }
    elif provider == "fal-chatterbox":
        settings = {
            "provider": provider,
            "fal": voice.get("fal"),
            "pron": voice.get("pronunciations"),
            "default_voice": bool(entry.get("default_voice", False)),
        }
    else:
        raise ValueError(f"unsupported narration provider {provider!r}")
    return text_hash(json.dumps(settings, sort_keys=True))


def narration_audio_markup(
    job_dir: Path,
    plan: dict,
    voice: dict,
    manifest: dict,
    gap_seconds: float,
    max_duration: float,
) -> str:
    """Return timed HTML audio clips, failing closed on stale or unsafe media."""
    job_dir = Path(job_dir).resolve()
    segments = plan.get("segments", [])
    if not isinstance(segments, list):
        raise ValueError("segments.json segments must be an array")
    if not isinstance(manifest, dict):
        raise ValueError("audio/manifest.json must contain an object")

    try:
        gap = float(gap_seconds)
        duration_limit = float(max_duration)
    except (TypeError, ValueError) as exc:
        raise ValueError("narration gap and storyboard duration must be numbers") from exc
    if not math.isfinite(gap) or gap < 0 or not math.isfinite(duration_limit) or duration_limit <= 0:
        raise ValueError("narration gap must be non-negative and storyboard duration must be positive")

    clips = []
    seen_ids = set()
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("every narration segment must be an object")
        text = segment.get("text", "")
        if text is None:
            continue
        if not isinstance(text, str):
            raise ValueError("narration segment text must be a string")
        if not text.strip():
            continue
        segment_id = segment.get("id", "")
        if not isinstance(segment_id, str) or not SEGMENT_ID.fullmatch(segment_id):
            raise ValueError("narration segment IDs must use lowercase letters, digits, and hyphens")
        if segment_id in seen_ids:
            raise ValueError(f"duplicate narration segment ID {segment_id!r}")
        seen_ids.add(segment_id)
        entry = manifest.get(segment_id)
        if not isinstance(entry, dict):
            raise ValueError(f"{segment_id}: audio manifest entry is missing")
        if entry.get("text_hash") != text_hash(text):
            raise ValueError(f"{segment_id}: audio manifest text hash is stale; regenerate or re-import narration")
        if entry.get("settings_hash") != _expected_settings_hash(voice, entry):
            raise ValueError(f"{segment_id}: audio manifest voice/settings hash is stale; re-import narration")
        audio_file = entry.get("file")
        if not isinstance(audio_file, str):
            raise ValueError(f"{segment_id}: audio manifest file must be a string")
        _, relative = _audio_path(job_dir, audio_file)
        raw_duration = entry.get("duration")
        if isinstance(raw_duration, bool) or not isinstance(raw_duration, (int, float, str)):
            raise ValueError(f"{segment_id}: manifest duration must be a positive number")
        try:
            clip_duration = float(raw_duration)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{segment_id}: manifest duration must be a positive number") from exc
        if not math.isfinite(clip_duration) or clip_duration <= 0:
            raise ValueError(f"{segment_id}: manifest duration must be a positive number")
        clips.append((segment_id, relative, clip_duration))

    cursor = 0.0
    tags = []
    for index, (segment_id, relative, clip_duration) in enumerate(clips):
        end = cursor + clip_duration
        if end > duration_limit + 1e-6:
            raise ValueError(
                f"narration segment {segment_id!r} ends at {end:.3f}s, beyond storyboard duration {duration_limit:.3f}s"
            )
        start_text = _format_seconds(cursor)
        duration_text = _format_seconds(clip_duration)
        tags.append(
            f'<audio id="narration-{escape(segment_id, quote=True)}" '
            f'src="{escape(relative, quote=True)}" data-start="{start_text}" '
            f'data-duration="{duration_text}" data-track-index="0"></audio>'
        )
        cursor = end + (gap if index < len(clips) - 1 else 0.0)
    return "\n".join(tags)


def prepare_workspace(job_dir: Path, workspace: Path, audio_markup: str) -> None:
    """Create an isolated project root; never edit source job files in place."""
    job_dir, workspace = Path(job_dir).resolve(), Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    source_index = job_dir / "index.html"
    if source_index.exists():
        _assert_inside_job(job_dir, source_index, "index.html")
    if not source_index.is_file():
        raise ValueError("HyperFrames job is missing index.html")
    index_html = source_index.read_text(encoding="utf-8")
    marker_count = index_html.count(AUDIO_MARKER)
    if audio_markup and marker_count != 1:
        raise ValueError(f"index.html must contain exactly one {AUDIO_MARKER} marker for narration")
    if marker_count > 1:
        raise ValueError(f"index.html contains multiple {AUDIO_MARKER} markers")
    if marker_count == 1:
        index_html = index_html.replace(AUDIO_MARKER, audio_markup)
    (workspace / "index.html").write_text(index_html, encoding="utf-8")

    for directory in ("assets", "audio", "compositions"):
        source = job_dir / directory
        if not source.is_dir():
            continue
        resolved_source = _assert_inside_job(job_dir, source, f"{directory} directory")
        destination = workspace / directory
        source_digest = _directory_digest(job_dir, resolved_source)
        _copy_directory(job_dir, resolved_source, destination)
        snapshot_digest = _directory_digest(workspace, destination)
        if snapshot_digest != source_digest:
            raise ValueError(f"render input directory changed while copying: {directory}")

    config = job_dir / "hyperframes.json"
    if config.is_file():
        safe_config = _assert_inside_job(job_dir, config, "hyperframes.json")
        shutil.copy2(safe_config, workspace / config.name)
    for suffix in (".css", ".js", ".mjs"):
        for source in job_dir.glob(f"*{suffix}"):
            if source.is_file():
                safe_source = _assert_inside_job(job_dir, source, f"{source.name}")
                shutil.copy2(safe_source, workspace / source.name)


def _format_seconds(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".") or "0"
