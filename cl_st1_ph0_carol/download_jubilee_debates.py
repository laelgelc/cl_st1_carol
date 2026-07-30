#!/usr/bin/env python3
"""
Download selected Jubilee debate videos and metadata for Corpus Linguistics Study 1.

This script reads debate sample metadata from an NDJSON file, validates and
deduplicates records by "corpus_id", and uses yt-dlp to download each selected
YouTube debate. Outputs are organised into a corpus directory containing videos,
raw yt-dlp metadata, descriptions, subtitles, optional comments, logs, manifests,
and a curated NDJSON index.

By default, the script runs in test mode and processes up to 5 planned records.
Existing output files are skipped unless --reprocess is provided, making the
script safe to re-run.

If YouTube requires authentication or bot confirmation, pass a Netscape-format
cookies file exported from a browser with --cookies. The script logs whether a
cookies file was provided, but never logs cookies contents.

Use --metadata-only to fetch or refresh yt-dlp metadata without downloading
video media. Use --start-corpus-id to resume planning from a specific corpus item.

Examples:
    python download_jubilee_debates.py

    python download_jubilee_debates.py --metadata-only

    python download_jubilee_debates.py --no-test-mode

    python download_jubilee_debates.py --no-test-mode --cookies env/youtube_cookies.txt

    python download_jubilee_debates.py --no-test-mode --start-corpus-id jubilee_surrounded_003

Exit codes:
    0    Completed with no failures
    1    Completed, but one or more items failed or invalid metadata was found
    2    Configuration or validation error
    130  Interrupted by user
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


TOOL_NAME = "download_jubilee_debates.py"
TOOL_VERSION = "v1"

DEFAULT_METADATA_PATH = (
    "cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson"
)
DEFAULT_OUTPUT_DIR = "cl_st1_ph0_carol/corpus/01_jubilee_debates"

DEFAULT_VIDEOS_DIR_NAME = "videos"
DEFAULT_RAW_METADATA_DIR_NAME = "metadata_raw"
DEFAULT_DESCRIPTIONS_DIR_NAME = "descriptions"
DEFAULT_SUBTITLES_DIR_NAME = "subtitles"
DEFAULT_COMMENTS_DIR_NAME = "comments"

DEFAULT_LOG_FILE = (
    "cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates.log"
)
DEFAULT_MANIFEST_FILE = (
    "cl_st1_ph0_carol/corpus/01_jubilee_debates/"
    "download_jubilee_debates_manifest.json"
)
DEFAULT_INDEX_FILE = (
    "cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson"
)

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 7200
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

YT_DLP_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"

DEFAULT_WRITE_DESCRIPTION = True
DEFAULT_WRITE_SUBS = True
DEFAULT_WRITE_AUTO_SUBS = True
DEFAULT_WRITE_COMMENTS = False
DEFAULT_SUB_LANGS = "en.*"

REQUIRED_FIELDS = ("corpus_id", "youtube_id", "youtube_url", "title", "debate_format")


class ConfigurationError(Exception):
    """Raised when command-line arguments or environment configuration are invalid."""


def utc_now() -> datetime:
    """Return the current UTC datetime with timezone information."""
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


def short_error(stderr: str, stdout: str = "", limit: int = 1000) -> str:
    """
    Extract a short error message from process stderr/stdout.

    Parameters:
        stderr: Captured standard error text.
        stdout: Captured standard output text used as fallback.
        limit: Maximum returned character count.

    Returns:
        A compact single-line error summary.
    """
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
    Parse command-line arguments.

    Returns:
        argparse.Namespace containing all command-line configuration.

    Performs I/O:
        No.

    Error behaviour:
        argparse handles malformed arguments by printing usage and exiting.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Download selected Jubilee debate videos and metadata with yt-dlp."
        )
    )

    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path(DEFAULT_METADATA_PATH),
        help="Path to the NDJSON input metadata file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR),
        help="Output directory for the downloaded corpus assets.",
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
        "--index-file",
        type=Path,
        default=Path(DEFAULT_INDEX_FILE),
        help="Curated NDJSON index file path.",
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
        help="Maximum number of planned items to process in test mode.",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Reprocess existing files instead of skipping them.",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Fetch metadata without downloading video media.",
    )
    parser.add_argument(
        "--skip-metadata",
        action="store_true",
        help="Do not request fresh yt-dlp metadata; rely on existing files.",
    )
    parser.add_argument(
        "--cookies",
        type=Path,
        default=None,
        help="Optional Netscape-format cookies file for yt-dlp.",
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
        help="Maximum seconds allowed for one yt-dlp process.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Number of retries after a failed yt-dlp attempt.",
    )
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=DEFAULT_RETRY_DELAY_SECONDS,
        help="Seconds to wait between retry attempts.",
    )

    parser.add_argument(
        "--write-description",
        dest="write_description",
        action="store_true",
        help="Write video descriptions.",
    )
    parser.add_argument(
        "--no-write-description",
        dest="write_description",
        action="store_false",
        help="Do not write video descriptions.",
    )
    parser.set_defaults(write_description=DEFAULT_WRITE_DESCRIPTION)

    parser.add_argument(
        "--write-subs",
        dest="write_subs",
        action="store_true",
        help="Write manually uploaded subtitles.",
    )
    parser.add_argument(
        "--no-write-subs",
        dest="write_subs",
        action="store_false",
        help="Do not write manually uploaded subtitles.",
    )
    parser.set_defaults(write_subs=DEFAULT_WRITE_SUBS)

    parser.add_argument(
        "--write-auto-subs",
        dest="write_auto_subs",
        action="store_true",
        help="Write automatic captions.",
    )
    parser.add_argument(
        "--no-write-auto-subs",
        dest="write_auto_subs",
        action="store_false",
        help="Do not write automatic captions.",
    )
    parser.set_defaults(write_auto_subs=DEFAULT_WRITE_AUTO_SUBS)

    parser.add_argument(
        "--write-comments",
        action="store_true",
        default=DEFAULT_WRITE_COMMENTS,
        help="Write YouTube comments. Disabled by default.",
    )
    parser.add_argument(
        "--sub-langs",
        default=DEFAULT_SUB_LANGS,
        help="Subtitle language selector passed to yt-dlp.",
    )

    return parser.parse_args()


def setup_logging(log_file: Path) -> logging.Logger:
    """
    Configure append-only UTF-8 logging.

    Parameters:
        log_file: Path to the log file.

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


def ensure_output_dirs(output_dir: Path) -> dict[str, Path]:
    """
    Create output directory structure.

    Parameters:
        output_dir: Base output directory.

    Returns:
        Mapping of logical directory names to Paths.

    Performs I/O:
        Creates directories if needed.

    Error behaviour:
        Lets OSError propagate if directories cannot be created.
    """
    dirs = {
        "output": output_dir,
        "videos": output_dir / DEFAULT_VIDEOS_DIR_NAME,
        "metadata_raw": output_dir / DEFAULT_RAW_METADATA_DIR_NAME,
        "descriptions": output_dir / DEFAULT_DESCRIPTIONS_DIR_NAME,
        "subtitles": output_dir / DEFAULT_SUBTITLES_DIR_NAME,
        "comments": output_dir / DEFAULT_COMMENTS_DIR_NAME,
    }
    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
    return dirs


def validate_args(args: argparse.Namespace) -> None:
    """
    Validate command-line arguments and paths.

    Parameters:
        args: Parsed command-line arguments.

    Returns:
        None.

    Performs I/O:
        Checks file and directory path existence.

    Error behaviour:
        Raises ConfigurationError for invalid configuration.
    """
    if not args.metadata.exists():
        raise ConfigurationError(f"Metadata file does not exist: {args.metadata}")
    if not args.metadata.is_file():
        raise ConfigurationError(f"Metadata path is not a file: {args.metadata}")

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
    if args.cookies is not None:
        if not args.cookies.exists():
            raise ConfigurationError(f"Cookies file does not exist: {args.cookies}")
        if not args.cookies.is_file():
            raise ConfigurationError(f"Cookies path is not a file: {args.cookies}")
    if args.start_corpus_id is not None and not args.start_corpus_id.strip():
        raise ConfigurationError("--start-corpus-id cannot be empty")
    if args.metadata_only and args.skip_metadata:
        raise ConfigurationError("--metadata-only and --skip-metadata cannot be combined")


def check_yt_dlp() -> dict[str, Any]:
    """
    Check whether yt-dlp is available and return version metadata.

    Returns:
        Dictionary with availability and version information.

    Performs I/O:
        Executes "yt-dlp --version".

    Error behaviour:
        Raises ConfigurationError if yt-dlp is unavailable or fails.
    """
    executable = shutil.which("yt-dlp")
    if executable is None:
        raise ConfigurationError("yt-dlp is not available on the system PATH")

    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ConfigurationError(f"Failed to run yt-dlp --version: {exc}") from exc

    if result.returncode != 0:
        raise ConfigurationError(
            f"yt-dlp --version failed: {short_error(result.stderr, result.stdout)}"
        )

    return {
        "available": True,
        "version": result.stdout.strip() or "unknown",
        "executable": executable,
    }


def load_samples(metadata_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int]:
    """
    Load, validate, and deduplicate debate sample records from NDJSON.

    Parameters:
        metadata_path: Path to the NDJSON sample file.

    Returns:
        A tuple:
            unique valid records,
            invalid record descriptors,
            duplicate record descriptors,
            total input line count.

    Performs I/O:
        Reads the metadata file.

    Error behaviour:
        Raises ConfigurationError for invalid JSON lines.
        Invalid rows with missing required fields are returned as invalid records.
    """
    records: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    seen_corpus_ids: set[str] = set()
    total_records = 0

    with metadata_path.open("r", encoding="utf-8") as handle:
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

            missing = [
                field for field in REQUIRED_FIELDS
                if not str(record.get(field, "")).strip()
            ]
            if missing:
                invalid_records.append(
                    {
                        "line_number": line_number,
                        "status": "failed_metadata",
                        "error": f"Missing required fields: {', '.join(missing)}",
                        "record": record,
                    }
                )
                continue

            corpus_id = str(record["corpus_id"])
            if corpus_id in seen_corpus_ids:
                duplicates.append(
                    {
                        "line_number": line_number,
                        "corpus_id": corpus_id,
                        "reason": "duplicate_corpus_id",
                        "record": record,
                    }
                )
                continue

            seen_corpus_ids.add(corpus_id)
            record["_line_number"] = line_number
            records.append(record)

    return records, invalid_records, duplicates, total_records


def output_paths_for_record(record: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    """
    Compute expected output paths for one record.

    Parameters:
        record: Valid input metadata record.
        output_dir: Base output directory.

    Returns:
        Dictionary of local output paths.

    Performs I/O:
        No.

    Error behaviour:
        None.
    """
    corpus_id = str(record["corpus_id"])
    return {
        "video_file": output_dir / DEFAULT_VIDEOS_DIR_NAME / f"{corpus_id}.mp4",
        "raw_metadata_file": (
                output_dir / DEFAULT_RAW_METADATA_DIR_NAME / f"{corpus_id}.info.json"
        ),
        "description_file": (
                output_dir / DEFAULT_DESCRIPTIONS_DIR_NAME / f"{corpus_id}.description"
        ),
        "subtitles_dir": output_dir / DEFAULT_SUBTITLES_DIR_NAME,
        "comments_file": output_dir / DEFAULT_COMMENTS_DIR_NAME / f"{corpus_id}.comments.json",
    }


def item_outputs_satisfied(
        paths: dict[str, Path],
        args: argparse.Namespace,
) -> tuple[bool, str]:
    """
    Determine whether requested outputs already exist.

    Parameters:
        paths: Output paths for a planned item.
        args: Parsed command-line arguments.

    Returns:
        Tuple of:
            all requested outputs exist,
            explanatory reason.

    Performs I/O:
        Checks path existence.

    Error behaviour:
        None.
    """
    metadata_exists = paths["raw_metadata_file"].exists()
    video_exists = paths["video_file"].exists()

    if args.metadata_only:
        return metadata_exists, "metadata exists" if metadata_exists else "metadata missing"

    if args.skip_metadata:
        return video_exists, "video exists" if video_exists else "video missing"

    satisfied = video_exists and metadata_exists
    if satisfied:
        return True, "video and metadata exist"

    missing = []
    if not video_exists:
        missing.append("video")
    if not metadata_exists:
        missing.append("metadata")
    return False, f"missing {', '.join(missing)}"


def plan_items(
        records: list[dict[str, Any]],
        output_dir: Path,
        args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Create planned and skipped processing items.

    Parameters:
        records: Unique valid input records.
        output_dir: Base output directory.
        args: Parsed command-line arguments.

    Returns:
        Tuple of:
            planned items,
            skipped items.

    Performs I/O:
        Checks whether expected output files exist.

    Error behaviour:
        Raises ConfigurationError if --start-corpus-id is provided but not found.
    """
    selected_records = records

    if args.start_corpus_id:
        start_index = None
        for index, record in enumerate(records):
            if record["corpus_id"] == args.start_corpus_id:
                start_index = index
                break

        if start_index is None:
            raise ConfigurationError(
                f"--start-corpus-id not found in metadata: {args.start_corpus_id}"
            )

        selected_records = records[start_index:]

    planned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for record in selected_records:
        paths = output_paths_for_record(record, output_dir)
        item = {
            "record": record,
            "paths": paths,
            "corpus_id": record["corpus_id"],
            "youtube_id": record["youtube_id"],
            "youtube_url": record["youtube_url"],
            "title_selected": record["title"],
            "debate_format": record["debate_format"],
        }

        satisfied, reason = item_outputs_satisfied(paths, args)

        if satisfied and not args.reprocess:
            skipped.append(
                {
                    **item,
                    "status": "skipped_existing",
                    "video_status": (
                        "not_requested" if args.metadata_only else "skipped_existing"
                    ),
                    "metadata_status": (
                        "not_requested" if args.skip_metadata else "skipped_existing"
                    ),
                    "skip_reason": reason,
                }
            )
            continue

        planned.append(item)

    if args.test_mode:
        planned = planned[: args.test_limit]

    return planned, skipped


def build_yt_dlp_command(
        item: dict[str, Any],
        args: argparse.Namespace,
        output_paths: dict[str, Path],
) -> list[str]:
    """
    Build the yt-dlp command for one corpus item.

    Parameters:
        item: Planned item.
        args: Parsed command-line arguments.
        output_paths: Computed local output paths.

    Returns:
        Command list suitable for subprocess.run.

    Performs I/O:
        No.

    Error behaviour:
        None.
    """
    corpus_id = str(item["corpus_id"])
    url = str(item["youtube_url"])

    if args.metadata_only:
        output_template = (
                output_paths["raw_metadata_file"].parent / f"{corpus_id}.%(ext)s"
        )
    else:
        output_template = (
                output_paths["video_file"].parent / f"{corpus_id}.%(ext)s"
        )

    command = ["yt-dlp"]

    if args.cookies is not None:
        command.extend(["--cookies", str(args.cookies)])

    if args.reprocess:
        command.append("--force-overwrites")
    else:
        command.append("--no-overwrites")

    if not args.skip_metadata:
        command.append("--write-info-json")

    if args.metadata_only:
        command.append("--skip-download")
    else:
        command.extend(["-f", YT_DLP_FORMAT])

    if args.write_description and not args.skip_metadata:
        command.append("--write-description")

    if args.write_subs and not args.skip_metadata:
        command.append("--write-subs")

    if args.write_auto_subs and not args.skip_metadata:
        command.append("--write-auto-subs")

    if (args.write_subs or args.write_auto_subs) and not args.skip_metadata:
        command.extend(["--sub-langs", args.sub_langs])

    if args.write_comments and not args.skip_metadata:
        command.append("--write-comments")

    command.extend([url, "-o", str(output_template)])
    return command


def run_yt_dlp_command(
        command: list[str],
        timeout: int,
        max_retries: int,
        retry_delay: int,
        logger: logging.Logger,
        corpus_id: str,
) -> dict[str, Any]:
    """
    Run yt-dlp with retries and return structured execution metadata.

    Parameters:
        command: yt-dlp command list.
        timeout: Per-attempt timeout in seconds.
        max_retries: Number of retries after an initial failure.
        retry_delay: Delay between failed attempts.
        logger: Configured logger.
        corpus_id: Corpus item identifier for logging.

    Returns:
        Structured result dictionary.

    Performs I/O:
        Executes external yt-dlp subprocesses and sleeps between retries.

    Error behaviour:
        Captures subprocess failures, timeouts, and OS errors in the result.
    """
    attempts: list[dict[str, Any]] = []
    overall_start = utc_now()
    start_time = utc_timestamp()
    final_return_code: int | None = None
    final_error: str | None = None

    total_attempts = max_retries + 1

    for attempt_number in range(1, total_attempts + 1):
        attempt_start = utc_now()
        logger.info(
            "Attempt %s/%s for %s",
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
            attempt_duration = (attempt_end - attempt_start).total_seconds()
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
                    "duration_seconds": attempt_duration,
                }
            )

            if result.returncode == 0:
                overall_end = utc_now()
                return {
                    "status": "success",
                    "error": None,
                    "return_code": result.returncode,
                    "retries": attempt_number - 1,
                    "attempts": attempts,
                    "start_time": start_time,
                    "end_time": overall_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "duration_seconds": (
                            overall_end - overall_start
                    ).total_seconds(),
                }

        except subprocess.TimeoutExpired as exc:
            attempt_end = utc_now()
            final_return_code = None
            final_error = f"yt-dlp timed out after {timeout} seconds"
            attempts.append(
                {
                    "attempt": attempt_number,
                    "return_code": None,
                    "stdout_tail": (exc.stdout or "")[-4000:]
                    if isinstance(exc.stdout, str) else "",
                    "stderr_tail": (exc.stderr or "")[-4000:]
                    if isinstance(exc.stderr, str) else "",
                    "error": final_error,
                    "duration_seconds": (
                            attempt_end - attempt_start
                    ).total_seconds(),
                }
            )

        except OSError as exc:
            attempt_end = utc_now()
            final_return_code = None
            final_error = f"Failed to execute yt-dlp: {exc}"
            attempts.append(
                {
                    "attempt": attempt_number,
                    "return_code": None,
                    "stdout_tail": "",
                    "stderr_tail": "",
                    "error": final_error,
                    "duration_seconds": (
                            attempt_end - attempt_start
                    ).total_seconds(),
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
        "attempts": attempts,
        "start_time": start_time,
        "end_time": overall_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": (overall_end - overall_start).total_seconds(),
    }


def move_if_exists(source: Path, destination: Path) -> bool:
    """
    Move a file if it exists.

    Parameters:
        source: Candidate source file.
        destination: Destination file.

    Returns:
        True if the file was moved or destination already exists, else False.

    Performs I/O:
        May move a file and create destination parent directory.

    Error behaviour:
        Lets OSError propagate.
    """
    if destination.exists():
        return True
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return True
    return False


def normalise_sidecar_files(
        item: dict[str, Any],
        output_paths: dict[str, Path],
        args: argparse.Namespace,
) -> dict[str, Any]:
    """
    Move or identify yt-dlp sidecar files in the expected project layout.

    Parameters:
        item: Processed item.
        output_paths: Expected local paths.
        args: Parsed command-line arguments.

    Returns:
        Dictionary with discovered local sidecar paths.

    Performs I/O:
        Moves metadata, description, comments, and subtitle files where possible.

    Error behaviour:
        Lets OSError propagate if moving files fails.
    """
    corpus_id = str(item["corpus_id"])
    video_dir = output_paths["video_file"].parent
    metadata_dir = output_paths["raw_metadata_file"].parent
    descriptions_dir = output_paths["description_file"].parent
    subtitles_dir = output_paths["subtitles_dir"]
    comments_dir = output_paths["comments_file"].parent

    # yt-dlp writes sidecars next to the output template base. In normal mode,
    # that is videos/. In metadata-only mode, that is metadata_raw/.
    candidate_dirs = [video_dir, metadata_dir]

    for directory in candidate_dirs:
        move_if_exists(
            directory / f"{corpus_id}.info.json",
            output_paths["raw_metadata_file"],
            )
        move_if_exists(
            directory / f"{corpus_id}.description",
            output_paths["description_file"],
            )

        for comments_candidate in directory.glob(f"{corpus_id}.comments.*"):
            if not output_paths["comments_file"].exists():
                output_paths["comments_file"].parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(comments_candidate), str(output_paths["comments_file"]))

    subtitle_files: list[Path] = []
    for directory in candidate_dirs:
        for subtitle_candidate in directory.glob(f"{corpus_id}.*"):
            if subtitle_candidate.suffix.lower() not in {".vtt", ".srt", ".ass", ".json3"}:
                continue
            destination = subtitles_dir / subtitle_candidate.name
            if subtitle_candidate.resolve() != destination.resolve():
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    shutil.move(str(subtitle_candidate), str(destination))
            subtitle_files.append(destination)

    subtitle_files.extend(
        path for path in subtitles_dir.glob(f"{corpus_id}.*")
        if path.suffix.lower() in {".vtt", ".srt", ".ass", ".json3"}
    )

    unique_subtitle_files = sorted({path.resolve(): path for path in subtitle_files}.values())

    return {
        "raw_metadata_file": (
            output_paths["raw_metadata_file"]
            if output_paths["raw_metadata_file"].exists()
            else None
        ),
        "description_file": (
            output_paths["description_file"]
            if output_paths["description_file"].exists()
            else None
        ),
        "comments_file": (
            output_paths["comments_file"]
            if output_paths["comments_file"].exists()
            else None
        ),
        "subtitles_files": unique_subtitle_files,
        "video_file": (
            output_paths["video_file"]
            if output_paths["video_file"].exists()
            else None
        ),
        "video_requested": not args.metadata_only,
        "metadata_requested": not args.skip_metadata,
    }


def load_raw_metadata(raw_metadata_path: Path | None) -> dict[str, Any]:
    """
    Load a raw yt-dlp info JSON file if available.

    Parameters:
        raw_metadata_path: Path to the raw metadata file, or None.

    Returns:
        Parsed metadata dictionary, or empty dict if unavailable/unreadable.

    Performs I/O:
        Reads the metadata file if it exists.

    Error behaviour:
        Returns an empty dictionary on read or JSON parsing failure.
    """
    if raw_metadata_path is None or not raw_metadata_path.exists():
        return {}

    try:
        with raw_metadata_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def extract_curated_metadata(
        input_record: dict[str, Any],
        raw_metadata_path: Path | None,
        local_paths: dict[str, Any],
        run_metadata: dict[str, Any],
        item_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Create one curated corpus index record.

    Parameters:
        input_record: Original input record.
        raw_metadata_path: Path to raw yt-dlp info JSON, if available.
        local_paths: Dictionary of discovered local files.
        run_metadata: Run-level metadata.
        item_result: Per-item processing result.

    Returns:
        Curated metadata dictionary suitable for NDJSON output.

    Performs I/O:
        Reads raw metadata JSON if available.

    Error behaviour:
        Missing raw metadata fields are represented with null, empty lists, or false.
    """
    raw = load_raw_metadata(raw_metadata_path)

    subtitles = raw.get("subtitles")
    automatic_captions = raw.get("automatic_captions")

    subtitles_available = isinstance(subtitles, dict) and bool(subtitles)
    automatic_captions_available = (
            isinstance(automatic_captions, dict) and bool(automatic_captions)
    )

    description_file = local_paths.get("description_file")
    comments_file = local_paths.get("comments_file")
    video_file = local_paths.get("video_file")
    subtitles_files = local_paths.get("subtitles_files", [])

    return {
        "corpus_id": input_record.get("corpus_id"),
        "debate_format": input_record.get("debate_format"),
        "sample_group": input_record.get("sample_group"),
        "sample_order": input_record.get("sample_order"),
        "title_selected": input_record.get("title"),
        "title_extracted": raw.get("title"),
        "youtube_id": input_record.get("youtube_id") or raw.get("id"),
        "youtube_url": input_record.get("youtube_url"),
        "webpage_url": raw.get("webpage_url"),
        "source_platform": input_record.get("source_platform"),
        "channel_selected": input_record.get("channel"),
        "channel_extracted": raw.get("channel"),
        "channel_id": raw.get("channel_id"),
        "channel_url": raw.get("channel_url"),
        "uploader": raw.get("uploader"),
        "uploader_id": raw.get("uploader_id"),
        "upload_date": raw.get("upload_date"),
        "duration_seconds": raw.get("duration"),
        "duration_string": raw.get("duration_string"),
        "view_count_at_selection": input_record.get("views_reported_numeric_approx"),
        "view_count_reported_by_selector": input_record.get(
            "views_reported_by_selector"
        ),
        "view_count_at_download": raw.get("view_count"),
        "like_count_at_download": raw.get("like_count"),
        "comment_count_at_download": raw.get("comment_count"),
        "categories": raw.get("categories") or [],
        "tags": raw.get("tags") or [],
        "description": raw.get("description"),
        "thumbnail_url": raw.get("thumbnail"),
        "chapters": raw.get("chapters") or [],
        "subtitles_available": subtitles_available,
        "automatic_captions_available": automatic_captions_available,
        "availability": raw.get("availability"),
        "age_limit": raw.get("age_limit"),
        "live_status": raw.get("live_status"),
        "video_file": path_to_str(video_file),
        "raw_metadata_file": path_to_str(raw_metadata_path),
        "description_file": path_to_str(description_file),
        "subtitles_files": [path_to_str(path) for path in subtitles_files],
        "comments_file": path_to_str(comments_file),
        "download_status": item_result.get("video_status"),
        "metadata_status": item_result.get("metadata_status"),
        "download_run_id": run_metadata.get("run_id"),
        "downloaded_at_utc": run_metadata.get("end_time") or run_metadata.get("start_time"),
        "yt_dlp_version": run_metadata.get("yt_dlp", {}).get("version", "unknown"),
        "selected_by": input_record.get("selected_by"),
        "selection_source": input_record.get("selection_source"),
        "notes": input_record.get("notes"),
    }


def write_index(index_records: list[dict[str, Any]], index_file: Path) -> None:
    """
    Write the curated NDJSON corpus index.

    Parameters:
        index_records: Curated metadata records.
        index_file: Destination NDJSON file.

    Returns:
        None.

    Performs I/O:
        Creates parent directory and writes the index file.

    Error behaviour:
        Lets OSError propagate if writing fails.
    """
    index_file.parent.mkdir(parents=True, exist_ok=True)
    with index_file.open("w", encoding="utf-8") as handle:
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
        Tuple of:
            latest manifest path,
            timestamped manifest path.

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
        yt_dlp_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Construct the initial run metadata dictionary.

    Parameters:
        args: Parsed command-line arguments.
        run_id: Run identifier.
        start_time: ISO-8601 UTC start time.
        yt_dlp_info: yt-dlp availability/version metadata, if available.

    Returns:
        Run metadata dictionary.

    Performs I/O:
        No.

    Error behaviour:
        None.
    """
    return {
        "run_id": run_id,
        "tool_name": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "start_time": start_time,
        "end_time": None,
        "test_mode": args.test_mode,
        "test_limit": args.test_limit,
        "metadata_only": args.metadata_only,
        "reprocess": args.reprocess,
        "workers": args.workers,
        "metadata_path": path_to_str(args.metadata),
        "output_dir": path_to_str(args.output_dir),
        "index_file": path_to_str(args.index_file),
        "log_file": path_to_str(args.log_file),
        "manifest_file": path_to_str(args.manifest_file),
        "config": {
            "yt_dlp_format": YT_DLP_FORMAT,
            "timeout_seconds": args.timeout,
            "max_retries": args.max_retries,
            "retry_delay_seconds": args.retry_delay,
            "cookies_provided": args.cookies is not None,
            "start_corpus_id": args.start_corpus_id,
            "write_description": args.write_description,
            "write_subs": args.write_subs,
            "write_auto_subs": args.write_auto_subs,
            "write_comments": args.write_comments,
            "sub_langs": args.sub_langs,
            "skip_metadata": args.skip_metadata,
        },
        "yt_dlp": yt_dlp_info or {"available": False, "version": None},
        "summary": {
            "input_records": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "unique_corpus_items": 0,
            "planned_items": 0,
            "attempted_items": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped_existing": 0,
        },
        "interrupted": False,
    }


def item_result_from_skipped(
        item: dict[str, Any],
        run_metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Create a manifest item result for an existing skipped item.

    Parameters:
        item: Skipped item from planning.
        run_metadata: Run metadata.

    Returns:
        Per-item manifest result.

    Performs I/O:
        No.

    Error behaviour:
        None.
    """
    paths = item["paths"]
    return {
        "corpus_id": item["corpus_id"],
        "youtube_id": item["youtube_id"],
        "youtube_url": item["youtube_url"],
        "title_selected": item["title_selected"],
        "debate_format": item["debate_format"],
        "video_file": path_to_str(paths["video_file"]),
        "raw_metadata_file": path_to_str(paths["raw_metadata_file"]),
        "description_file": path_to_str(paths["description_file"]),
        "status": "skipped_existing",
        "video_status": item.get("video_status", "skipped_existing"),
        "metadata_status": item.get("metadata_status", "skipped_existing"),
        "error": None,
        "return_code": None,
        "retries": 0,
        "duration_seconds": 0.0,
        "start_time": run_metadata["start_time"],
        "end_time": run_metadata["start_time"],
        "skip_reason": item.get("skip_reason"),
    }


def process_item(
        item: dict[str, Any],
        args: argparse.Namespace,
        logger: logging.Logger,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Process one planned item with yt-dlp.

    Parameters:
        item: Planned item.
        args: Parsed command-line arguments.
        logger: Configured logger.

    Returns:
        Tuple of:
            per-item manifest result,
            local sidecar path metadata.

    Performs I/O:
        Runs yt-dlp and normalises sidecar files.

    Error behaviour:
        Converts processing errors into failed item results where possible.
    """
    paths = item["paths"]
    command = build_yt_dlp_command(item, args, paths)

    logger.info("Processing %s %s", item["corpus_id"], item["youtube_url"])

    execution = run_yt_dlp_command(
        command=command,
        timeout=args.timeout,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        logger=logger,
        corpus_id=str(item["corpus_id"]),
    )

    local_paths: dict[str, Any] = {}
    normalise_error = None

    try:
        local_paths = normalise_sidecar_files(item, paths, args)
    except OSError as exc:
        normalise_error = f"Failed to normalise sidecar files: {exc}"

    status = execution["status"]
    if normalise_error is not None:
        status = "failed"

    metadata_file_exists = paths["raw_metadata_file"].exists()
    video_file_exists = paths["video_file"].exists()

    if args.metadata_only:
        video_status = "not_requested"
    else:
        video_status = "success" if video_file_exists and status == "success" else status

    if args.skip_metadata:
        metadata_status = "not_requested"
    else:
        metadata_status = "success" if metadata_file_exists and status == "success" else status

    error = normalise_error or execution.get("error")

    item_result = {
        "corpus_id": item["corpus_id"],
        "youtube_id": item["youtube_id"],
        "youtube_url": item["youtube_url"],
        "title_selected": item["title_selected"],
        "debate_format": item["debate_format"],
        "video_file": path_to_str(paths["video_file"]),
        "raw_metadata_file": path_to_str(paths["raw_metadata_file"]),
        "description_file": path_to_str(paths["description_file"]),
        "status": status,
        "video_status": video_status,
        "metadata_status": metadata_status,
        "error": error,
        "return_code": execution.get("return_code"),
        "retries": execution.get("retries", 0),
        "duration_seconds": execution.get("duration_seconds"),
        "start_time": execution.get("start_time"),
        "end_time": execution.get("end_time"),
        "metadata": {
            "command": command,
            "attempts": execution.get("attempts", []),
        },
    }

    if status == "success":
        logger.info("SUCCESS %s", item["corpus_id"])
    else:
        logger.error("FAILED %s: %s", item["corpus_id"], error)

    if not local_paths:
        local_paths = {
            "raw_metadata_file": paths["raw_metadata_file"]
            if paths["raw_metadata_file"].exists()
            else None,
            "description_file": paths["description_file"]
            if paths["description_file"].exists()
            else None,
            "comments_file": paths["comments_file"]
            if paths["comments_file"].exists()
            else None,
            "subtitles_files": sorted(
                path for path in paths["subtitles_dir"].glob(f"{item['corpus_id']}.*")
                if path.suffix.lower() in {".vtt", ".srt", ".ass", ".json3"}
            ),
            "video_file": paths["video_file"] if paths["video_file"].exists() else None,
        }

    return item_result, local_paths


def main() -> int:
    """
    Run the complete Jubilee debate download workflow.

    Returns:
        Process exit code.

    Performs I/O:
        Reads NDJSON metadata, creates directories, runs yt-dlp, writes logs,
        writes manifests, and writes the curated index.

    Error behaviour:
        Returns:
            0 for success,
            1 for completed runs with item/metadata failures,
            2 for configuration errors,
            130 for keyboard interruption.
    """
    args = parse_args()
    run_id = make_run_id()
    start_time = utc_timestamp()
    logger: logging.Logger | None = None

    run_metadata = make_initial_run_metadata(args, run_id, start_time)
    manifest: dict[str, Any] = {
        "run_metadata": run_metadata,
        "items": [],
        "invalid_records": [],
        "duplicates": [],
    }

    try:
        ensure_output_dirs(args.output_dir)
        logger = setup_logging(args.log_file)

        logger.info("Starting %s run_id=%s", TOOL_NAME, run_id)
        logger.info("Metadata path: %s", args.metadata)
        logger.info("Output directory: %s", args.output_dir)
        logger.info("Index file: %s", args.index_file)
        logger.info("Test mode: %s; test_limit=%s", args.test_mode, args.test_limit)
        logger.info("Metadata-only: %s", args.metadata_only)
        logger.info("Skip metadata: %s", args.skip_metadata)
        logger.info("Reprocess: %s", args.reprocess)
        logger.info("Cookies file provided: %s", args.cookies is not None)
        logger.info("Start corpus ID: %s", args.start_corpus_id)

        validate_args(args)
        yt_dlp_info = check_yt_dlp()
        run_metadata["yt_dlp"] = yt_dlp_info
        logger.info("yt-dlp version: %s", yt_dlp_info["version"])

        records, invalid_records, duplicates, total_records = load_samples(args.metadata)

        if not records:
            raise ConfigurationError("No valid records found in metadata file")

        # Validate --start-corpus-id after loading, so the error is precise.
        if args.start_corpus_id and not any(
                record["corpus_id"] == args.start_corpus_id for record in records
        ):
            raise ConfigurationError(
                f"--start-corpus-id not found in metadata: {args.start_corpus_id}"
            )

        planned, skipped = plan_items(records, args.output_dir, args)

        run_metadata["summary"].update(
            {
                "input_records": total_records,
                "valid_records": len(records),
                "invalid_records": len(invalid_records),
                "unique_corpus_items": len(records),
                "planned_items": len(planned),
                "skipped_existing": len(skipped),
            }
        )
        manifest["invalid_records"] = invalid_records
        manifest["duplicates"] = duplicates

        logger.info(
            "Loaded records: input=%s valid=%s invalid=%s duplicates=%s",
            total_records,
            len(records),
            len(invalid_records),
            len(duplicates),
        )
        logger.info("Planned items: %s", len(planned))
        logger.info("Skipped existing items: %s", len(skipped))

        item_results: list[dict[str, Any]] = []
        index_records: list[dict[str, Any]] = []

        for skipped_item in skipped:
            logger.info(
                "SKIPPED existing %s: %s",
                skipped_item["corpus_id"],
                skipped_item.get("skip_reason"),
            )
            result = item_result_from_skipped(skipped_item, run_metadata)
            item_results.append(result)

            paths = skipped_item["paths"]
            local_paths = {
                "raw_metadata_file": paths["raw_metadata_file"]
                if paths["raw_metadata_file"].exists()
                else None,
                "description_file": paths["description_file"]
                if paths["description_file"].exists()
                else None,
                "comments_file": paths["comments_file"]
                if paths["comments_file"].exists()
                else None,
                "subtitles_files": sorted(
                    path for path in paths["subtitles_dir"].glob(
                        f"{skipped_item['corpus_id']}.*"
                    )
                    if path.suffix.lower() in {".vtt", ".srt", ".ass", ".json3"}
                ),
                "video_file": paths["video_file"] if paths["video_file"].exists() else None,
            }

            index_records.append(
                extract_curated_metadata(
                    input_record=skipped_item["record"],
                    raw_metadata_path=local_paths["raw_metadata_file"],
                    local_paths=local_paths,
                    run_metadata=run_metadata,
                    item_result=result,
                )
            )

        for item in planned:
            result, local_paths = process_item(item, args, logger)
            item_results.append(result)
            run_metadata["summary"]["attempted_items"] += 1

            index_records.append(
                extract_curated_metadata(
                    input_record=item["record"],
                    raw_metadata_path=local_paths.get("raw_metadata_file"),
                    local_paths=local_paths,
                    run_metadata=run_metadata,
                    item_result=result,
                )
            )

        succeeded = sum(
            1 for item in item_results
            if item["status"] in {"success", "skipped_existing"}
        )
        failed = sum(1 for item in item_results if item["status"] == "failed")

        run_metadata["summary"]["succeeded"] = succeeded
        run_metadata["summary"]["failed"] = failed
        run_metadata["end_time"] = utc_timestamp()

        # Refresh downloaded_at_utc after end_time is known.
        for record in index_records:
            record["downloaded_at_utc"] = run_metadata["end_time"]

        manifest["items"] = item_results

        write_index(index_records, args.index_file)
        logger.info("Wrote curated index: %s", args.index_file)

        latest_manifest, run_manifest = write_manifests(
            manifest,
            args.manifest_file,
            run_id,
        )
        logger.info("Wrote latest manifest: %s", latest_manifest)
        logger.info("Wrote run manifest: %s", run_manifest)

        logger.info(
            "Finished run: succeeded=%s failed=%s skipped_existing=%s "
            "invalid_records=%s",
            succeeded,
            failed,
            len(skipped),
            len(invalid_records),
        )

        if failed > 0 or invalid_records:
            return 1
        return 0

    except KeyboardInterrupt:
        run_metadata["interrupted"] = True
        run_metadata["end_time"] = utc_timestamp()
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