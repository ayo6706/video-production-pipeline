"""Run the pinned HyperFrames validation, review, render, and output checks."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

from _common import ROOT, load_config, load_manifest, load_persona
from hyperframes_prepare import narration_audio_markup, prepare_workspace
from storyboard_check import validate_storyboard


SECONDS = re.compile(r"^(\d+(?:\.\d+)?)\s*s?$", re.IGNORECASE)


def _frontmatter(job: Path) -> dict:
    lines = (job / "STORYBOARD.md").read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    metadata = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return metadata
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip("\"'")
    return {}


def _seconds(value: str) -> float | None:
    match = SECONDS.fullmatch(value.strip())
    return float(match.group(1)) if match else None


def _resolve_cli(cli_path: Path | None) -> Path | None:
    if cli_path is not None:
        return Path(cli_path).resolve()
    name = "hyperframes.cmd" if os.name == "nt" else "hyperframes"
    candidate = ROOT / "tools" / "hyperframes" / "node_modules" / ".bin" / name
    return candidate.resolve() if candidate.is_file() else None


def _cli_command(cli: Path, *args: str) -> list[str]:
    if os.name == "nt" and cli.suffix.lower() == ".cmd":
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", str(cli), *args]
    return [str(cli), *args]


def _run_json_stage(action: str, cli: Path, job: Path, env: dict, runner):
    result = runner(
        _cli_command(cli, action, "--json"),
        cwd=job, capture_output=True, text=True, env=env, check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"HyperFrames {action} failed (exit {result.returncode}): {detail}")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"HyperFrames {action} returned invalid JSON: {exc}") from exc
    return report, result.stdout


def _run(command: list[str], job: Path, env: dict, runner):
    result = runner(command, cwd=job, capture_output=True, text=True, env=env, check=False)
    if result.returncode:
        raise RuntimeError(f"Command failed (exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}")
    return result


def _verify_media(output: Path, ffprobe: Path, dimensions: tuple[int, int], duration: float, fps: float, needs_audio: bool, runner, job: Path, env: dict):
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("HyperFrames reported success but did not produce a non-empty video file.")
    probe = _run(
        [str(ffprobe), "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", str(output)],
        job, env, runner,
    )
    try:
        metadata = json.loads(probe.stdout)
        streams = metadata.get("streams", [])
        video = next(stream for stream in streams if stream.get("codec_type") == "video")
        actual_duration = float(metadata["format"]["duration"])
    except (json.JSONDecodeError, KeyError, StopIteration, TypeError, ValueError) as exc:
        raise RuntimeError(f"ffprobe could not verify the rendered media: {exc}") from exc
    if (video.get("width"), video.get("height")) != dimensions:
        raise RuntimeError(f"Rendered canvas {video.get('width')}x{video.get('height')} does not match {dimensions[0]}x{dimensions[1]}.")
    if actual_duration <= 0 or abs(actual_duration - duration) > max(0.1, 2 / fps):
        raise RuntimeError(f"Rendered duration {actual_duration:.3f}s does not match storyboard duration {duration:.3f}s.")
    if needs_audio and not any(stream.get("codec_type") == "audio" for stream in streams):
        raise RuntimeError("Narrated job rendered without an audio stream.")


def _save_report(path: Path, raw: str, workspace: Path, job: Path) -> None:
    path.write_text(raw.replace(str(workspace), str(job)), encoding="utf-8")


def _persist_artifacts(workspace: Path, job: Path) -> None:
    source = workspace / ".hyperframes" / "artifacts"
    if source.is_dir():
        destination = job / ".hyperframes" / "artifacts"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, dirs_exist_ok=True)


def render_job(
    job: Path,
    *,
    preview: bool = False,
    approved: bool = False,
    format_override: str | None = None,
    runner=None,
    cli_path: Path | None = None,
    ffprobe_path: Path | None = None,
) -> int:
    """Render a HyperFrames job; final output requires a human approval flag."""
    job = Path(job).resolve()
    if not preview and not approved:
        print("Final render blocked: inspect the preview and review frames, then rerun with --approved.")
        return 1

    problems = validate_storyboard(job, require_ready=True)
    if problems:
        print("Cannot render HyperFrames job:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    metadata = _frontmatter(job)
    size = re.fullmatch(r"([0-9]{3,5})x([0-9]{3,5})", metadata.get("format", ""))
    duration, fps = _seconds(metadata.get("duration", "")), float(metadata.get("fps", "0"))
    if not size or duration is None or fps <= 0:
        print("Cannot render: invalid storyboard format, duration, or frame rate.")
        return 1
    dimensions = (int(size.group(1)), int(size.group(2)))
    orientation = "portrait" if dimensions[0] < dimensions[1] else "landscape" if dimensions[0] > dimensions[1] else "square"
    if format_override == "both":
        print("HyperFrames renders one canvas per job; set the target in STORYBOARD.md or use a Remotion job for both layouts.")
        return 1
    if format_override and format_override != orientation:
        print(f"Requested {format_override} output does not match storyboard format {dimensions[0]}x{dimensions[1]}.")
        return 1

    cli = _resolve_cli(cli_path)
    ffprobe_name = shutil.which("ffprobe")
    ffprobe = Path(ffprobe_path).resolve() if ffprobe_path else (Path(ffprobe_name).resolve() if ffprobe_name else None)
    if cli is None:
        print("Pinned HyperFrames CLI is missing. Run npm ci --ignore-scripts in tools/hyperframes.")
        return 1
    if ffprobe is None or not ffprobe.is_file():
        print("ffprobe is required to verify the rendered file; install the FFmpeg tools and retry.")
        return 1

    runner = runner or subprocess.run
    env = os.environ.copy()
    env.update({
        "HYPERFRAMES_NO_UPDATE_CHECK": "1",
        "HYPERFRAMES_NO_TELEMETRY": "1",
        "HYPERFRAMES_SKIP_SKILLS": "1",
        "CI": "1",
    })
    temporary_output: Path | None = None
    try:
        plan = json.loads((job / "segments.json").read_text(encoding="utf-8"))
        if not isinstance(plan, dict):
            raise ValueError("segments.json must contain an object")
        segments = plan.get("segments", [])
        if not isinstance(segments, list):
            raise ValueError("segments.json segments must be an array")
        has_narration = any(
            isinstance(segment, dict) and isinstance(segment.get("text"), str) and segment["text"].strip()
            for segment in segments
        )
        audio_markup = ""
        if has_narration:
            persona_id = plan.get("persona")
            if not isinstance(persona_id, str) or not persona_id:
                raise ValueError("Narrated HyperFrames jobs must set a persona in segments.json")
            try:
                persona = load_persona(persona_id)
            except SystemExit as exc:
                raise ValueError(str(exc)) from exc
            voice = persona.get("voice") if isinstance(persona, dict) else None
            if not isinstance(voice, dict):
                raise ValueError(f"Persona {persona_id!r} must define a voice object")
            config = load_config()
            audio_markup = narration_audio_markup(
                job, plan, voice, load_manifest(job),
                config.get("segment_gap_seconds", 0.25), duration,
            )
        slug = plan.get("slug") or job.name
        tag = "9x16" if orientation == "portrait" else "16x9" if orientation == "landscape" else "1x1" if dimensions[0] == dimensions[1] else f"{dimensions[0]}x{dimensions[1]}"
        output_dir = job / "out"
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / f"{slug}-{tag}{'-preview' if preview else ''}.mp4"
        temporary_output = output_dir / f"{slug}-{tag}-{uuid.uuid4().hex}.tmp.mp4"
        workspace_parent = job / ".hyperframes"
        workspace_parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="build-", dir=workspace_parent) as workspace_name:
            workspace = Path(workspace_name)
            prepare_workspace(job, workspace, audio_markup)
            try:
                lint, lint_json = _run_json_stage("lint", cli, workspace, env, runner)
                _save_report(output_dir / "hyperframes-lint.json", lint_json, workspace, job)
                if int(lint.get("errorCount", 0)) > 0:
                    raise RuntimeError(f"HyperFrames lint found {lint['errorCount']} error(s). Fix them before rendering.")

                check_result = runner(
                    _cli_command(cli, "check", "--json", "--snapshots", "--at-transitions"),
                    cwd=workspace, capture_output=True, text=True, env=env, check=False,
                )
                if check_result.returncode:
                    detail = check_result.stderr.strip() or check_result.stdout.strip()
                    raise RuntimeError(f"HyperFrames check failed (exit {check_result.returncode}): {detail}")
                try:
                    check = json.loads(check_result.stdout)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"HyperFrames check returned invalid JSON: {exc}") from exc
                _save_report(output_dir / "hyperframes-check.json", check_result.stdout, workspace, job)
                if check.get("ok") is not True:
                    raise RuntimeError("HyperFrames browser/layout/motion/contrast check did not pass; see hyperframes-check.json.")
                lint_warnings = int(lint.get("warningCount", 0) or 0)
                craft_warnings = int((check.get("craft") or {}).get("warningCount", 0) or 0)
                if lint_warnings or craft_warnings:
                    print(f"QA warnings: lint={lint_warnings}, craft={craft_warnings}; inspect review artifacts before approving.")

                review_result = runner(
                    _cli_command(cli, "snapshot", "--review", "--json"),
                    cwd=workspace, capture_output=True, text=True, env=env, check=False,
                )
                if review_result.returncode:
                    detail = review_result.stderr.strip() or review_result.stdout.strip()
                    raise RuntimeError(f"HyperFrames review snapshot failed (exit {review_result.returncode}): {detail}")
                try:
                    json.loads(review_result.stdout)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"HyperFrames review snapshot returned invalid JSON: {exc}") from exc
                _save_report(output_dir / "hyperframes-review.json", review_result.stdout, workspace, job)

                quality = "draft" if preview else "delivery"
                _run(_cli_command(cli, "render", "--output", str(temporary_output), "--quality", quality, "--no-best-effort"), workspace, env, runner)
                _verify_media(temporary_output, ffprobe, dimensions, duration, fps, bool(audio_markup), runner, job, env)
                temporary_output.replace(output)
                print(f"HyperFrames {quality} render verified: {output}")
                print("Review artifacts: out/hyperframes-lint.json, out/hyperframes-check.json, out/hyperframes-review.json")
                return 0
            finally:
                _persist_artifacts(workspace, job)
    except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"HyperFrames render failed: {exc}")
        return 1
    finally:
        if temporary_output is not None:
            temporary_output.unlink(missing_ok=True)
