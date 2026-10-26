"""Validate a job's timestamped storyboard against its narration and assets."""
from pathlib import Path, PureWindowsPath
import json
from html.parser import HTMLParser
import re
import sys


FRAME_HEADING = re.compile(r"^##\s+Frame\s+(\d+)\s*[—–:-]\s*(.+?)\s*$")
FIELD_LINE = re.compile(r"^\s*-\s*([a-z][a-z0-9_-]*):\s*(.*?)\s*$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SECONDS = re.compile(r"^(\d+(?:\.\d+)?)\s*s?$", re.IGNORECASE)
OVERLAP_TRANSITIONS = {"crossfade", "wipe", "morph", "object-morph", "zoom-through", "blur-swap"}


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _seconds(value: str):
    if not isinstance(value, str):
        return None
    match = SECONDS.fullmatch(_scalar(value))
    return float(match.group(1)) if match else None


def _parse_frontmatter(lines):
    if not lines or lines[0].strip() != "---":
        return {}, 0, ["STORYBOARD.md must begin with YAML frontmatter delimited by ---."]
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}, 0, ["STORYBOARD.md frontmatter has no closing ---."]

    metadata, errors = {}, []
    for line_number, line in enumerate(lines[1:end], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            errors.append(f"frontmatter line {line_number}: expected key: value")
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", key):
            errors.append(f"frontmatter line {line_number}: invalid key {key!r}")
            continue
        if key in metadata:
            errors.append(f"frontmatter line {line_number}: duplicate key {key!r}")
            continue
        metadata[key] = _scalar(value)
    return metadata, end + 1, errors


def _parse_frames(lines, start_line):
    frames, current, errors = [], None, []
    for line_number, line in enumerate(lines[start_line:], start=start_line + 1):
        heading = FRAME_HEADING.match(line)
        if heading:
            current = {"number": int(heading.group(1)), "title": heading.group(2), "line": line_number}
            current["fields"] = {}
            frames.append(current)
            continue
        if current is None:
            continue
        field = FIELD_LINE.match(line)
        if field:
            key, value = field.groups()
            if key in current["fields"]:
                errors.append(f"frame {current['number']} line {line_number}: duplicate field {key!r}")
            else:
                current["fields"][key] = _scalar(value)
    if not frames:
        errors.append("STORYBOARD.md must contain at least one '## Frame N — Title' section.")
    return frames, errors


def _safe_job_file(job_dir: Path, relative: str, *, expected_root: str | None = None):
    rel = relative.replace("\\", "/").strip()
    posix = Path(rel)
    windows = PureWindowsPath(relative)
    parts = rel.split("/")
    if not rel or posix.is_absolute() or windows.is_absolute() or windows.drive or any(part in {"", ".", ".."} for part in parts):
        return None, "unsafe path"
    if expected_root and parts[0] != expected_root:
        return None, f"path must be under {expected_root}/"
    try:
        candidate = (job_dir / posix).resolve(strict=False)
        candidate.relative_to(job_dir.resolve())
    except (OSError, ValueError):
        return None, "path escapes the job directory"
    return candidate, None


class _HtmlTagCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag.lower(), dict(attrs)))


def _validate_hyperframes_root(job_dir: Path, metadata: dict, total_duration, frames):
    root_path = job_dir / "index.html"
    if not root_path.is_file():
        return ["Missing index.html HyperFrames composition root."]
    try:
        html = root_path.read_text(encoding="utf-8")
        collector = _HtmlTagCollector()
        collector.feed(html)
    except (OSError, ValueError) as exc:
        return [f"Could not parse index.html: {exc}"]

    errors = []
    tags = collector.tags
    root = next((attrs for _, attrs in tags if attrs.get("id") == "root"), None)
    if root is None:
        errors.append('index.html must declare a root element with id="root".')

    required_attrs = ("data-composition-id", "data-start", "data-duration", "data-width", "data-height")
    if root is not None:
        missing = [name for name in required_attrs if not root.get(name)]
        if missing:
            errors.append(f"index.html root is missing required attributes: {', '.join(missing)}.")

    size_match = re.fullmatch(r"([0-9]{3,5})x([0-9]{3,5})", metadata.get("format", ""))
    width = height = None
    if not size_match:
        errors.append("Storyboard format cannot be matched to index.html canvas dimensions.")
    else:
        width, height = int(size_match.group(1)), int(size_match.group(2))

    if root is not None:
        root_width = root_height = None
        if root.get("data-width") and root.get("data-height"):
            try:
                root_width, root_height = int(root["data-width"]), int(root["data-height"])
                if root_width <= 0 or root_height <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                root_width = root_height = None
                errors.append("index.html root data-width and data-height must be positive integers.")
        if width is not None and height is not None and root_width is not None and (root_width, root_height) != (width, height):
            errors.append(f"index.html canvas {root_width}x{root_height} does not match storyboard format {width}x{height}.")

        root_start = _seconds(root.get("data-start", ""))
        if root_start != 0:
            errors.append("index.html root data-start must be 0.")
        root_duration = _seconds(root.get("data-duration", ""))
        if root_duration is None or root_duration <= 0:
            errors.append("index.html root data-duration must be a positive number of seconds.")
        elif total_duration is not None and root_duration + 1e-6 < total_duration:
            errors.append("index.html root data-duration is shorter than the storyboard duration.")

    for frame in frames:
        fields = frame["fields"]
        if fields.get("status", "outline").lower() not in {"built", "animated"}:
            continue
        frame_id, src = fields.get("id", ""), fields.get("src", "")
        matches = [attrs for _, attrs in tags if attrs.get("data-composition-src") == src]
        label = f"frame {frame_id or frame['number']}"
        if len(matches) != 1:
            errors.append(f"{label}: expected one root mount for {src!r} in index.html, found {len(matches)}.")
            continue
        host = matches[0]
        for name in ("id", "data-composition-id"):
            if host.get(name) != frame_id:
                errors.append(f"{label}: root mount {name} must match storyboard id {frame_id!r}.")
        if width is not None and height is not None:
            for name, expected in (("data-width", width), ("data-height", height)):
                if str(host.get(name, "")) != str(expected):
                    errors.append(f"{label}: root mount {name} must match canvas {width}x{height}.")
        expected_start, actual_start = _seconds(fields.get("start", "")), _seconds(host.get("data-start", ""))
        expected_duration, actual_duration = _seconds(fields.get("duration", "")), _seconds(host.get("data-duration", ""))
        if expected_start is None or actual_start is None or abs(expected_start - actual_start) > 1e-6:
            errors.append(f"{label}: root mount data-start must match storyboard start.")
        if expected_duration is None or actual_duration is None or abs(expected_duration - actual_duration) > 1e-6:
            errors.append(f"{label}: root mount data-duration must match storyboard duration.")
    return errors


def validate_storyboard(job_dir: Path, require_ready: bool = False) -> list[str]:
    """Return actionable errors; an empty list means the plan passes structural checks."""
    job_dir = Path(job_dir).resolve()
    storyboard_path = job_dir / "STORYBOARD.md"
    segments_path = job_dir / "segments.json"
    errors = []
    if not storyboard_path.is_file():
        return [f"Missing {storyboard_path.name}; create the visual beat plan before rendering."]
    if not segments_path.is_file():
        return [f"Missing {segments_path.name}; create the narration plan before validating the storyboard."]

    try:
        text = storyboard_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Could not read STORYBOARD.md: {exc}"]
    lines = text.splitlines()
    metadata, body_start, frontmatter_errors = _parse_frontmatter(lines)
    errors.extend(frontmatter_errors)
    frames, frame_errors = _parse_frames(lines, body_start)
    errors.extend(frame_errors)

    if not re.fullmatch(r"\d{3,5}x\d{3,5}", metadata.get("format", "")):
        errors.append("frontmatter format must be a size such as 1080x1920 or 1920x1080.")
    try:
        fps = float(metadata.get("fps", ""))
        if fps <= 0:
            raise ValueError
    except ValueError:
        errors.append("frontmatter fps must be a positive number.")
    total_duration = _seconds(metadata.get("duration", ""))
    if total_duration is None or total_duration <= 0:
        errors.append("frontmatter duration must be a positive number of seconds (for example, 48s).")

    try:
        job_data = json.loads(segments_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return errors + [f"Could not read segments.json: {exc}"]
    segments = job_data.get("segments", [])
    if not isinstance(segments, list):
        segments = []
        errors.append("segments.json segments must be an array.")
    segment_ids = {str(item.get("id")) for item in segments if isinstance(item, dict) and item.get("id")}
    claims = job_data.get("claims", [])
    claim_ids = {str(item.get("id")) for item in claims if isinstance(item, dict) and item.get("id")} if isinstance(claims, list) else set()

    seen_numbers, seen_ids, previous_end = set(), set(), 0.0
    for frame in frames:
        fields = frame["fields"]
        number, label = frame["number"], f"frame {frame['number']} ({frame['title']})"
        if number in seen_numbers:
            errors.append(f"{label}: duplicate frame number {number}.")
        seen_numbers.add(number)
        frame_id = fields.get("id", "")
        if not SLUG.fullmatch(frame_id):
            errors.append(f"{label}: id must use lowercase letters, digits, and hyphens.")
        elif frame_id in seen_ids:
            errors.append(f"{label}: duplicate frame id {frame_id!r}.")
        seen_ids.add(frame_id)
        for required in ("start", "duration", "scene"):
            if not fields.get(required):
                errors.append(f"{label}: missing required {required} field.")
        status = fields.get("status", "outline").lower()
        if status not in {"outline", "built", "animated"}:
            errors.append(f"{label}: status must be outline, built, or animated.")
        if require_ready and status != "animated":
            errors.append(f"{label}: status is {status}; mark and finish the frame before rendering.")

        start = _seconds(fields.get("start", ""))
        duration = _seconds(fields.get("duration", ""))
        if start is None or start < 0:
            errors.append(f"{label}: start must be zero or a positive number of seconds.")
        if duration is None or duration <= 0:
            errors.append(f"{label}: duration must be a positive number of seconds.")
        if start is not None and duration is not None:
            if start < previous_end - 1e-6 and fields.get("transition_in", "cut").lower() not in OVERLAP_TRANSITIONS:
                errors.append(f"{label}: overlaps the preceding frame without an overlap transition.")
            previous_end = max(previous_end, start + duration)
            if total_duration is not None and start + duration > total_duration + 1e-6:
                errors.append(f"{label}: extends beyond the storyboard duration.")

        segment_id = fields.get("voiceover_segment_id", "")
        if segment_id and segment_id not in segment_ids:
            errors.append(f"{label}: voiceover_segment_id {segment_id!r} is missing from segments.json.")
        if fields.get("source_refs"):
            refs = [ref.strip() for ref in fields["source_refs"].split(",") if ref.strip()]
            if not claim_ids:
                errors.append(f"{label}: source_refs require claim IDs in segments.json claims.")
            for ref in refs:
                if ref not in claim_ids:
                    errors.append(f"{label}: source reference {ref!r} is missing from segments.json claims.")

        src = fields.get("src", "")
        if status in {"built", "animated"} and not src:
            errors.append(f"{label}: built/animated frames require a src composition path.")
        if src:
            path, path_error = _safe_job_file(job_dir, src)
            if path_error:
                errors.append(f"{label}: src {src!r} is {path_error}.")
            elif path is None:
                errors.append(f"{label}: could not resolve src {src!r}.")
            elif status in {"built", "animated"} and not path.is_file():
                errors.append(f"{label}: composition file {src!r} is missing.")

        if fields.get("assets"):
            for asset in (part.strip() for part in fields["assets"].split(",")):
                if not asset:
                    continue
                path, path_error = _safe_job_file(job_dir, asset, expected_root="assets")
                if path_error:
                    errors.append(f"{label}: asset {asset!r} is {path_error}.")
                elif path is None:
                    errors.append(f"{label}: could not resolve asset {asset!r}.")
                elif not path.is_file():
                    errors.append(f"{label}: asset file {asset!r} is missing.")

    if require_ready:
        errors.extend(_validate_hyperframes_root(job_dir, metadata, total_duration, frames))
    return errors


def main(argv=None) -> int:
    import argparse

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _common import resolve_job

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", help="job folder, segments.json path, or job slug")
    parser.add_argument("--require-ready", action="store_true", help="require every frame to be animated and have a composition")
    args = parser.parse_args(argv)
    job = resolve_job(args.job)
    errors = validate_storyboard(job, require_ready=args.require_ready)
    if errors:
        print("Storyboard check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"Storyboard check passed: {job}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
