"""Create and enforce a hash-bound human editorial review for a preview."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile


GLOBAL_CHECKS = {
    "full_video_watched": "I watched the complete preview, not only selected frames.",
    "audio_sync_and_levels": "Narration, timing, and audio levels were checked by listening.",
    "visual_variety_tracks_story": "The visuals change with the idea and avoid repetitive filler.",
    "transitions_restrained": "Cuts/transitions are restrained and let each action finish and remain readable.",
}
FRAME_CHECKS = {
    "captions_clear_of_key_content": "Captions do not cover important source content or actions.",
    "source_content_readable_on_phone": "Source text and evidence are readable at phone size.",
    "action_completes_before_cut": "The depicted action completes and its result holds before the cut.",
    "visual_supports_narration": "The visual directly supports the spoken beat or idea.",
}
FRAME_HEADING = re.compile(r"^##\s+Frame\s+\d+\s*[—–:-]\s*(.+?)\s*$")
FIELD_LINE = re.compile(r"^\s*-\s*([a-z][a-z0-9_-]*):\s*(.*?)\s*$")
SECONDS = re.compile(r"^(\d+(?:\.\d+)?)\s*s?$", re.IGNORECASE)
HASH = re.compile(r"^[0-9a-f]{64}$")
EXCLUDED_JOB_DIRS = {".git", ".hyperframes", "out"}
PIPELINE_ROOT = Path(__file__).resolve().parents[4]
PIPELINE_INPUTS = (
    ".agents/skills/presenter-video-pipeline/pipeline.config.json",
    ".agents/skills/presenter-video-pipeline/scripts/_common.py",
    ".agents/skills/presenter-video-pipeline/scripts/render.py",
    ".agents/skills/presenter-video-pipeline/scripts/storyboard_check.py",
    ".agents/skills/presenter-video-pipeline/scripts/hyperframes_prepare.py",
    ".agents/skills/presenter-video-pipeline/scripts/hyperframes_render.py",
    ".agents/skills/presenter-video-pipeline/scripts/editorial_review.py",
    "tools/hyperframes/package.json",
    "tools/hyperframes/package-lock.json",
)


def preview_sha256(preview: Path) -> str:
    """Hash a rendered preview without loading it all into memory."""
    digest = hashlib.sha256()
    with Path(preview).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raise_walk_error(error: OSError) -> None:
    raise error


def _inside_job(job: Path, path: Path) -> Path:
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(job)
    except ValueError as exc:
        raise ValueError(f"render input resolves outside the job: {path}") from exc
    if relative.parts and relative.parts[0] in EXCLUDED_JOB_DIRS:
        raise ValueError(f"render input resolves into an output directory: {path}")
    return resolved


def _update_digest(digest, label: str, path: Path) -> None:
    digest.update(label.encode("utf-8"))
    digest.update(b"\0")
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    digest.update(b"\0")


def render_input_fingerprint(job: Path) -> str:
    """Hash every job input and the renderer/config files that can affect output."""
    job = Path(job).resolve(strict=True)
    if not job.is_dir():
        raise ValueError("render job must be a directory")
    for name in ("out", ".hyperframes"):
        if (job / name).is_symlink():
            raise ValueError(f"job {name}/ output directory must not be a symlink")

    digest = hashlib.sha256()
    seen_directories = set()
    for current, directories, filenames in os.walk(
        job, topdown=True, followlinks=True, onerror=_raise_walk_error
    ):
        current_path = Path(current)
        resolved_current = current_path.resolve(strict=True)
        try:
            resolved_current.relative_to(job)
        except ValueError as exc:
            raise ValueError(f"render input directory resolves outside the job: {current_path}") from exc
        stat = resolved_current.stat()
        identity = (stat.st_dev, stat.st_ino)
        if identity in seen_directories:
            directories[:] = []
            continue
        seen_directories.add(identity)

        relative_dir = current_path.relative_to(job)
        if not relative_dir.parts:
            directories[:] = [name for name in directories if name not in EXCLUDED_JOB_DIRS]
        directories.sort()
        for name in directories:
            directory_path = current_path / name
            resolved_directory = _inside_job(job, directory_path)
            if directory_path.is_symlink():
                target = resolved_directory.relative_to(job).as_posix()
                digest.update(b"symlink-directory\0")
                digest.update(directory_path.relative_to(job).as_posix().encode("utf-8"))
                digest.update(b"\0")
                digest.update(target.encode("utf-8"))
                digest.update(b"\0")

        for name in sorted(filenames):
            source = current_path / name
            resolved = _inside_job(job, source)
            if resolved.is_file():
                _update_digest(digest, source.relative_to(job).as_posix(), resolved)

    for relative in PIPELINE_INPUTS:
        source = PIPELINE_ROOT / relative
        try:
            resolved = source.resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"required renderer input is missing: {relative}") from exc
        if not resolved.is_file():
            raise ValueError(f"required renderer input is not a file: {relative}")
        _update_digest(digest, f"pipeline:{relative}", resolved)

    plan_path = job / "segments.json"
    if plan_path.is_file():
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read segments.json while fingerprinting: {exc}") from exc
        persona_id = plan.get("persona") if isinstance(plan, dict) else None
        if persona_id:
            if not isinstance(persona_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", persona_id):
                raise ValueError("segments.json has an invalid persona ID")
            persona_root = PIPELINE_ROOT / ".agents/skills/presenter-video-pipeline/personas"
            persona_path = persona_root / persona_id / "persona.json"
            try:
                resolved_persona = persona_path.resolve(strict=True)
                resolved_persona.relative_to(persona_root.resolve(strict=True))
            except (OSError, ValueError) as exc:
                raise ValueError(f"active persona config is missing or unsafe: {persona_id}") from exc
            if not resolved_persona.is_file():
                raise ValueError(f"active persona config is not a file: {persona_id}")
            _update_digest(digest, f"pipeline:persona:{persona_id}", resolved_persona)
    return digest.hexdigest()


def storyboard_frames(job: Path) -> list[dict]:
    """Return stable frame identifiers and timing for the review checklist."""
    path = Path(job) / "STORYBOARD.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    frames = []
    current = None
    for line in lines:
        heading = FRAME_HEADING.match(line)
        if heading:
            current = {"title": heading.group(1), "fields": {}}
            frames.append(current)
            continue
        if current is None:
            continue
        field = FIELD_LINE.match(line)
        if field:
            current["fields"][field.group(1)] = field.group(2).strip().strip("\"'")

    result = []
    for frame in frames:
        fields = frame["fields"]
        start = _parse_seconds(fields.get("start", ""))
        duration = _parse_seconds(fields.get("duration", ""))
        frame_id = fields.get("id", "")
        if frame_id and start is not None and duration is not None:
            result.append({"id": frame_id, "title": frame["title"], "start": start, "duration": duration})
    return result


def _parse_seconds(value: str) -> float | None:
    match = SECONDS.fullmatch(value.strip())
    return float(match.group(1)) if match else None


def _safe_preview(job: Path, preview: Path) -> Path:
    job = Path(job).resolve(strict=True)
    output_dir = job / "out"
    if output_dir.is_symlink():
        raise ValueError("job out/ directory must not be a symlink")
    output_dir = output_dir.resolve(strict=True)
    try:
        output_dir.relative_to(job)
    except ValueError as exc:
        raise ValueError("job out/ directory resolves outside the job") from exc
    preview = Path(preview).resolve(strict=True)
    try:
        preview.relative_to(output_dir)
    except ValueError as exc:
        raise ValueError("preview must be inside the job's out/ directory") from exc
    if not preview.is_file() or preview.stat().st_size == 0:
        raise ValueError("preview file is missing or empty")
    return preview


def _packet_path(job: Path) -> Path:
    return Path(job) / "out" / "editorial-review-packet.json"


def _safe_output_file(job: Path, path: Path) -> Path:
    """Resolve an output destination inside the job and reject symlink paths."""
    job = Path(job).resolve(strict=True)
    path = Path(path)
    if path.parent.is_symlink():
        raise ValueError("job out/ directory must not be a symlink")
    parent = path.parent.resolve(strict=True)
    try:
        parent.relative_to(job)
    except ValueError as exc:
        raise ValueError("editorial review output resolves outside the job") from exc
    if path.is_symlink():
        raise ValueError(f"{path.name} output must not be a symlink")
    return parent / path.name


def _atomic_write_text(job: Path, path: Path, content: str) -> None:
    """Atomically write a review artifact without following destination symlinks."""
    path = _safe_output_file(job, path)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}-", suffix=".tmp", delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(content)
        if path.is_symlink():
            raise ValueError(f"{path.name} output became a symlink while writing")
        os.replace(temp_name, path)
        temp_name = None
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def _load_packet(job: Path) -> dict:
    packet_path = _packet_path(job)
    if not packet_path.is_file():
        raise ValueError("editorial review packet is missing; render a fresh preview")
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"editorial review packet cannot be read: {exc}") from exc
    if not isinstance(packet, dict) or type(packet.get("schema_version")) is not int or packet.get("schema_version") != 1:
        raise ValueError("editorial review packet has an invalid schema")
    return packet


def _frame_snapshot(frames: list[dict]) -> list[dict]:
    return [
        {
            "id": str(frame["id"]),
            "title": str(frame.get("title", frame["id"])),
            "start": float(frame["start"]),
            "duration": float(frame["duration"]),
        }
        for frame in frames
    ]


def create_review_packet(
    job: Path,
    preview: Path,
    frames: list[dict],
    *,
    render_inputs_sha256: str | None = None,
) -> Path:
    """Write a phone-size player and snapshot metadata for manual review."""
    job = Path(job).resolve(strict=True)
    preview = _safe_preview(job, preview)
    if not frames:
        raise ValueError("review packet requires at least one storyboard frame")
    input_hash = render_inputs_sha256 or render_input_fingerprint(job)
    if not HASH.fullmatch(input_hash):
        raise ValueError("render input fingerprint must be a SHA-256 hex digest")
    preview_hash = preview_sha256(preview)
    frame_snapshot = _frame_snapshot(frames)
    packet_data = {
        "schema_version": 1,
        "preview": preview.name,
        "preview_sha256": preview_hash,
        "render_inputs_sha256": input_hash,
        "frames": frame_snapshot,
    }
    packet_path = _safe_output_file(job, _packet_path(job))
    page_path = _safe_output_file(job, job / "out" / "editorial-review.html")
    _atomic_write_text(
        job, packet_path, json.dumps(packet_data, ensure_ascii=False, indent=2) + "\n"
    )

    frame_sections = []
    for frame in frame_snapshot:
        title = html.escape(frame["title"])
        frame_id = html.escape(frame["id"])
        checks = "".join(
            f"<li><code>{html.escape(name)}</code>: {html.escape(description)}</li>"
            for name, description in FRAME_CHECKS.items()
        )
        frame_sections.append(
            f"<section><h2>{frame_id} — {title}</h2>"
            f"<p>{frame['start']:.2f}s to {frame['start'] + frame['duration']:.2f}s</p>"
            f"<ul>{checks}</ul></section>"
        )
    global_items = "".join(
        f"<li><code>{html.escape(name)}</code>: {html.escape(description)}</li>"
        for name, description in GLOBAL_CHECKS.items()
    )
    page = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Editorial review — {html.escape(preview.stem)}</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:760px;margin:24px auto;padding:0 16px;color:#18202a}}video{{display:block;width:100%;max-width:360px;max-height:640px;background:#111;margin:16px 0}}section{{border-top:1px solid #ccd2d8;padding:12px 0}}code{{font-size:.9em}}</style>
<h1>Editorial review</h1>
<p>Watch the entire preview. Use the player at phone size; inspect each listed beat, then record the checklist with <code>editorial_review.py &lt;job&gt; --record</code>.</p>
<p>Preview SHA-256: <code data-preview-sha256="{preview_hash}">{preview_hash}</code></p>
<p>Render-input SHA-256: <code data-render-inputs-sha256="{input_hash}">{input_hash}</code></p>
<video controls preload="metadata" src="{html.escape(preview.name, quote=True)}"></video>
<h2>Whole-video checks</h2><ul>{global_items}</ul>
{''.join(frame_sections)}
</html>
"""
    _atomic_write_text(job, page_path, page)
    return page_path


def validate_review_packet(
    job: Path,
    preview: Path,
    frames: list[dict],
    *,
    render_inputs_sha256: str | None = None,
) -> list[str]:
    """Verify the packet still describes the exact preview and render inputs."""
    job = Path(job).resolve(strict=True)
    try:
        preview = _safe_preview(job, preview)
        current_input_hash = render_inputs_sha256 or render_input_fingerprint(job)
        packet = _load_packet(job)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    errors = []
    if packet.get("preview") != preview.name:
        errors.append("Review packet names a different preview file.")
    if packet.get("preview_sha256") != preview_sha256(preview):
        errors.append("Preview changed since its review packet was created; render a fresh preview.")
    if packet.get("render_inputs_sha256") != current_input_hash:
        errors.append("Render inputs changed since preview; render a fresh preview before review.")
    if packet.get("frames") != _frame_snapshot(frames):
        errors.append("Storyboard frames changed since preview; render a fresh preview before review.")
    return errors


def record_review(
    job: Path,
    preview: Path,
    frames: list[dict],
    *,
    reviewer: str,
    global_checks: dict,
    frame_checks: dict,
    expected_preview_sha256: str,
    expected_render_inputs_sha256: str,
) -> Path:
    """Persist a review only if its preview and source snapshot remain unchanged."""
    job = Path(job).resolve(strict=True)
    preview = _safe_preview(job, preview)
    packet = _load_packet(job)
    if not reviewer.strip():
        raise ValueError("reviewer name or initials are required")
    if packet.get("preview_sha256") != expected_preview_sha256:
        raise ValueError("review packet changed during editorial review")
    if packet.get("render_inputs_sha256") != expected_render_inputs_sha256:
        raise ValueError("review packet render-input snapshot changed during editorial review")
    errors = validate_review_packet(
        job, preview, frames,
        render_inputs_sha256=expected_render_inputs_sha256,
    )
    if errors:
        raise ValueError(errors[0])

    record = {
        "schema_version": 1,
        "preview": preview.name,
        "preview_sha256": expected_preview_sha256,
        "render_inputs_sha256": expected_render_inputs_sha256,
        "reviewer": reviewer.strip(),
        "reviewed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "global": global_checks,
        "frames": frame_checks,
    }
    path = job / "out" / "editorial-review.json"
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".editorial-review-", suffix=".tmp", delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        if preview_sha256(preview) != expected_preview_sha256:
            raise ValueError("Preview changed during editorial review; sign-off was not saved")
        if render_input_fingerprint(job) != expected_render_inputs_sha256:
            raise ValueError("Render inputs changed during editorial review; sign-off was not saved")
        os.replace(temp_name, path)
        temp_name = None
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
    return path


def validate_review(
    job: Path,
    preview: Path,
    frames: list[dict],
    *,
    render_inputs_sha256: str | None = None,
) -> list[str]:
    """Return blocking errors for absent, failed, malformed, or stale sign-off."""
    job = Path(job).resolve(strict=True)
    try:
        preview = _safe_preview(job, preview)
        current_input_hash = render_inputs_sha256 or render_input_fingerprint(job)
    except (OSError, ValueError) as exc:
        return [f"Review inputs unavailable: {exc}"]
    errors = validate_review_packet(
        job, preview, frames, render_inputs_sha256=current_input_hash
    )
    if errors:
        return errors

    review_path = job / "out" / "editorial-review.json"
    if not review_path.is_file():
        return ["Editorial review is missing; inspect the preview and record the checklist first."]
    try:
        record = json.loads(review_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Editorial review cannot be read: {exc}"]
    if not isinstance(record, dict):
        return ["Editorial review must contain a JSON object."]
    if type(record.get("schema_version")) is not int or record.get("schema_version") != 1:
        errors.append("Editorial review has an unsupported schema_version.")
    if record.get("preview") != preview.name:
        errors.append("Editorial review names a different preview file.")
    if record.get("preview_sha256") != preview_sha256(preview):
        errors.append("Preview changed since review; sign-off is stale and must be repeated.")
    if record.get("render_inputs_sha256") != current_input_hash:
        errors.append("Render inputs changed since review; sign-off is stale and must be repeated.")
    if not isinstance(record.get("reviewer"), str) or not record["reviewer"].strip():
        errors.append("Editorial review must identify a reviewer.")
    if not isinstance(record.get("reviewed_at"), str) or not record["reviewed_at"].strip():
        errors.append("Editorial review is missing its review time.")
    _check_items(record.get("global"), GLOBAL_CHECKS, "global", errors)
    frame_records = record.get("frames")
    if not isinstance(frame_records, dict):
        errors.append("Editorial review frames must be an object keyed by frame id.")
        return errors
    expected_ids = {str(frame["id"]) for frame in frames}
    for missing in sorted(expected_ids - set(frame_records)):
        errors.append(f"Editorial review is missing frame {missing}.")
    for unexpected in sorted(set(frame_records) - expected_ids):
        errors.append(f"Editorial review contains unknown frame {unexpected}.")
    for frame_id in sorted(expected_ids & set(frame_records)):
        _check_items(frame_records[frame_id], FRAME_CHECKS, f"frame {frame_id}", errors)
    return errors


def _check_items(actual, required: dict, label: str, errors: list[str]) -> None:
    if not isinstance(actual, dict):
        errors.append(f"Editorial review {label} checks must be an object.")
        return
    for name in required:
        if name not in actual:
            errors.append(f"Editorial review {label} is missing check {name}.")
        elif actual[name] is not True:
            errors.append(f"Editorial review {label} check {name} did not pass.")
    for name in set(actual) - set(required):
        errors.append(f"Editorial review {label} has unknown check {name}.")


def find_preview(job: Path) -> Path:
    candidates = sorted((job / "out").glob("*-preview.mp4"))
    if len(candidates) != 1:
        raise ValueError(f"expected one preview MP4 in {job / 'out'}, found {len(candidates)}")
    return candidates[0]


def _ask(prompt: str) -> bool:
    return input(f"{prompt} [y/N] ").strip().lower() in {"y", "yes"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", help="HyperFrames job folder")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--record", action="store_true", help="record an interactive editorial review")
    action.add_argument("--check", action="store_true", help="check the saved review against the current preview")
    args = parser.parse_args(argv)
    job = Path(args.job).resolve()
    try:
        frames = storyboard_frames(job)
        if not frames:
            raise ValueError("no timed storyboard frames found")
        preview = find_preview(job)
        if args.check:
            errors = validate_review(job, preview, frames)
            if errors:
                print("Editorial review blocked:")
                for error in errors:
                    print(f"  - {error}")
                return 1
            print(f"Editorial review passed for {preview.name}.")
            return 0

        packet_errors = validate_review_packet(job, preview, frames)
        if packet_errors:
            print("Editorial review packet is stale or invalid:")
            for error in packet_errors:
                print(f"  - {error}")
            return 1
        packet = _load_packet(job)
        expected_preview_sha256 = packet["preview_sha256"]
        expected_render_inputs_sha256 = packet["render_inputs_sha256"]
        print(f"Open this review packet and watch the full preview: {job / 'out' / 'editorial-review.html'}")
        reviewer = input("Reviewer name or initials: ").strip()
        global_checks = {name: _ask(prompt) for name, prompt in GLOBAL_CHECKS.items()}
        frame_checks = {}
        for frame in frames:
            print(f"Frame {frame['id']}: {frame['title']}")
            frame_checks[frame["id"]] = {
                name: _ask(prompt) for name, prompt in FRAME_CHECKS.items()
            }
        path = record_review(
            job, preview, frames, reviewer=reviewer,
            global_checks=global_checks, frame_checks=frame_checks,
            expected_preview_sha256=expected_preview_sha256,
            expected_render_inputs_sha256=expected_render_inputs_sha256,
        )
        errors = validate_review(
            job, preview, frames,
            render_inputs_sha256=expected_render_inputs_sha256,
        )
        if errors:
            print(f"Review saved with blocking items: {path}")
            for error in errors:
                print(f"  - {error}")
            return 1
        print(f"Editorial review passed and saved: {path}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Editorial review failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
