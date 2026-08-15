#!/usr/bin/env python3
"""
Extract Whisper-ready audio from downloaded Jubilee debate videos.

This script reads a curated Jubilee debate index from an NDJSON file, selects
records whose downloaded source videos are available, and extracts one full-length
WAV audio file per eligible debate using ffmpeg.

Source debate videos are resolved from the input record's "video_file" field when
available, or from the input directory as "<corpus_id>.mp4". Extracted audio files
are written to the output directory as "<corpus_id>.wav".

The output audio format is designed for Whisper, WhisperX, and pyannote.audio:
mono, 16 kHz, signed 16-bit PCM WAV.

By default, the script runs in test mode and attempts only the first 5 planned
debates. Existing output audio files are skipped unless --reprocess is provided,
making the script safe to re-run.

Use --start-corpus-id to start planning extraction from a specific corpus_id
onward.

This script extracts full-length audio only. Transcription, alignment,
segmentation, and diarisation are handled by later pipeline stages.

Example:
    python extract_jubilee_debates_audio.py

Full run:
    python extract_jubilee_debates_audio.py --no-test-mode

Full run from a specific debate:
    python extract_jubilee_debates_audio.py --no-test-mode --start-corpus-id jubilee_surrounded_003

The script writes an append-only log file, a JSON manifest, and a curated NDJSON
audio index describing run-level metadata and per-debate audio extraction status.

For portability, curated index paths under the project phase directory are written
relative to SCRIPT_DIR instead of as machine-specific absolute paths. This allows
the generated audio index to work both locally and on EC2 when the project layout
is preserved.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOOL_NAME = "extract_jubilee_debates_audio.py"
TOOL_VERSION = "v1"

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_INDEX_PATH = "corpus/01_jubilee_debates/jubilee_debates_index.ndjson"
DEFAULT_INPUT_DIR = "corpus/01_jubilee_debates/videos"
DEFAULT_OUTPUT_DIR = "corpus/02_jubilee_debates_audio"
DEFAULT_LOG_FILE = (
    "corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log"
)
DEFAULT_MANIFEST_FILE = (
    "corpus/02_jubilee_debates_audio/"
    "extract_jubilee_debates_audio_manifest.json"
)
DEFAULT_AUDIO_INDEX_FILE = (
    "corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson"
)

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 7200
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

INPUT_VIDEO_EXTENSION = ".mp4"
OUTPUT_AUDIO_EXTENSION = ".wav"

OUTPUT_AUDIO_FORMAT = "wav"
FFMPEG_AUDIO_CHANNELS = "1"
FFMPEG_AUDIO_SAMPLE_RATE = "16000"
FFMPEG_AUDIO_CODEC = "pcm_s16le"
FFMPEG_AUDIO_SAMPLE_FORMAT = "s16"

FFMPEG_AUDIO_ARGS = [
    "-vn",
    "-ac",
    FFMPEG_AUDIO_CHANNELS,
    "-ar",
    FFMPEG_AUDIO_SAMPLE_RATE,
    "-sample_fmt",
    FFMPEG_AUDIO_SAMPLE_FORMAT,
]

ELIGIBLE_DOWNLOAD_STATUSES = ("success", "skipped_existing")

PRESERVED_METADATA_FIELDS = (
    "corpus_id",
    "debate_format",
    "sample_group",
    "sample_order",
    "title",
    "title_selected",
    "title_extracted",
    "youtube_id",
    "youtube_url",
    "webpage_url",
    "channel",
    "channel_selected",
    "channel_extracted",
    "duration_seconds",
    "duration_string",
    "chapters",
    "subtitles_files",
    "raw_metadata_file",
    "description_file",
    "download_run_id",
    "downloaded_at_utc",
    "yt_dlp_version",
    "selected_by",
    "selection_source",
    "notes",
    "metadata_status",
)


class ConfigurationError(Exception):
    """Raised when command-line options or runtime configuration are invalid."""


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime without performing I/O."""
    return datetime.now(timezone.utc)


def utc_timestamp() -> str:
    """Return an ISO-like UTC timestamp string without microseconds."""
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    """Return a compact UTC run identifier suitable for filenames."""
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the Jubilee debate audio extraction programme.

    Returns:
        argparse.Namespace containing raw command-line values. Paths are resolved
        after parsing.

    I/O:
        Reads command-line arguments from sys.argv via argparse.

    Error behaviour:
        argparse exits with code 2 for malformed command-line usage.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Extract full-length mono 16 kHz PCM WAV audio from downloaded "
            "Jubilee debate videos."
        )
    )

    parser.add_argument("--index", default=DEFAULT_INDEX_PATH, help="Path to NDJSON debate index.")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR, help="Directory containing source MP4 videos.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for extracted WAV files.")

    test_mode_group = parser.add_mutually_exclusive_group()
    test_mode_group.add_argument(
        "--test-mode",
        dest="test_mode",
        action="store_true",
        help="Enable test mode.",
    )
    test_mode_group.add_argument(
        "--no-test-mode",
        dest="test_mode",
        action="store_false",
        help="Disable test mode.",
    )
    parser.set_defaults(test_mode=DEFAULT_TEST_MODE)

    parser.add_argument("--test-limit", type=int, default=DEFAULT_TEST_LIMIT)
    parser.add_argument("--reprocess", action="store_true", help="Overwrite existing output WAV files.")
    parser.add_argument("--start-corpus-id", default=None, help="Start planning from this corpus_id.")

    parser.add_argument("--log-file", default=DEFAULT_LOG_FILE)
    parser.add_argument("--manifest-file", default=DEFAULT_MANIFEST_FILE)
    parser.add_argument("--audio-index-file", default=DEFAULT_AUDIO_INDEX_FILE)

    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--retry-delay", type=int, default=DEFAULT_RETRY_DELAY_SECONDS)

    args = parser.parse_args()

    args.index = resolve_script_relative_path(Path(args.index))
    args.input_dir = resolve_script_relative_path(Path(args.input_dir))
    args.output_dir = resolve_script_relative_path(Path(args.output_dir))
    args.log_file = resolve_script_relative_path(Path(args.log_file))
    args.manifest_file = resolve_script_relative_path(Path(args.manifest_file))
    args.audio_index_file = resolve_script_relative_path(Path(args.audio_index_file))

    return args


def resolve_script_relative_path(path: Path) -> Path:
    """
    Resolve relative paths against the programme directory.

    Args:
        path: A relative or absolute filesystem path.

    Returns:
        Absolute paths unchanged; relative paths resolved relative to SCRIPT_DIR.

    I/O:
        Does not touch the filesystem.

    Error behaviour:
        Does not raise for non-existent paths.
    """
    if path.is_absolute():
        return path
    return SCRIPT_DIR / path


def path_for_index(path_value: Any) -> str | None:
    """
    Convert a path to a portable string for curated index files.

    Paths located inside the project phase directory are stored relative to
    SCRIPT_DIR, for example:

        corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav

    Paths outside SCRIPT_DIR are preserved as originally supplied. This avoids
    converting genuinely external paths into misleading project-relative paths.

    Args:
        path_value: Path-like value or string.

    Returns:
        Project-relative path string when possible; otherwise original/resolved
        path string. Returns None for None input.

    I/O:
        Does not require path existence. Path.resolve(strict=False) is used.

    Error behaviour:
        Falls back to str(path) if path resolution fails.
    """
    if path_value is None:
        return None

    path = Path(str(path_value))

    try:
        resolved = path.resolve(strict=False)
    except OSError:
        return str(path)

    try:
        return str(resolved.relative_to(SCRIPT_DIR))
    except ValueError:
        return str(path)


def setup_logging(log_file: Path) -> logging.Logger:
    """
    Configure append-only logging.

    Args:
        log_file: Path to the UTF-8 log file.

    Returns:
        Configured programme logger.

    I/O:
        Creates the parent directory if needed and appends to the log file.

    Error behaviour:
        Propagates OSError if the log directory/file cannot be created or opened.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(TOOL_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


def check_ffmpeg() -> dict[str, Any]:
    """
    Check whether ffmpeg is available and return version metadata.

    Returns:
        Dictionary with availability flag and version string.

    I/O:
        Runs "ffmpeg -version" through subprocess.

    Error behaviour:
        Raises ConfigurationError if ffmpeg is not found or cannot be executed.
    """
    if shutil.which("ffmpeg") is None:
        raise ConfigurationError("ffmpeg is not available on the system PATH.")

    try:
        completed = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigurationError(f"Could not run ffmpeg -version: {exc}") from exc

    if completed.returncode != 0:
        error = completed.stderr.strip() or completed.stdout.strip() or "unknown ffmpeg error"
        raise ConfigurationError(f"ffmpeg -version failed: {error}")

    version = completed.stdout.splitlines()[0] if completed.stdout.splitlines() else "unknown"
    return {"available": True, "version": version}


def validate_args(args: argparse.Namespace) -> None:
    """
    Validate command-line arguments and filesystem configuration.

    Args:
        args: Parsed and path-resolved argparse namespace.

    Returns:
        None.

    I/O:
        Checks path existence, readability, and creates the output directory.

    Error behaviour:
        Raises ConfigurationError for validation failures.
    """
    if args.test_limit <= 0:
        raise ConfigurationError("--test-limit must be a positive integer.")

    if args.workers <= 0:
        raise ConfigurationError("--workers must be a positive integer.")

    if args.workers != 1:
        raise ConfigurationError("Only --workers 1 is supported in this sequential implementation.")

    if args.timeout <= 0:
        raise ConfigurationError("--timeout must be a positive integer.")

    if args.max_retries < 0:
        raise ConfigurationError("--max-retries must be zero or a positive integer.")

    if args.retry_delay < 0:
        raise ConfigurationError("--retry-delay must be zero or a positive integer.")

    if args.start_corpus_id is not None and not args.start_corpus_id.strip():
        raise ConfigurationError("--start-corpus-id must not be empty.")

    if not args.index.exists():
        raise ConfigurationError(f"Input index file does not exist: {args.index}")

    if not args.index.is_file():
        raise ConfigurationError(f"Input index path is not a file: {args.index}")

    try:
        with args.index.open("r", encoding="utf-8"):
            pass
    except OSError as exc:
        raise ConfigurationError(f"Input index file is unreadable: {args.index}: {exc}") from exc

    if not args.input_dir.exists():
        raise ConfigurationError(f"Input video directory does not exist: {args.input_dir}")

    if not args.input_dir.is_dir():
        raise ConfigurationError(f"Input video path is not a directory: {args.input_dir}")

    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        args.audio_index_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create output/log/manifest directories: {exc}") from exc


def load_debate_index(
        index_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int, list[dict[str, Any]]]:
    """
    Load and validate eligible debate metadata from an NDJSON index file.

    Args:
        index_path: Path to the input NDJSON debate index.

    Returns:
        Tuple of:
            eligible_records: records with eligible download_status and valid corpus_id;
            invalid_records: eligible records missing required metadata;
            total_records: total non-blank NDJSON records read;
            ignored_count: count of ineligible records;
            ignored_records: manifest records for ignored ineligible rows.

    I/O:
        Reads the NDJSON file.

    Error behaviour:
        Raises ConfigurationError for invalid JSON lines or no eligible records.
    """
    eligible_records: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    ignored_records: list[dict[str, Any]] = []
    total_records = 0

    with index_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            total_records += 1

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ConfigurationError(
                    f"Invalid JSON in index file at line {line_number}: {exc}"
                ) from exc

            if not isinstance(record, dict):
                raise ConfigurationError(
                    f"Invalid NDJSON object at line {line_number}: expected JSON object."
                )

            download_status = record.get("download_status")
            if download_status not in ELIGIBLE_DOWNLOAD_STATUSES:
                ignored_records.append(
                    make_item_base(record)
                    | {
                        "status": "ignored_not_downloaded",
                        "error": None,
                        "line_number": line_number,
                        "download_status": download_status,
                    }
                )
                continue

            corpus_id = record.get("corpus_id")
            if not isinstance(corpus_id, str) or not corpus_id.strip():
                invalid_records.append(
                    make_item_base(record)
                    | {
                        "corpus_id": corpus_id,
                        "status": "failed_metadata",
                        "error": "Eligible record is missing non-empty corpus_id.",
                        "line_number": line_number,
                    }
                )
                continue

            eligible_records.append(record)

    if not eligible_records and not invalid_records:
        raise ConfigurationError("No eligible records found in input index.")

    return eligible_records, invalid_records, total_records, len(ignored_records), ignored_records


def resolve_source_video_path(record: dict[str, Any], input_dir: Path) -> Path:
    """
    Resolve source video path using video_file or fallback input directory.

    Args:
        record: One valid eligible index record.
        input_dir: Fallback directory containing "<corpus_id>.mp4" files.

    Returns:
        Path to the preferred source video. A present and non-blank video_file is
        used first; otherwise the fallback path is returned.

    I/O:
        Does not check existence.

    Error behaviour:
        Raises KeyError if corpus_id is absent, which should not happen after
        metadata validation.
    """
    video_file = record.get("video_file")
    if isinstance(video_file, str) and video_file.strip():
        video_path = Path(video_file.strip())
        return resolve_script_relative_path(video_path)

    corpus_id = str(record["corpus_id"])
    return input_dir / f"{corpus_id}{INPUT_VIDEO_EXTENSION}"


def plan_audio_extractions(
        records: list[dict[str, Any]],
        input_dir: Path,
        output_dir: Path,
        test_mode: bool,
        test_limit: int,
        reprocess: bool,
        start_corpus_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Create planned, skipped, and missing-input debate audio extraction records.

    Args:
        records: Valid eligible metadata records, in input order.
        input_dir: Fallback source video directory.
        output_dir: Destination audio directory.
        test_mode: Whether to limit planned extraction attempts.
        test_limit: Maximum number of extraction attempts in test mode.
        reprocess: Whether to overwrite existing output audio.
        start_corpus_id: Optional corpus_id from which to start planning.

    Returns:
        Tuple of planned extraction items, skipped-existing items, and
        missing-input items.

    I/O:
        Checks source and output file existence.

    Error behaviour:
        Raises ConfigurationError if start_corpus_id is not found.
    """
    if start_corpus_id:
        start_index = None
        for index, record in enumerate(records):
            if record.get("corpus_id") == start_corpus_id:
                start_index = index
                break

        if start_index is None:
            raise ConfigurationError(
                f"--start-corpus-id was not found among eligible records: {start_corpus_id}"
            )

        records = records[start_index:]

    planned: list[dict[str, Any]] = []
    skipped_existing: list[dict[str, Any]] = []
    missing_input: list[dict[str, Any]] = []

    for record in records:
        corpus_id = str(record["corpus_id"])
        input_path = resolve_source_video_path(record, input_dir)
        output_path = output_dir / f"{corpus_id}{OUTPUT_AUDIO_EXTENSION}"

        item = {
            "record": record,
            "corpus_id": corpus_id,
            "input_path": input_path,
            "output_path": output_path,
        }

        if not input_path.exists():
            missing_input.append(item)
            continue

        if output_path.exists() and not reprocess:
            skipped_existing.append(item)
            continue

        planned.append(item)

    if test_mode:
        planned = planned[:test_limit]

    return planned, skipped_existing, missing_input


def build_ffmpeg_command(input_path: Path, output_path: Path) -> list[str]:
    """
    Build the ffmpeg command for one Whisper-ready WAV extraction.

    Args:
        input_path: Source video path.
        output_path: Destination WAV path.

    Returns:
        List of subprocess arguments.

    I/O:
        Does not run the command.

    Error behaviour:
        Does not validate filesystem state.
    """
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        *FFMPEG_AUDIO_ARGS,
        str(output_path),
    ]


def extract_one_audio(
        corpus_id: str,
        input_path: Path,
        output_path: Path,
        timeout: int,
        max_retries: int,
        retry_delay: int,
        logger: logging.Logger,
) -> dict[str, Any]:
    """
    Extract one Whisper-ready WAV audio file with ffmpeg.

    Args:
        corpus_id: Stable debate identifier.
        input_path: Source video path.
        output_path: Destination WAV path.
        timeout: Per-attempt timeout in seconds.
        max_retries: Number of retries after the initial failed attempt.
        retry_delay: Delay between failed attempts in seconds.
        logger: Configured programme logger.

    Returns:
        Structured manifest result containing status, timing, command, attempts,
        return code, retries used, error summary, and output file size.

    I/O:
        Runs ffmpeg as a subprocess and writes the output WAV file.

    Error behaviour:
        Does not raise for ffmpeg failures; returns status "failed".
    """
    command = build_ffmpeg_command(input_path, output_path)
    start_time = utc_timestamp()
    monotonic_start = time.monotonic()
    attempts: list[dict[str, Any]] = []

    output_path.parent.mkdir(parents=True, exist_ok=True)

    final_return_code: int | None = None
    final_error: str | None = None
    retries_used = 0

    total_attempts = max_retries + 1

    for attempt_number in range(1, total_attempts + 1):
        logger.info("Attempt %s/%s for %s", attempt_number, total_attempts, corpus_id)
        attempt_start = utc_timestamp()
        attempt_monotonic_start = time.monotonic()

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=timeout,
            )

            attempt_duration = round(time.monotonic() - attempt_monotonic_start, 3)
            stderr_tail = tail_text(completed.stderr)
            stdout_tail = tail_text(completed.stdout)

            attempt = {
                "attempt": attempt_number,
                "start_time": attempt_start,
                "end_time": utc_timestamp(),
                "duration_seconds": attempt_duration,
                "return_code": completed.returncode,
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
                "timed_out": False,
                "error": None if completed.returncode == 0 else summarise_error(completed.stderr),
            }
            attempts.append(attempt)

            final_return_code = completed.returncode
            final_error = attempt["error"]

            if completed.returncode == 0:
                end_time = utc_timestamp()
                duration = round(time.monotonic() - monotonic_start, 3)
                output_size = output_path.stat().st_size if output_path.exists() else None

                logger.info("SUCCESS %s -> %s", corpus_id, output_path)

                return {
                    "corpus_id": corpus_id,
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                    "status": "success",
                    "error": None,
                    "return_code": 0,
                    "retries": retries_used,
                    "duration_seconds": duration,
                    "start_time": start_time,
                    "end_time": end_time,
                    "output_file_size_bytes": output_size,
                    "metadata": {
                        "command": command,
                        "attempts": attempts,
                    },
                }

            logger.error("FAILED attempt %s for %s: %s", attempt_number, corpus_id, final_error)

        except subprocess.TimeoutExpired as exc:
            attempt_duration = round(time.monotonic() - attempt_monotonic_start, 3)
            final_return_code = None
            final_error = f"ffmpeg timed out after {timeout} seconds"

            attempts.append(
                {
                    "attempt": attempt_number,
                    "start_time": attempt_start,
                    "end_time": utc_timestamp(),
                    "duration_seconds": attempt_duration,
                    "return_code": None,
                    "stdout_tail": tail_text(exc.stdout),
                    "stderr_tail": tail_text(exc.stderr),
                    "timed_out": True,
                    "error": final_error,
                }
            )
            logger.error("TIMEOUT attempt %s for %s: %s", attempt_number, corpus_id, final_error)

        except OSError as exc:
            final_return_code = None
            final_error = f"Could not run ffmpeg: {exc}"
            attempts.append(
                {
                    "attempt": attempt_number,
                    "start_time": attempt_start,
                    "end_time": utc_timestamp(),
                    "duration_seconds": round(time.monotonic() - attempt_monotonic_start, 3),
                    "return_code": None,
                    "stdout_tail": "",
                    "stderr_tail": "",
                    "timed_out": False,
                    "error": final_error,
                }
            )
            logger.error("ERROR attempt %s for %s: %s", attempt_number, corpus_id, final_error)

        if attempt_number < total_attempts:
            retries_used += 1
            logger.info("Retrying %s after %s seconds", corpus_id, retry_delay)
            if retry_delay:
                time.sleep(retry_delay)

    end_time = utc_timestamp()
    duration = round(time.monotonic() - monotonic_start, 3)
    output_size = output_path.stat().st_size if output_path.exists() else None

    logger.error("FAILED %s -> %s: %s", corpus_id, output_path, final_error)

    return {
        "corpus_id": corpus_id,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "status": "failed",
        "error": final_error or "ffmpeg failed",
        "return_code": final_return_code,
        "retries": retries_used,
        "duration_seconds": duration,
        "start_time": start_time,
        "end_time": end_time,
        "output_file_size_bytes": output_size,
        "metadata": {
            "command": command,
            "attempts": attempts,
        },
    }


def tail_text(value: Any, limit: int = 4000) -> str:
    """Return a compact tail string for stdout/stderr values without performing I/O."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value).strip()
    return text[-limit:]


def summarise_error(stderr: str | None, limit: int = 500) -> str:
    """Return a short stderr-derived error summary without performing I/O."""
    if not stderr:
        return "ffmpeg returned a non-zero exit code."

    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    if not lines:
        return "ffmpeg returned a non-zero exit code."

    return lines[-1][-limit:]


def make_item_base(record: dict[str, Any]) -> dict[str, Any]:
    """
    Create a metadata-preserving base item dictionary.

    Args:
        record: Input metadata record.

    Returns:
        Dictionary with selected metadata fields.

    I/O:
        None.

    Error behaviour:
        Does not raise for missing fields.
    """
    return {field: record.get(field) for field in PRESERVED_METADATA_FIELDS if field in record}


def make_missing_input_result(item: dict[str, Any], logger: logging.Logger) -> dict[str, Any]:
    """Create a manifest item for a missing input video and log the error."""
    record = item["record"]
    input_path = item["input_path"]
    output_path = item["output_path"]
    error = f"Source video file is missing: {input_path}"

    logger.error("MISSING_INPUT %s: %s", item["corpus_id"], input_path)

    return make_item_base(record) | {
        "corpus_id": item["corpus_id"],
        "input_path": str(input_path),
        "output_path": str(output_path),
        "status": "missing_input",
        "error": error,
        "return_code": None,
        "retries": 0,
        "duration_seconds": None,
        "start_time": None,
        "end_time": None,
        "output_file_size_bytes": output_path.stat().st_size if output_path.exists() else None,
        "metadata": {
            "command": None,
            "attempts": [],
        },
    }


def make_skipped_existing_result(item: dict[str, Any], logger: logging.Logger) -> dict[str, Any]:
    """Create a manifest item for an existing skipped WAV and log the skip."""
    record = item["record"]
    input_path = item["input_path"]
    output_path = item["output_path"]

    logger.info("SKIPPED_EXISTING %s -> %s", item["corpus_id"], output_path)

    return make_item_base(record) | {
        "corpus_id": item["corpus_id"],
        "input_path": str(input_path),
        "output_path": str(output_path),
        "status": "skipped_existing",
        "error": None,
        "return_code": None,
        "retries": 0,
        "duration_seconds": 0,
        "start_time": None,
        "end_time": None,
        "output_file_size_bytes": output_path.stat().st_size if output_path.exists() else None,
        "metadata": {
            "command": build_ffmpeg_command(input_path, output_path),
            "attempts": [],
        },
    }


def merge_result_with_record(record: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Merge preserved input metadata into an extraction result without performing I/O."""
    return make_item_base(record) | result


def make_audio_index_record(
        item_result: dict[str, Any],
        run_id: str,
        ffmpeg_info: dict[str, Any],
) -> dict[str, Any]:
    """
    Build one curated audio index record.

    Args:
        item_result: Manifest item result.
        run_id: Current run ID.
        ffmpeg_info: ffmpeg availability/version metadata.

    Returns:
        NDJSON-ready audio index record.

    I/O:
        None.

    Error behaviour:
        Does not raise for missing optional metadata.
    """
    record = {field: item_result.get(field) for field in PRESERVED_METADATA_FIELDS if field in item_result}

    record.update(
        {
            "source_video_file": path_for_index(item_result.get("input_path")),
            "audio_file": path_for_index(item_result.get("output_path")),
            "audio_format": OUTPUT_AUDIO_FORMAT,
            "audio_codec": FFMPEG_AUDIO_CODEC,
            "audio_channels": int(FFMPEG_AUDIO_CHANNELS),
            "audio_sample_rate": int(FFMPEG_AUDIO_SAMPLE_RATE),
            "audio_sample_format": FFMPEG_AUDIO_SAMPLE_FORMAT,
            "audio_file_size_bytes": item_result.get("output_file_size_bytes"),
            "audio_extraction_status": item_result.get("status"),
            "audio_extraction_run_id": run_id,
            "audio_extracted_at_utc": item_result.get("end_time"),
            "ffmpeg_version": ffmpeg_info.get("version"),
            "video_download_status": item_result.get("download_status"),
            "metadata_status": item_result.get("metadata_status"),
            "error": item_result.get("error"),
        }
    )

    return record


def write_audio_index(index_records: list[dict[str, Any]], audio_index_file: Path) -> None:
    """
    Write the curated NDJSON audio index.

    Args:
        index_records: List of JSON-serialisable index records.
        audio_index_file: Destination NDJSON path.

    Returns:
        None.

    I/O:
        Creates parent directory and overwrites the NDJSON file.

    Error behaviour:
        Propagates OSError and JSON serialisation errors.
    """
    audio_index_file.parent.mkdir(parents=True, exist_ok=True)
    with audio_index_file.open("w", encoding="utf-8") as handle:
        for record in index_records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=False) + "\n")


def write_manifests(
        manifest: dict[str, Any],
        manifest_file: Path,
        run_id: str,
) -> tuple[Path, Path]:
    """
    Write latest and per-run manifest files.

    Args:
        manifest: JSON-serialisable manifest dictionary.
        manifest_file: Latest manifest path, overwritten each run.
        run_id: Current run ID for the timestamped manifest filename.

    Returns:
        Tuple of latest manifest path and per-run manifest path.

    I/O:
        Writes two JSON files.

    Error behaviour:
        Propagates OSError and JSON serialisation errors.
    """
    manifest_file.parent.mkdir(parents=True, exist_ok=True)

    per_run_manifest_file = (
            manifest_file.parent / f"{manifest_file.stem}_{run_id}{manifest_file.suffix}"
    )

    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False)

    manifest_file.write_text(manifest_json + "\n", encoding="utf-8")
    per_run_manifest_file.write_text(manifest_json + "\n", encoding="utf-8")

    return manifest_file, per_run_manifest_file


def build_run_metadata(
        args: argparse.Namespace,
        run_id: str,
        start_time: str,
        ffmpeg_info: dict[str, Any] | None,
        summary: dict[str, int],
        interrupted: bool = False,
        end_time: str | None = None,
) -> dict[str, Any]:
    """Construct the run_metadata section of the JSON manifest."""
    return {
        "run_id": run_id,
        "tool_name": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "start_time": start_time,
        "end_time": end_time,
        "test_mode": args.test_mode,
        "test_limit": args.test_limit,
        "reprocess": args.reprocess,
        "workers": args.workers,
        "index_path": str(args.index),
        "input_dir": str(args.input_dir),
        "output_dir": str(args.output_dir),
        "audio_index_file": str(args.audio_index_file),
        "log_file": str(args.log_file),
        "manifest_file": str(args.manifest_file),
        "config": {
            "output_format": OUTPUT_AUDIO_FORMAT,
            "audio_channels": int(FFMPEG_AUDIO_CHANNELS),
            "audio_sample_rate": int(FFMPEG_AUDIO_SAMPLE_RATE),
            "audio_codec": FFMPEG_AUDIO_CODEC,
            "audio_sample_format": FFMPEG_AUDIO_SAMPLE_FORMAT,
            "timeout_seconds": args.timeout,
            "max_retries": args.max_retries,
            "retry_delay_seconds": args.retry_delay,
            "start_corpus_id": args.start_corpus_id,
        },
        "ffmpeg": ffmpeg_info or {"available": False, "version": None},
        "summary": summary,
        "interrupted": interrupted,
    }


def make_summary(
        input_records: int,
        eligible_records: int,
        ignored_records: int,
        invalid_records: int,
        planned_items: int,
        attempted_items: int,
        succeeded: int,
        failed: int,
        missing_input: int,
        skipped_existing: int,
) -> dict[str, int]:
    """Create a manifest summary dictionary without performing I/O."""
    return {
        "input_records": input_records,
        "eligible_records": eligible_records,
        "ignored_records": ignored_records,
        "invalid_records": invalid_records,
        "planned_items": planned_items,
        "attempted_items": attempted_items,
        "succeeded": succeeded,
        "failed": failed,
        "missing_input": missing_input,
        "skipped_existing": skipped_existing,
    }


def main() -> int:
    """
    Run the batch Jubilee debate audio extraction workflow.

    Returns:
        Process exit code:
            0 for clean completion;
            1 for per-item errors;
            2 for configuration/validation errors;
            130 for keyboard interruption.

    I/O:
        Reads the input index, checks filesystem state, runs ffmpeg, writes WAV
        files, appends logs, writes manifests, and writes the audio index.

    Error behaviour:
        Handles expected configuration, per-item, and keyboard interrupt errors.
    """
    logger: logging.Logger | None = None
    args: argparse.Namespace | None = None
    run_id = make_run_id()
    start_time = utc_timestamp()
    ffmpeg_info: dict[str, Any] | None = None

    manifest_items: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    ignored_records: list[dict[str, Any]] = []

    total_records = 0
    eligible_count = 0
    ignored_count = 0
    planned_count = 0
    attempted_count = 0

    try:
        args = parse_args()
        validate_args(args)
        logger = setup_logging(args.log_file)

        logger.info("Starting %s run_id=%s", TOOL_NAME, run_id)
        logger.info("Input index: %s", args.index)
        logger.info("Input video directory: %s", args.input_dir)
        logger.info("Output directory: %s", args.output_dir)
        logger.info(
            "Audio format: %s; channels=%s; sample_rate=%s; codec=%s; sample_fmt=%s",
            OUTPUT_AUDIO_FORMAT,
            FFMPEG_AUDIO_CHANNELS,
            FFMPEG_AUDIO_SAMPLE_RATE,
            FFMPEG_AUDIO_CODEC,
            FFMPEG_AUDIO_SAMPLE_FORMAT,
        )
        logger.info("Test mode: %s; test_limit=%s", args.test_mode, args.test_limit)
        logger.info("Reprocess: %s", args.reprocess)
        logger.info("Start corpus ID: %s", args.start_corpus_id)

        ffmpeg_info = check_ffmpeg()
        logger.info("ffmpeg version: %s", ffmpeg_info["version"])

        eligible_records, invalid_records, total_records, ignored_count, ignored_records = load_debate_index(
            args.index
        )
        eligible_count = len(eligible_records) + len(invalid_records)

        logger.info(
            "Loaded records: input=%s eligible=%s ignored=%s invalid=%s",
            total_records,
            eligible_count,
            ignored_count,
            len(invalid_records),
        )

        for invalid_record in invalid_records:
            logger.error(
                "FAILED_METADATA line=%s corpus_id=%s error=%s",
                invalid_record.get("line_number"),
                invalid_record.get("corpus_id"),
                invalid_record.get("error"),
            )

        planned, skipped_existing, missing_input = plan_audio_extractions(
            records=eligible_records,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            test_mode=args.test_mode,
            test_limit=args.test_limit,
            reprocess=args.reprocess,
            start_corpus_id=args.start_corpus_id,
        )

        planned_count = len(planned)
        logger.info(
            "Planning complete: planned=%s skipped_existing=%s missing_input=%s",
            len(planned),
            len(skipped_existing),
            len(missing_input),
        )

        for item in skipped_existing:
            manifest_items.append(make_skipped_existing_result(item, logger))

        for item in missing_input:
            manifest_items.append(make_missing_input_result(item, logger))

        for item in planned:
            attempted_count += 1
            result = extract_one_audio(
                corpus_id=item["corpus_id"],
                input_path=item["input_path"],
                output_path=item["output_path"],
                timeout=args.timeout,
                max_retries=args.max_retries,
                retry_delay=args.retry_delay,
                logger=logger,
            )
            manifest_items.append(merge_result_with_record(item["record"], result))

        succeeded = sum(1 for item in manifest_items if item.get("status") == "success")
        failed = sum(1 for item in manifest_items if item.get("status") == "failed")
        missing_count = sum(1 for item in manifest_items if item.get("status") == "missing_input")
        skipped_count = sum(1 for item in manifest_items if item.get("status") == "skipped_existing")

        audio_index_records = [
            make_audio_index_record(item, run_id, ffmpeg_info)
            for item in [*manifest_items, *invalid_records]
            if item.get("status")
               in {"success", "failed", "skipped_existing", "missing_input", "failed_metadata"}
        ]
        write_audio_index(audio_index_records, args.audio_index_file)
        logger.info("Wrote audio index: %s", args.audio_index_file)

        summary = make_summary(
            input_records=total_records,
            eligible_records=eligible_count,
            ignored_records=ignored_count,
            invalid_records=len(invalid_records),
            planned_items=planned_count,
            attempted_items=attempted_count,
            succeeded=succeeded,
            failed=failed,
            missing_input=missing_count,
            skipped_existing=skipped_count,
        )

        manifest = {
            "run_metadata": build_run_metadata(
                args=args,
                run_id=run_id,
                start_time=start_time,
                end_time=utc_timestamp(),
                ffmpeg_info=ffmpeg_info,
                summary=summary,
                interrupted=False,
            ),
            "items": manifest_items,
            "invalid_records": invalid_records,
            "ignored_records": ignored_records,
        }

        latest_manifest, per_run_manifest = write_manifests(manifest, args.manifest_file, run_id)
        logger.info("Wrote latest manifest: %s", latest_manifest)
        logger.info("Wrote per-run manifest: %s", per_run_manifest)
        logger.info(
            "Finished run: succeeded=%s failed=%s skipped_existing=%s missing_input=%s invalid_records=%s",
            succeeded,
            failed,
            skipped_count,
            missing_count,
            len(invalid_records),
        )

        if failed or missing_count or invalid_records:
            return 1

        return 0

    except KeyboardInterrupt:
        if logger:
            logger.error("Interrupted by user.")

        if args:
            summary = make_summary(
                input_records=total_records,
                eligible_records=eligible_count,
                ignored_records=ignored_count,
                invalid_records=len(invalid_records),
                planned_items=planned_count,
                attempted_items=attempted_count,
                succeeded=sum(1 for item in manifest_items if item.get("status") == "success"),
                failed=sum(1 for item in manifest_items if item.get("status") == "failed"),
                missing_input=sum(1 for item in manifest_items if item.get("status") == "missing_input"),
                skipped_existing=sum(
                    1 for item in manifest_items if item.get("status") == "skipped_existing"
                ),
            )

            manifest = {
                "run_metadata": build_run_metadata(
                    args=args,
                    run_id=run_id,
                    start_time=start_time,
                    end_time=utc_timestamp(),
                    ffmpeg_info=ffmpeg_info,
                    summary=summary,
                    interrupted=True,
                ),
                "items": manifest_items,
                "invalid_records": invalid_records,
                "ignored_records": ignored_records,
            }

            try:
                write_manifests(manifest, args.manifest_file, run_id)
            except Exception as exc:  # noqa: BLE001 - best-effort interrupt manifest
                if logger:
                    logger.error("Could not write interrupted manifest: %s", exc)

        return 130

    except ConfigurationError as exc:
        message = f"Configuration error: {exc}"
        if logger:
            logger.error(message)
        else:
            print(message, file=sys.stderr)
        return 2

    except Exception as exc:  # noqa: BLE001 - final safety net for clear batch exit
        message = f"Unexpected error: {exc}"
        if logger:
            logger.exception(message)
        else:
            print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())