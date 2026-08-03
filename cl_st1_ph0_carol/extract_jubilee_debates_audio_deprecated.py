#!/usr/bin/env python3
"""
Extract full-length audio from downloaded Jubilee debate videos.

This script reads the curated Jubilee debate index produced by
download_jubilee_debates.py, locates successfully downloaded video files, and
extracts one full-length audio file per eligible debate using ffmpeg.

The default audio profile is "gemini_flac", which produces stereo 44.1 kHz FLAC
audio for Gemini 1.5 Pro transcription and speaker-turn differentiation tests.
The script also supports "gemini_wav" and "whisper_wav" profiles.

This script intentionally does not segment audio. Audio segmentation should be
handled by a later pipeline programme so that segment duration, chapter-based
splitting, Gemini upload constraints, and timestamp offsets can be handled
separately.

By default, the script runs in test mode and processes up to 5 planned debates.
Existing output audio files are skipped unless --reprocess is provided, making
the script safe to re-run.

Example:
    python extract_jubilee_debates_audio.py

Full run:
    python extract_jubilee_debates_audio.py --no-test-mode

Whisper-compatible extraction:
    python extract_jubilee_debates_audio.py --profile whisper_wav --no-test-mode

Resume from a specific debate:
    python extract_jubilee_debates_audio.py --no-test-mode --start-corpus-id jubilee_surrounded_003
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

DEFAULT_PROFILE = "gemini_flac"
SUPPORTED_PROFILES = ("gemini_flac", "gemini_wav", "whisper_wav")

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 7200
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

INPUT_VIDEO_EXTENSION = ".mp4"

PROFILE_CONFIGS: dict[str, dict[str, Any]] = {
    "gemini_flac": {
        "output_subdir": "gemini_flac",
        "output_extension": ".flac",
        "output_format": "flac",
        "audio_channels": 2,
        "audio_sample_rate": 44100,
        "audio_codec": "flac",
        "audio_sample_format": None,
        "ffmpeg_args": [
            "-vn",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-c:a",
            "flac",
        ],
    },
    "gemini_wav": {
        "output_subdir": "gemini_wav",
        "output_extension": ".wav",
        "output_format": "wav",
        "audio_channels": 2,
        "audio_sample_rate": 44100,
        "audio_codec": "pcm_s16le",
        "audio_sample_format": "s16",
        "ffmpeg_args": [
            "-vn",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-c:a",
            "pcm_s16le",
        ],
    },
    "whisper_wav": {
        "output_subdir": "whisper_wav",
        "output_extension": ".wav",
        "output_format": "wav",
        "audio_channels": 1,
        "audio_sample_rate": 16000,
        "audio_codec": "pcm_s16le",
        "audio_sample_format": "s16",
        "ffmpeg_args": [
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-sample_fmt",
            "s16",
        ],
    },
}

ELIGIBLE_DOWNLOAD_STATUSES = ("success", "skipped_existing")

PRESERVED_INPUT_FIELDS = (
    "corpus_id",
    "debate_format",
    "sample_group",
    "sample_order",
    "title_selected",
    "title_extracted",
    "youtube_id",
    "youtube_url",
    "webpage_url",
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
    """Raised when command-line arguments or environment configuration are invalid."""


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp using a trailing Z."""
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def make_run_id() -> str:
    """Return a compact UTC run identifier."""
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def path_to_str(path: Path | None) -> str | None:
    """Convert a Path to a POSIX-style string, preserving None."""
    if path is None:
        return None
    return path.as_posix()


def resolve_script_relative_path(path: Path) -> Path:
    """
    Resolve a path relative to the programme directory.

    Parameters:
        path: Absolute or relative path.

    Returns:
        Absolute paths unchanged; relative paths resolved under SCRIPT_DIR.

    Performs I/O:
        No.

    Error behaviour:
        None.
    """
    if path.is_absolute():
        return path
    return SCRIPT_DIR / path


def short_error(stderr: str, stdout: str = "", limit: int = 1000) -> str:
    """Return a compact single-line process error summary."""
    text = stderr.strip() or stdout.strip() or "Unknown error"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "Unknown error"

    interesting = [
        line for line in lines
        if "ERROR:" in line or "Error" in line or "error" in line
    ]
    selected = interesting[-1] if interesting else lines[-1]
    return selected[:limit]


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments and resolve paths.

    Returns:
        argparse.Namespace containing resolved configuration values.

    Performs I/O:
        No direct file reads or writes.

    Error behaviour:
        argparse exits for malformed CLI syntax.
    """
    parser = argparse.ArgumentParser(
        description="Extract full-length audio from downloaded Jubilee debate videos."
    )

    parser.add_argument(
        "--index",
        type=Path,
        default=Path(DEFAULT_INDEX_PATH),
        help="Path to the NDJSON curated debate index.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(DEFAULT_INPUT_DIR),
        help="Directory containing source video files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR),
        help="Base output directory for extracted audio, logs, manifests, and index.",
    )
    parser.add_argument(
        "--profile",
        choices=SUPPORTED_PROFILES,
        default=DEFAULT_PROFILE,
        help="Audio extraction profile.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path(DEFAULT_LOG_FILE),
        help="Append-only log file path.",
    )
    parser.add_argument(
        "--manifest-file",
        type=Path,
        default=Path(DEFAULT_MANIFEST_FILE),
        help="Latest JSON manifest file path.",
    )
    parser.add_argument(
        "--audio-index-file",
        type=Path,
        default=Path(DEFAULT_AUDIO_INDEX_FILE),
        help="Curated NDJSON audio index file path.",
    )

    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument(
        "--test-mode",
        dest="test_mode",
        action="store_true",
        help="Enable test mode.",
    )
    test_group.add_argument(
        "--no-test-mode",
        dest="test_mode",
        action="store_false",
        help="Disable test mode.",
    )
    parser.set_defaults(test_mode=DEFAULT_TEST_MODE)

    parser.add_argument(
        "--test-limit",
        type=int,
        default=DEFAULT_TEST_LIMIT,
        help="Maximum number of planned records processed in test mode.",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Re-run ffmpeg and overwrite existing audio outputs.",
    )
    parser.add_argument(
        "--start-corpus-id",
        default=None,
        help="Start planning from this corpus_id, preserving input order.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Number of workers. Only 1 is supported in this implementation.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Maximum seconds allowed for one ffmpeg process.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Number of retries after a failed ffmpeg attempt.",
    )
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=DEFAULT_RETRY_DELAY_SECONDS,
        help="Seconds to wait between retry attempts.",
    )

    args = parser.parse_args()

    args.index = resolve_script_relative_path(args.index)
    args.input_dir = resolve_script_relative_path(args.input_dir)
    args.output_dir = resolve_script_relative_path(args.output_dir)
    args.log_file = resolve_script_relative_path(args.log_file)
    args.manifest_file = resolve_script_relative_path(args.manifest_file)
    args.audio_index_file = resolve_script_relative_path(args.audio_index_file)

    return args


def setup_logging(log_file: Path) -> logging.Logger:
    """
    Configure append-only UTF-8 logging.

    Parameters:
        log_file: Destination log file.

    Returns:
        Configured logger.

    Performs I/O:
        Creates the log directory and opens the log file in append mode.

    Error behaviour:
        Lets OSError propagate if logging cannot be configured.
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
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def ensure_output_dirs(output_dir: Path, profile: str) -> dict[str, Path]:
    """
    Create the output directory structure for the selected profile.

    Parameters:
        output_dir: Base audio output directory.
        profile: Selected audio profile name.

    Returns:
        Mapping of logical directory names to paths.

    Performs I/O:
        Creates directories if needed.

    Error behaviour:
        Lets OSError propagate if directory creation fails.
    """
    profile_config = get_audio_profile_config(profile)
    dirs = {
        "output": output_dir,
        "profile_output": output_dir / profile_config["output_subdir"],
    }

    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)

    return dirs


def validate_args(args: argparse.Namespace) -> None:
    """
    Validate command-line arguments and filesystem paths.

    Parameters:
        args: Parsed command-line arguments.

    Returns:
        None.

    Performs I/O:
        Checks file and directory existence/readability.

    Error behaviour:
        Raises ConfigurationError for invalid configuration.
    """
    if args.profile not in SUPPORTED_PROFILES:
        raise ConfigurationError(f"Unsupported profile: {args.profile}")

    if not args.index.exists():
        raise ConfigurationError(f"Input index file does not exist: {args.index}")
    if not args.index.is_file():
        raise ConfigurationError(f"Input index path is not a file: {args.index}")

    try:
        with args.index.open("r", encoding="utf-8"):
            pass
    except OSError as exc:
        raise ConfigurationError(f"Input index file is unreadable: {args.index}") from exc

    if not args.input_dir.exists():
        raise ConfigurationError(f"Input video directory does not exist: {args.input_dir}")
    if not args.input_dir.is_dir():
        raise ConfigurationError(f"Input video path is not a directory: {args.input_dir}")

    if args.test_limit <= 0:
        raise ConfigurationError("--test-limit must be greater than zero")
    if args.workers <= 0:
        raise ConfigurationError("--workers must be greater than zero")
    if args.workers != 1:
        raise ConfigurationError("Only --workers 1 is supported in this implementation")
    if args.timeout <= 0:
        raise ConfigurationError("--timeout must be greater than zero")
    if args.max_retries < 0:
        raise ConfigurationError("--max-retries must be zero or greater")
    if args.retry_delay < 0:
        raise ConfigurationError("--retry-delay must be zero or greater")

    if args.start_corpus_id is not None and not args.start_corpus_id.strip():
        raise ConfigurationError("--start-corpus-id cannot be empty")


def check_ffmpeg() -> dict[str, Any]:
    """
    Check whether ffmpeg is available and return version metadata.

    Returns:
        Dictionary with availability, executable, and version information.

    Performs I/O:
        Executes "ffmpeg -version".

    Error behaviour:
        Raises ConfigurationError if ffmpeg is unavailable or fails.
    """
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise ConfigurationError("ffmpeg is not available on the system PATH")

    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ConfigurationError(f"Failed to run ffmpeg -version: {exc}") from exc

    if result.returncode != 0:
        raise ConfigurationError(
            f"ffmpeg -version failed: {short_error(result.stderr, result.stdout)}"
        )

    version_line = result.stdout.splitlines()[0] if result.stdout.splitlines() else "unknown"
    return {
        "available": True,
        "version": version_line,
        "executable": executable,
    }


def load_debate_index(
        index_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int, list[dict[str, Any]]]:
    """
    Load and validate eligible debate records from the NDJSON source index.

    Parameters:
        index_path: Path to the curated debate NDJSON index.

    Returns:
        Tuple containing:
            eligible valid records,
            invalid eligible record descriptors,
            total input record count,
            ignored record count,
            ignored record descriptors.

    Performs I/O:
        Reads the index file.

    Error behaviour:
        Raises ConfigurationError for invalid JSON lines.
        Rows missing required metadata are returned as invalid records.
    """
    eligible_records: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    ignored_records: list[dict[str, Any]] = []
    total_records = 0
    ignored_count = 0

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
                    f"Invalid JSON on line {line_number}: {exc}"
                ) from exc

            if not isinstance(record, dict):
                invalid_records.append(
                    {
                        "line_number": line_number,
                        "status": "failed_metadata",
                        "error": "Line is not a JSON object",
                        "record": record,
                    }
                )
                continue

            download_status = record.get("download_status")
            if download_status not in ELIGIBLE_DOWNLOAD_STATUSES:
                ignored_count += 1
                ignored_records.append(
                    {
                        "line_number": line_number,
                        "corpus_id": record.get("corpus_id"),
                        "download_status": download_status,
                        "status": "ignored_not_downloaded",
                        "record": record,
                    }
                )
                continue

            if not str(record.get("corpus_id", "")).strip():
                invalid_records.append(
                    {
                        "line_number": line_number,
                        "status": "failed_metadata",
                        "error": "Missing required field: corpus_id",
                        "record": record,
                    }
                )
                continue

            record["_line_number"] = line_number
            eligible_records.append(record)

    return eligible_records, invalid_records, total_records, ignored_count, ignored_records


def get_audio_profile_config(profile: str) -> dict[str, Any]:
    """
    Return ffmpeg and output configuration for the selected audio profile.

    Parameters:
        profile: Profile name.

    Returns:
        Profile configuration dictionary.

    Performs I/O:
        No.

    Error behaviour:
        Raises ConfigurationError for unsupported profiles.
    """
    try:
        return PROFILE_CONFIGS[profile]
    except KeyError as exc:
        raise ConfigurationError(f"Unsupported profile: {profile}") from exc


def resolve_source_video_path(record: dict[str, Any], input_dir: Path) -> Path:
    """
    Resolve the source video path for one input record.

    Parameters:
        record: Input debate record.
        input_dir: Fallback input video directory.

    Returns:
        Path to the expected source video.

    Performs I/O:
        No.

    Error behaviour:
        None.
    """
    corpus_id = str(record["corpus_id"])
    video_file = record.get("video_file")

    if isinstance(video_file, str) and video_file.strip():
        candidate = Path(video_file)
        if candidate.is_absolute():
            return candidate

        script_relative_candidate = resolve_script_relative_path(candidate)
        if script_relative_candidate.exists():
            return script_relative_candidate

        cwd_candidate = Path.cwd() / candidate
        if cwd_candidate.exists():
            return cwd_candidate

        return script_relative_candidate

    return input_dir / f"{corpus_id}{INPUT_VIDEO_EXTENSION}"


def plan_audio_extractions(
        records: list[dict[str, Any]],
        input_dir: Path,
        output_dir: Path,
        profile: str,
        test_mode: bool,
        test_limit: int,
        reprocess: bool,
        start_corpus_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Create planned, skipped-existing, and missing-input extraction records.

    Parameters:
        records: Eligible valid debate records.
        input_dir: Fallback source video directory.
        output_dir: Base audio output directory.
        profile: Selected audio profile.
        test_mode: Whether to limit planned extraction records.
        test_limit: Maximum planned extractions in test mode.
        reprocess: Whether to overwrite existing audio files.
        start_corpus_id: Optional corpus_id from which to start.

    Returns:
        Tuple of planned items, skipped-existing items, and missing-input items.

    Performs I/O:
        Checks source and output file existence.

    Error behaviour:
        Raises ConfigurationError when start_corpus_id is not found.
    """
    selected_records = records

    if start_corpus_id:
        start_index = None
        for index, record in enumerate(records):
            if record["corpus_id"] == start_corpus_id:
                start_index = index
                break

        if start_index is None:
            raise ConfigurationError(
                f"--start-corpus-id not found among eligible records: {start_corpus_id}"
            )

        selected_records = records[start_index:]

    profile_config = get_audio_profile_config(profile)
    profile_output_dir = output_dir / profile_config["output_subdir"]

    planned: list[dict[str, Any]] = []
    skipped_existing: list[dict[str, Any]] = []
    missing_input: list[dict[str, Any]] = []

    for record in selected_records:
        corpus_id = str(record["corpus_id"])
        input_path = resolve_source_video_path(record, input_dir)
        output_path = profile_output_dir / (
            f"{corpus_id}{profile_config['output_extension']}"
        )

        item = {
            "record": record,
            "corpus_id": corpus_id,
            "input_path": input_path,
            "output_path": output_path,
            "profile": profile,
            "profile_config": profile_config,
        }

        if not input_path.exists():
            missing_input.append(
                {
                    **item,
                    "status": "missing_input",
                    "error": f"Source video file does not exist: {input_path}",
                }
            )
            continue

        if output_path.exists() and not reprocess:
            skipped_existing.append(
                {
                    **item,
                    "status": "skipped_existing",
                    "error": None,
                }
            )
            continue

        planned.append(item)

    if test_mode:
        planned = planned[:test_limit]

    return planned, skipped_existing, missing_input


def build_ffmpeg_command(
        input_path: Path,
        output_path: Path,
        profile_config: dict[str, Any],
) -> list[str]:
    """
    Build the ffmpeg command for one audio extraction.

    Parameters:
        input_path: Source video path.
        output_path: Destination audio path.
        profile_config: Selected profile configuration.

    Returns:
        Command list suitable for subprocess.run.

    Performs I/O:
        No.

    Error behaviour:
        None.
    """
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        *profile_config["ffmpeg_args"],
        str(output_path),
    ]


def extract_one_audio(
        corpus_id: str,
        input_path: Path,
        output_path: Path,
        profile_config: dict[str, Any],
        timeout: int,
        max_retries: int,
        retry_delay: int,
        logger: logging.Logger,
) -> dict[str, Any]:
    """
    Extract one audio file with ffmpeg.

    Parameters:
        corpus_id: Stable corpus identifier.
        input_path: Source video file.
        output_path: Destination audio file.
        profile_config: Audio profile configuration.
        timeout: Per-attempt timeout in seconds.
        max_retries: Number of retries after initial failure.
        retry_delay: Delay between retry attempts.
        logger: Configured logger.

    Returns:
        Structured item execution result.

    Performs I/O:
        Creates output parent directory, runs ffmpeg, and sleeps between retries.

    Error behaviour:
        Captures subprocess failures, timeouts, and OS errors in the result.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = build_ffmpeg_command(input_path, output_path, profile_config)

    attempts: list[dict[str, Any]] = []
    overall_start = utc_now()
    start_time = utc_timestamp()
    final_return_code: int | None = None
    final_error: str | None = None
    total_attempts = max_retries + 1

    for attempt_number in range(1, total_attempts + 1):
        attempt_start = utc_now()
        logger.info(
            "ffmpeg attempt %s/%s for %s",
            attempt_number,
            total_attempts,
            corpus_id,
        )

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )

            attempt_end = utc_now()
            final_return_code = result.returncode
            final_error = (
                None if result.returncode == 0
                else short_error(result.stderr, result.stdout)
            )

            attempts.append(
                {
                    "attempt": attempt_number,
                    "return_code": result.returncode,
                    "stdout_tail": result.stdout[-4000:],
                    "stderr_tail": result.stderr[-4000:],
                    "error": final_error,
                    "duration_seconds": (attempt_end - attempt_start).total_seconds(),
                }
            )

            if result.returncode == 0:
                overall_end = utc_now()
                output_file_size = (
                    output_path.stat().st_size if output_path.exists() else None
                )
                return {
                    "status": "success",
                    "error": None,
                    "return_code": result.returncode,
                    "retries": attempt_number - 1,
                    "duration_seconds": (overall_end - overall_start).total_seconds(),
                    "start_time": start_time,
                    "end_time": overall_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "output_file_size_bytes": output_file_size,
                    "metadata": {
                        "command": command,
                        "attempts": attempts,
                    },
                }

        except subprocess.TimeoutExpired as exc:
            attempt_end = utc_now()
            final_return_code = None
            final_error = f"ffmpeg timed out after {timeout} seconds"
            attempts.append(
                {
                    "attempt": attempt_number,
                    "return_code": None,
                    "stdout_tail": (
                        (exc.stdout or "")[-4000:]
                        if isinstance(exc.stdout, str)
                        else ""
                    ),
                    "stderr_tail": (
                        (exc.stderr or "")[-4000:]
                        if isinstance(exc.stderr, str)
                        else ""
                    ),
                    "error": final_error,
                    "duration_seconds": (attempt_end - attempt_start).total_seconds(),
                }
            )

        except OSError as exc:
            attempt_end = utc_now()
            final_return_code = None
            final_error = f"Failed to execute ffmpeg: {exc}"
            attempts.append(
                {
                    "attempt": attempt_number,
                    "return_code": None,
                    "stdout_tail": "",
                    "stderr_tail": "",
                    "error": final_error,
                    "duration_seconds": (attempt_end - attempt_start).total_seconds(),
                }
            )

        if attempt_number < total_attempts:
            logger.warning(
                "Attempt %s for %s failed: %s; retrying in %s seconds",
                attempt_number,
                corpus_id,
                final_error,
                retry_delay,
            )
            time.sleep(retry_delay)

    overall_end = utc_now()
    return {
        "status": "failed",
        "error": final_error,
        "return_code": final_return_code,
        "retries": max_retries,
        "duration_seconds": (overall_end - overall_start).total_seconds(),
        "start_time": start_time,
        "end_time": overall_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "output_file_size_bytes": output_path.stat().st_size if output_path.exists() else None,
        "metadata": {
            "command": command,
            "attempts": attempts,
        },
    }


def manifest_item_from_non_extracted(
        item: dict[str, Any],
        run_metadata: dict[str, Any],
        status: str,
        error: str | None = None,
) -> dict[str, Any]:
    """Create a manifest item for skipped-existing or missing-input records."""
    record = item["record"]
    output_path = item["output_path"]
    input_path = item["input_path"]

    return {
        "corpus_id": item["corpus_id"],
        "youtube_id": record.get("youtube_id"),
        "youtube_url": record.get("youtube_url"),
        "title_selected": record.get("title_selected"),
        "title_extracted": record.get("title_extracted"),
        "debate_format": record.get("debate_format"),
        "input_path": path_to_str(input_path),
        "output_path": path_to_str(output_path),
        "profile": item["profile"],
        "status": status,
        "error": error,
        "return_code": None,
        "retries": 0,
        "duration_seconds": 0.0,
        "start_time": run_metadata["start_time"],
        "end_time": run_metadata["start_time"],
        "output_file_size_bytes": (
            output_path.stat().st_size if output_path.exists() else None
        ),
        "metadata": {
            "duration_seconds": record.get("duration_seconds"),
            "duration_string": record.get("duration_string"),
            "command": None,
            "attempts": [],
        },
    }


def build_audio_index_record(
        item: dict[str, Any],
        item_result: dict[str, Any],
        run_metadata: dict[str, Any],
        ffmpeg_info: dict[str, Any],
) -> dict[str, Any]:
    """Create one curated audio index record from input and extraction metadata."""
    record = item["record"]
    profile_config = item["profile_config"]

    audio_record = {
        field: record.get(field)
        for field in PRESERVED_INPUT_FIELDS
        if field in record
    }

    audio_record.update(
        {
            "source_video_file": path_to_str(item["input_path"]),
            "audio_file": path_to_str(item["output_path"]),
            "audio_profile": item["profile"],
            "audio_format": profile_config["output_format"],
            "audio_codec": profile_config["audio_codec"],
            "audio_channels": profile_config["audio_channels"],
            "audio_sample_rate": profile_config["audio_sample_rate"],
            "audio_sample_format": profile_config["audio_sample_format"],
            "audio_file_size_bytes": item_result.get("output_file_size_bytes"),
            "audio_extraction_status": item_result.get("status"),
            "audio_extraction_run_id": run_metadata.get("run_id"),
            "audio_extracted_at_utc": run_metadata.get("end_time")
                                      or item_result.get("end_time"),
            "ffmpeg_version": ffmpeg_info.get("version", "unknown"),
            "video_download_status": record.get("download_status"),
        }
    )

    audio_record.setdefault("chapters", record.get("chapters") or [])
    audio_record.setdefault("subtitles_files", record.get("subtitles_files") or [])
    audio_record.setdefault("notes", record.get("notes"))

    return audio_record


def write_audio_index(index_records: list[dict[str, Any]], audio_index_file: Path) -> None:
    """
    Write the curated NDJSON audio index.

    Parameters:
        index_records: Records to write.
        audio_index_file: Destination NDJSON file.

    Returns:
        None.

    Performs I/O:
        Creates the parent directory and writes the file.

    Error behaviour:
        Lets OSError propagate if writing fails.
    """
    audio_index_file.parent.mkdir(parents=True, exist_ok=True)
    with audio_index_file.open("w", encoding="utf-8") as handle:
        for record in index_records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=False))
            handle.write("\n")


def write_manifests(
        manifest: dict[str, Any],
        manifest_file: Path,
        run_id: str,
) -> tuple[Path, Path]:
    """
    Write latest and timestamped manifest files.

    Parameters:
        manifest: Full run manifest.
        manifest_file: Latest manifest path.
        run_id: UTC run identifier.

    Returns:
        Tuple of latest manifest path and timestamped manifest path.

    Performs I/O:
        Writes JSON files.

    Error behaviour:
        Lets OSError propagate if writing fails.
    """
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    run_manifest = (
            manifest_file.parent / f"{manifest_file.stem}_{run_id}{manifest_file.suffix}"
    )

    for path in (manifest_file, run_manifest):
        with path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    return manifest_file, run_manifest


def make_initial_run_metadata(
        args: argparse.Namespace,
        run_id: str,
        start_time: str,
        profile_config: dict[str, Any],
        ffmpeg_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct initial run metadata for the manifest."""
    return {
        "run_id": run_id,
        "tool_name": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "start_time": start_time,
        "end_time": None,
        "test_mode": args.test_mode,
        "test_limit": args.test_limit,
        "reprocess": args.reprocess,
        "workers": args.workers,
        "index_path": path_to_str(args.index),
        "input_dir": path_to_str(args.input_dir),
        "output_dir": path_to_str(args.output_dir),
        "audio_index_file": path_to_str(args.audio_index_file),
        "log_file": path_to_str(args.log_file),
        "manifest_file": path_to_str(args.manifest_file),
        "config": {
            "profile": args.profile,
            "output_format": profile_config["output_format"],
            "audio_channels": profile_config["audio_channels"],
            "audio_sample_rate": profile_config["audio_sample_rate"],
            "audio_codec": profile_config["audio_codec"],
            "audio_sample_format": profile_config["audio_sample_format"],
            "timeout_seconds": args.timeout,
            "max_retries": args.max_retries,
            "retry_delay_seconds": args.retry_delay,
            "start_corpus_id": args.start_corpus_id,
        },
        "ffmpeg": ffmpeg_info or {"available": False, "version": None},
        "summary": {
            "input_records": 0,
            "eligible_records": 0,
            "ignored_records": 0,
            "invalid_records": 0,
            "planned_items": 0,
            "attempted_items": 0,
            "succeeded": 0,
            "failed": 0,
            "missing_input": 0,
            "skipped_existing": 0,
        },
        "interrupted": False,
    }


def main() -> int:
    """
    Run the complete Jubilee debate audio extraction workflow.

    Returns:
        Process exit code:
            0 for success,
            1 for item/metadata failures,
            2 for configuration errors,
            130 for keyboard interruption.

    Performs I/O:
        Reads the NDJSON index, creates directories, runs ffmpeg, writes logs,
        writes the audio index, and writes manifests.

    Error behaviour:
        Converts expected configuration and I/O failures to documented exit codes.
    """
    args = parse_args()
    run_id = make_run_id()
    start_time = utc_timestamp()
    logger: logging.Logger | None = None

    profile_config = get_audio_profile_config(args.profile)
    run_metadata = make_initial_run_metadata(args, run_id, start_time, profile_config)

    manifest: dict[str, Any] = {
        "run_metadata": run_metadata,
        "items": [],
        "invalid_records": [],
        "ignored_records": [],
    }

    item_results: list[dict[str, Any]] = []
    audio_index_records: list[dict[str, Any]] = []

    try:
        ensure_output_dirs(args.output_dir, args.profile)
        logger = setup_logging(args.log_file)

        logger.info("Starting %s run_id=%s", TOOL_NAME, run_id)
        logger.info("Input index: %s", args.index)
        logger.info("Input video directory: %s", args.input_dir)
        logger.info("Output directory: %s", args.output_dir)
        logger.info(
            "Audio profile: %s; format=%s; channels=%s; sample_rate=%s; codec=%s; sample_format=%s",
            args.profile,
            profile_config["output_format"],
            profile_config["audio_channels"],
            profile_config["audio_sample_rate"],
            profile_config["audio_codec"],
            profile_config["audio_sample_format"],
        )
        logger.info("Test mode: %s; test_limit=%s", args.test_mode, args.test_limit)
        logger.info("Reprocess: %s", args.reprocess)
        logger.info("Start corpus ID: %s", args.start_corpus_id)

        validate_args(args)
        ffmpeg_info = check_ffmpeg()
        run_metadata["ffmpeg"] = ffmpeg_info
        logger.info("ffmpeg version: %s", ffmpeg_info["version"])

        (
            eligible_records,
            invalid_records,
            total_records,
            ignored_count,
            ignored_records,
        ) = load_debate_index(args.index)

        if not eligible_records:
            raise ConfigurationError("No eligible records found in input index")

        if args.start_corpus_id and not any(
                record["corpus_id"] == args.start_corpus_id
                for record in eligible_records
        ):
            raise ConfigurationError(
                f"--start-corpus-id not found among eligible records: {args.start_corpus_id}"
            )

        planned, skipped_existing, missing_input = plan_audio_extractions(
            records=eligible_records,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            profile=args.profile,
            test_mode=args.test_mode,
            test_limit=args.test_limit,
            reprocess=args.reprocess,
            start_corpus_id=args.start_corpus_id,
        )

        manifest["invalid_records"] = invalid_records
        manifest["ignored_records"] = ignored_records

        run_metadata["summary"].update(
            {
                "input_records": total_records,
                "eligible_records": len(eligible_records),
                "ignored_records": ignored_count,
                "invalid_records": len(invalid_records),
                "planned_items": len(planned),
                "missing_input": len(missing_input),
                "skipped_existing": len(skipped_existing),
            }
        )

        logger.info(
            "Loaded records: input=%s eligible=%s ignored=%s invalid=%s",
            total_records,
            len(eligible_records),
            ignored_count,
            len(invalid_records),
        )
        logger.info("Planned extractions: %s", len(planned))
        logger.info("Skipped existing items: %s", len(skipped_existing))
        logger.info("Missing input files: %s", len(missing_input))

        for item in skipped_existing:
            logger.info(
                "SKIPPED existing %s -> %s",
                item["corpus_id"],
                item["output_path"],
            )
            result = manifest_item_from_non_extracted(
                item,
                run_metadata,
                "skipped_existing",
                None,
            )
            item_results.append(result)
            audio_index_records.append(
                build_audio_index_record(item, result, run_metadata, ffmpeg_info)
            )

        for item in missing_input:
            logger.error(
                "MISSING input %s expected=%s",
                item["corpus_id"],
                item["input_path"],
            )
            result = manifest_item_from_non_extracted(
                item,
                run_metadata,
                "missing_input",
                item["error"],
            )
            item_results.append(result)
            audio_index_records.append(
                build_audio_index_record(item, result, run_metadata, ffmpeg_info)
            )

        for item in planned:
            logger.info(
                "Extracting %s: %s -> %s",
                item["corpus_id"],
                item["input_path"],
                item["output_path"],
            )

            result = extract_one_audio(
                corpus_id=item["corpus_id"],
                input_path=item["input_path"],
                output_path=item["output_path"],
                profile_config=profile_config,
                timeout=args.timeout,
                max_retries=args.max_retries,
                retry_delay=args.retry_delay,
                logger=logger,
            )

            result.update(
                {
                    "corpus_id": item["corpus_id"],
                    "youtube_id": item["record"].get("youtube_id"),
                    "youtube_url": item["record"].get("youtube_url"),
                    "title_selected": item["record"].get("title_selected"),
                    "title_extracted": item["record"].get("title_extracted"),
                    "debate_format": item["record"].get("debate_format"),
                    "input_path": path_to_str(item["input_path"]),
                    "output_path": path_to_str(item["output_path"]),
                    "profile": item["profile"],
                }
            )
            result["metadata"].update(
                {
                    "duration_seconds": item["record"].get("duration_seconds"),
                    "duration_string": item["record"].get("duration_string"),
                }
            )

            item_results.append(result)
            run_metadata["summary"]["attempted_items"] += 1

            if result["status"] == "success":
                logger.info("SUCCESS %s -> %s", item["corpus_id"], item["output_path"])
            else:
                logger.error("FAILED %s: %s", item["corpus_id"], result.get("error"))

            audio_index_records.append(
                build_audio_index_record(item, result, run_metadata, ffmpeg_info)
            )

        succeeded = sum(
            1 for item in item_results
            if item["status"] in {"success", "skipped_existing"}
        )
        failed = sum(1 for item in item_results if item["status"] == "failed")

        run_metadata["summary"]["succeeded"] = succeeded
        run_metadata["summary"]["failed"] = failed
        run_metadata["summary"]["missing_input"] = len(missing_input)
        run_metadata["summary"]["skipped_existing"] = len(skipped_existing)
        run_metadata["end_time"] = utc_timestamp()

        for record in audio_index_records:
            record["audio_extracted_at_utc"] = run_metadata["end_time"]

        manifest["items"] = item_results

        write_audio_index(audio_index_records, args.audio_index_file)
        logger.info("Wrote audio index: %s", args.audio_index_file)

        latest_manifest, run_manifest = write_manifests(
            manifest,
            args.manifest_file,
            run_id,
        )
        logger.info("Wrote latest manifest: %s", latest_manifest)
        logger.info("Wrote run manifest: %s", run_manifest)

        logger.info(
            "Finished run: succeeded=%s failed=%s skipped_existing=%s missing_input=%s invalid_records=%s",
            succeeded,
            failed,
            len(skipped_existing),
            len(missing_input),
            len(invalid_records),
        )

        if failed > 0 or missing_input or invalid_records:
            return 1

        return 0

    except KeyboardInterrupt:
        run_metadata["interrupted"] = True
        run_metadata["end_time"] = utc_timestamp()
        manifest["items"] = item_results

        if logger is not None:
            logger.error("Interrupted by user")

        try:
            write_manifests(manifest, args.manifest_file, run_id)
        except OSError:
            if logger is not None:
                logger.exception("Failed to write interrupted manifest")

        return 130

    except ConfigurationError as exc:
        message = f"Configuration error: {exc}"

        if logger is not None:
            logger.error(message)
        else:
            print(message, file=sys.stderr)

        return 2

    except OSError as exc:
        message = f"I/O error: {exc}"

        if logger is not None:
            logger.exception(message)
        else:
            print(message, file=sys.stderr)

        return 2


if __name__ == "__main__":
    sys.exit(main())