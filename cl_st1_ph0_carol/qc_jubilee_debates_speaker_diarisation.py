#!/usr/bin/env python3
"""
Produce QC reports for Jubilee debate speaker diarisation outputs.

This script reads the curated Jubilee debate speaker-assignment index, selects
records whose speaker-attributed transcript outputs are available, and computes
quality-control metrics for alignment, diarisation, and speaker assignment.

The primary inputs are speaker word and speaker segment outputs from
assign_speakers_jubilee_debates.py. Alignment and diarisation files are also
inspected when available to compute additional coverage and timing diagnostics.

Outputs are written to the QC output directory as per-debate JSON and Markdown
reports, plus corpus-level JSON and Markdown summaries. The reports include
metrics such as word assignment coverage, unknown-speaker ratio, detected speaker
count, diarisation coverage, short-turn ratio, speaker distribution, timing
anomalies, and review warnings.

By default, the script runs in test mode and attempts only the first planned
debate. Existing complete QC outputs are skipped unless --reprocess is provided,
making the script safe to re-run.

Use --start-corpus-id to resume planning from a specific debate onward.

This programme performs QC reporting only. It does not transcribe, align,
diarise, assign speakers, identify real speakers, or modify upstream outputs.

Example:
    python qc_jubilee_debates_speaker_diarisation.py

Full run:
    python qc_jubilee_debates_speaker_diarisation.py --no-test-mode

Full run from a specific debate:
    python qc_jubilee_debates_speaker_diarisation.py --no-test-mode --start-corpus-id jubilee_surrounded_003
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOOL_NAME = "qc_jubilee_debates_speaker_diarisation.py"
TOOL_VERSION = "v1"

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_SPEAKER_INDEX_PATH = (
    "corpus/06_jubilee_debates_speaker_transcripts/"
    "jubilee_debates_speaker_assignment_index.ndjson"
)
DEFAULT_ALIGNMENT_DIR = "corpus/04_jubilee_debates_alignment"
DEFAULT_DIARISATION_DIR = "corpus/05_jubilee_debates_diarisation"
DEFAULT_SPEAKER_TRANSCRIPTS_DIR = "corpus/06_jubilee_debates_speaker_transcripts"
DEFAULT_OUTPUT_DIR = "corpus/07_jubilee_debates_qc"

DEFAULT_LOG_FILE = (
    "corpus/07_jubilee_debates_qc/"
    "qc_jubilee_debates_speaker_diarisation.log"
)
DEFAULT_MANIFEST_FILE = (
    "corpus/07_jubilee_debates_qc/"
    "qc_jubilee_debates_speaker_diarisation_manifest.json"
)
DEFAULT_QC_INDEX_FILE = (
    "corpus/07_jubilee_debates_qc/"
    "jubilee_debates_speaker_diarisation_qc_index.ndjson"
)

CORPUS_SUMMARY_JSON_NAME = "jubilee_debates_speaker_diarisation_qc_summary.json"
CORPUS_SUMMARY_MD_NAME = "jubilee_debates_speaker_diarisation_qc_summary.md"

DEFAULT_GAP_WARNING_THRESHOLD_SECONDS = 5.0
DEFAULT_UNKNOWN_SPAN_WARNING_THRESHOLD_SECONDS = 10.0
DEFAULT_UNASSIGNED_WORD_RATIO_WARNING_THRESHOLD = 0.05
DEFAULT_DIARISATION_COVERAGE_WARNING_THRESHOLD = 0.60
DEFAULT_DIARISATION_COVERAGE_HIGH_WARNING_THRESHOLD = 0.98
DEFAULT_MIN_EXPECTED_SPEAKERS = 3
DEFAULT_MAX_EXPECTED_SPEAKERS = 35
DEFAULT_SHORT_TURN_THRESHOLD_SECONDS = 0.5
DEFAULT_SHORT_TURN_RATIO_WARNING_THRESHOLD = 0.25
DEFAULT_LONG_TURN_THRESHOLD_SECONDS = 120.0
DEFAULT_SPEAKER_IMBALANCE_WARNING_THRESHOLD = 0.65

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 1
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

OUTPUT_QC_JSON_EXTENSION = ".qc.json"
OUTPUT_QC_MARKDOWN_EXTENSION = ".qc.md"

ELIGIBLE_SPEAKER_ASSIGNMENT_STATUSES = ("success", "skipped_existing")
UNKNOWN_SPEAKER_LABELS = {"", "unknown", "unknown_speaker", "UNKNOWN", "UNKNOWN_SPEAKER", None}

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
    "duration_seconds",
    "duration_string",
    "chapters",
    "audio_file",
    "aligned_json_file",
    "words_ndjson_file",
    "diarisation_json_file",
    "segments_ndjson_file",
    "speaker_words_json_file",
    "speaker_words_ndjson_file",
    "speaker_segments_json_file",
    "speaker_segments_ndjson_file",
    "speaker_transcript_text_file",
    "alignment_status",
    "diarisation_status",
    "speaker_assignment_status",
    "alignment_run_id",
    "diarisation_run_id",
    "speaker_assignment_run_id",
    "selected_by",
    "selection_source",
    "notes",
)


class ConfigurationError(Exception):
    """Raised when command-line options or runtime configuration are invalid."""


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime without performing I/O."""
    return datetime.now(timezone.utc)


def utc_timestamp() -> str:
    """Return an ISO-like UTC timestamp without microseconds."""
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    """Return a compact UTC run identifier suitable for filenames."""
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the QC programme.

    Returns:
        Parsed argparse namespace with all path arguments resolved relative to
        SCRIPT_DIR unless absolute paths were supplied.

    I/O:
        Reads command-line arguments through argparse.

    Error behaviour:
        argparse exits with code 2 for malformed command-line usage.
    """
    parser = argparse.ArgumentParser(
        description="Produce quality-control reports for Jubilee debate speaker diarisation outputs."
    )

    parser.add_argument("--speaker-index", default=DEFAULT_SPEAKER_INDEX_PATH)
    parser.add_argument("--alignment-dir", default=DEFAULT_ALIGNMENT_DIR)
    parser.add_argument("--diarisation-dir", default=DEFAULT_DIARISATION_DIR)
    parser.add_argument("--speaker-transcripts-dir", default=DEFAULT_SPEAKER_TRANSCRIPTS_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)

    parser.add_argument(
        "--gap-warning-threshold",
        type=float,
        default=DEFAULT_GAP_WARNING_THRESHOLD_SECONDS,
    )
    parser.add_argument(
        "--unknown-span-warning-threshold",
        type=float,
        default=DEFAULT_UNKNOWN_SPAN_WARNING_THRESHOLD_SECONDS,
    )
    parser.add_argument(
        "--unassigned-word-ratio-warning-threshold",
        type=float,
        default=DEFAULT_UNASSIGNED_WORD_RATIO_WARNING_THRESHOLD,
    )
    parser.add_argument(
        "--diarisation-coverage-warning-threshold",
        type=float,
        default=DEFAULT_DIARISATION_COVERAGE_WARNING_THRESHOLD,
    )
    parser.add_argument(
        "--diarisation-coverage-high-warning-threshold",
        type=float,
        default=DEFAULT_DIARISATION_COVERAGE_HIGH_WARNING_THRESHOLD,
    )
    parser.add_argument(
        "--min-expected-speakers",
        type=int,
        default=DEFAULT_MIN_EXPECTED_SPEAKERS,
    )
    parser.add_argument(
        "--max-expected-speakers",
        type=int,
        default=DEFAULT_MAX_EXPECTED_SPEAKERS,
    )
    parser.add_argument(
        "--short-turn-threshold",
        type=float,
        default=DEFAULT_SHORT_TURN_THRESHOLD_SECONDS,
    )
    parser.add_argument(
        "--short-turn-ratio-warning-threshold",
        type=float,
        default=DEFAULT_SHORT_TURN_RATIO_WARNING_THRESHOLD,
    )
    parser.add_argument(
        "--long-turn-threshold",
        type=float,
        default=DEFAULT_LONG_TURN_THRESHOLD_SECONDS,
    )
    parser.add_argument(
        "--speaker-imbalance-warning-threshold",
        type=float,
        default=DEFAULT_SPEAKER_IMBALANCE_WARNING_THRESHOLD,
    )

    test_mode_group = parser.add_mutually_exclusive_group()
    test_mode_group.add_argument("--test-mode", dest="test_mode", action="store_true")
    test_mode_group.add_argument("--no-test-mode", dest="test_mode", action="store_false")
    parser.set_defaults(test_mode=DEFAULT_TEST_MODE)

    parser.add_argument("--test-limit", type=int, default=DEFAULT_TEST_LIMIT)
    parser.add_argument("--reprocess", action="store_true")
    parser.add_argument("--start-corpus-id", default=None)

    parser.add_argument("--log-file", default=DEFAULT_LOG_FILE)
    parser.add_argument("--manifest-file", default=DEFAULT_MANIFEST_FILE)
    parser.add_argument("--qc-index-file", default=DEFAULT_QC_INDEX_FILE)

    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--retry-delay", type=int, default=DEFAULT_RETRY_DELAY_SECONDS)

    args = parser.parse_args()

    for field in (
        "speaker_index",
        "alignment_dir",
        "diarisation_dir",
        "speaker_transcripts_dir",
        "output_dir",
        "log_file",
        "manifest_file",
        "qc_index_file",
    ):
        setattr(args, field, resolve_script_relative_path(Path(getattr(args, field))))

    return args


def resolve_script_relative_path(path: Path) -> Path:
    """
    Resolve relative paths against the programme directory.

    Args:
        path: Relative or absolute path.

    Returns:
        Absolute paths unchanged; relative paths resolved against SCRIPT_DIR.

    I/O:
        Does not touch the filesystem.

    Error behaviour:
        Does not raise for missing paths.
    """
    if path.is_absolute():
        return path
    return SCRIPT_DIR / path


def setup_logging(log_file: Path) -> logging.Logger:
    """
    Configure append-only UTF-8 logging.

    Args:
        log_file: Destination log file.

    Returns:
        Configured logger.

    I/O:
        Creates parent directories and opens the log file in append mode.

    Error behaviour:
        Propagates OSError if the log cannot be created.
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


def validate_args(args: argparse.Namespace) -> None:
    """
    Validate command-line arguments and filesystem paths.

    Args:
        args: Parsed, path-resolved command-line arguments.

    Returns:
        None.

    I/O:
        Checks input paths and creates output/log/manifest parent directories.

    Error behaviour:
        Raises ConfigurationError for validation failures.
    """
    if args.gap_warning_threshold < 0:
        raise ConfigurationError("--gap-warning-threshold must be >= 0.")
    if args.unknown_span_warning_threshold < 0:
        raise ConfigurationError("--unknown-span-warning-threshold must be >= 0.")
    validate_ratio(args.unassigned_word_ratio_warning_threshold, "--unassigned-word-ratio-warning-threshold")
    validate_ratio(args.diarisation_coverage_warning_threshold, "--diarisation-coverage-warning-threshold")
    validate_ratio(
        args.diarisation_coverage_high_warning_threshold,
        "--diarisation-coverage-high-warning-threshold",
    )
    if args.diarisation_coverage_warning_threshold > args.diarisation_coverage_high_warning_threshold:
        raise ConfigurationError("Low diarisation coverage threshold must not exceed high threshold.")
    if args.min_expected_speakers <= 0:
        raise ConfigurationError("--min-expected-speakers must be > 0.")
    if args.max_expected_speakers <= 0:
        raise ConfigurationError("--max-expected-speakers must be > 0.")
    if args.min_expected_speakers > args.max_expected_speakers:
        raise ConfigurationError("--min-expected-speakers must not exceed --max-expected-speakers.")
    if args.short_turn_threshold < 0:
        raise ConfigurationError("--short-turn-threshold must be >= 0.")
    validate_ratio(args.short_turn_ratio_warning_threshold, "--short-turn-ratio-warning-threshold")
    if args.long_turn_threshold <= 0:
        raise ConfigurationError("--long-turn-threshold must be > 0.")
    validate_ratio(args.speaker_imbalance_warning_threshold, "--speaker-imbalance-warning-threshold")
    if args.test_limit <= 0:
        raise ConfigurationError("--test-limit must be a positive integer.")
    if args.workers <= 0:
        raise ConfigurationError("--workers must be a positive integer.")
    if args.workers != 1:
        raise ConfigurationError("Only --workers 1 is supported in this implementation.")
    if args.timeout <= 0:
        raise ConfigurationError("--timeout must be a positive integer.")
    if args.max_retries < 0:
        raise ConfigurationError("--max-retries must be zero or a positive integer.")
    if args.retry_delay < 0:
        raise ConfigurationError("--retry-delay must be zero or a positive integer.")
    if args.start_corpus_id is not None and not args.start_corpus_id.strip():
        raise ConfigurationError("--start-corpus-id must not be empty.")

    if not args.speaker_index.exists():
        raise ConfigurationError(f"Speaker-assignment index does not exist: {args.speaker_index}")
    if not args.speaker_index.is_file():
        raise ConfigurationError(f"Speaker-assignment index path is not a file: {args.speaker_index}")

    try:
        with args.speaker_index.open("r", encoding="utf-8"):
            pass
    except OSError as exc:
        raise ConfigurationError(f"Speaker-assignment index is unreadable: {exc}") from exc

    for directory_field, label in (
        ("alignment_dir", "alignment directory"),
        ("diarisation_dir", "diarisation directory"),
        ("speaker_transcripts_dir", "speaker transcripts directory"),
    ):
        directory = getattr(args, directory_field)
        if not directory.exists():
            raise ConfigurationError(f"{label.capitalize()} does not exist: {directory}")
        if not directory.is_dir():
            raise ConfigurationError(f"{label.capitalize()} path is not a directory: {directory}")

    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        args.qc_index_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create output/log/manifest directories: {exc}") from exc


def validate_ratio(value: float, argument_name: str) -> None:
    """Validate that a floating-point command-line value is between 0.0 and 1.0."""
    if value < 0.0 or value > 1.0:
        raise ConfigurationError(f"{argument_name} must be between 0.0 and 1.0.")


def load_speaker_assignment_index(
    index_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int]:
    """
    Load and filter the speaker-assignment NDJSON index.

    Args:
        index_path: Path to speaker-assignment NDJSON index.

    Returns:
        Tuple containing valid eligible records, invalid eligible records,
        ignored records, and total non-blank records read.

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
                    f"Invalid JSON in speaker-assignment index at line {line_number}: {exc}"
                ) from exc

            if not isinstance(record, dict):
                raise ConfigurationError(
                    f"Invalid NDJSON object at line {line_number}: expected JSON object."
                )

            status = record.get("speaker_assignment_status")
            if status not in ELIGIBLE_SPEAKER_ASSIGNMENT_STATUSES:
                ignored_records.append(
                    make_item_base(record)
                    | {
                        "status": "ignored_speaker_assignment_unavailable",
                        "line_number": line_number,
                        "speaker_assignment_status": status,
                        "error": None,
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
                        "line_number": line_number,
                        "error": "Eligible record is missing non-empty corpus_id.",
                    }
                )
                continue

            eligible_records.append(record)

    if not eligible_records and not invalid_records:
        raise ConfigurationError("No eligible speaker-assignment records found.")

    return eligible_records, invalid_records, ignored_records, total_records


def resolve_qc_input_paths(
    record: dict[str, Any],
    alignment_dir: Path,
    diarisation_dir: Path,
    speaker_transcripts_dir: Path,
) -> dict[str, Path | None]:
    """
    Resolve speaker-assignment and optional upstream input paths.

    Args:
        record: Speaker-assignment index row.
        alignment_dir: Fallback alignment directory.
        diarisation_dir: Fallback diarisation directory.
        speaker_transcripts_dir: Fallback speaker transcript directory.

    Returns:
        Mapping from logical path field names to paths.

    I/O:
        Does not check filesystem existence.

    Error behaviour:
        Raises KeyError if corpus_id is missing after prior validation.
    """
    corpus_id = str(record["corpus_id"])

    return {
        "speaker_words_json_file": path_from_record_or_fallback(
            record,
            "speaker_words_json_file",
            speaker_transcripts_dir / f"{corpus_id}.speaker_words.json",
        ),
        "speaker_words_ndjson_file": path_from_record_or_fallback(
            record,
            "speaker_words_ndjson_file",
            speaker_transcripts_dir / f"{corpus_id}.speaker_words.ndjson",
        ),
        "speaker_segments_json_file": path_from_record_or_fallback(
            record,
            "speaker_segments_json_file",
            speaker_transcripts_dir / f"{corpus_id}.speaker_segments.json",
        ),
        "speaker_segments_ndjson_file": path_from_record_or_fallback(
            record,
            "speaker_segments_ndjson_file",
            speaker_transcripts_dir / f"{corpus_id}.speaker_segments.ndjson",
        ),
        "speaker_transcript_text_file": path_from_record_or_fallback(
            record,
            "speaker_transcript_text_file",
            speaker_transcripts_dir / f"{corpus_id}.speaker_transcript.txt",
        ),
        "aligned_json_file": path_from_record_or_fallback(
            record,
            "aligned_json_file",
            alignment_dir / f"{corpus_id}.aligned.json",
        ),
        "words_ndjson_file": path_from_record_or_fallback(
            record,
            "words_ndjson_file",
            alignment_dir / f"{corpus_id}.words.ndjson",
        ),
        "diarisation_json_file": path_from_record_or_fallback(
            record,
            "diarisation_json_file",
            diarisation_dir / f"{corpus_id}.diarisation.json",
        ),
        "segments_ndjson_file": path_from_record_or_fallback(
            record,
            "segments_ndjson_file",
            diarisation_dir / f"{corpus_id}.segments.ndjson",
        ),
    }


def path_from_record_or_fallback(record: dict[str, Any], field: str, fallback: Path) -> Path:
    """Resolve one path field from a record, falling back when the field is absent or blank."""
    value = record.get(field)
    if isinstance(value, str) and value.strip():
        return resolve_script_relative_path(Path(value.strip()))
    return fallback


def plan_qc_reports(
    records: list[dict[str, Any]],
    alignment_dir: Path,
    diarisation_dir: Path,
    speaker_transcripts_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_corpus_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Create planned, skipped, and missing-input QC records.

    Args:
        records: Valid eligible records in input order.
        alignment_dir: Fallback alignment directory.
        diarisation_dir: Fallback diarisation directory.
        speaker_transcripts_dir: Fallback speaker transcript directory.
        output_dir: QC output directory.
        test_mode: Whether to limit planned reports.
        test_limit: Maximum planned reports in test mode.
        reprocess: Whether to overwrite existing complete reports.
        start_corpus_id: Optional corpus_id from which to start planning.

    Returns:
        Tuple of planned items, skipped-existing items, and missing-input items.

    I/O:
        Checks existence of expected input and output files.

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
        input_paths = resolve_qc_input_paths(record, alignment_dir, diarisation_dir, speaker_transcripts_dir)

        qc_json_path = output_dir / f"{corpus_id}{OUTPUT_QC_JSON_EXTENSION}"
        qc_md_path = output_dir / f"{corpus_id}{OUTPUT_QC_MARKDOWN_EXTENSION}"

        item = {
            "record": record,
            "corpus_id": corpus_id,
            "input_paths": input_paths,
            "qc_json_path": qc_json_path,
            "qc_markdown_path": qc_md_path,
        }

        words_available = any(
            path and path.exists()
            for path in (input_paths["speaker_words_ndjson_file"], input_paths["speaker_words_json_file"])
        )
        segments_available = any(
            path and path.exists()
            for path in (input_paths["speaker_segments_ndjson_file"], input_paths["speaker_segments_json_file"])
        )

        if not words_available or not segments_available:
            missing_input.append(item)
            continue

        if qc_json_path.exists() and qc_md_path.exists() and not reprocess:
            skipped_existing.append(item)
            continue

        planned.append(item)

    if test_mode:
        planned = planned[:test_limit]

    return planned, skipped_existing, missing_input


def load_ndjson_records(path: Path) -> list[dict[str, Any]]:
    """
    Load a line-oriented NDJSON file.

    Args:
        path: NDJSON file path.

    Returns:
        List of JSON objects.

    I/O:
        Reads the file.

    Error behaviour:
        Raises ValueError for malformed lines or non-object records.
    """
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Invalid NDJSON object in {path} at line {line_number}: expected object.")
            records.append(record)
    return records


def load_json_object(path: Path) -> dict[str, Any]:
    """
    Load a JSON object file.

    Args:
        path: JSON file path.

    Returns:
        JSON object dictionary.

    I/O:
        Reads the file.

    Error behaviour:
        Raises ValueError if the file does not contain a JSON object.
    """
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}.")
    return data


def load_json_list_or_object_records(path: Path, preferred_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """Load records from a JSON file that may be a list or object containing a list."""
    data = load_json_object(path)
    for key in preferred_keys:
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if all(isinstance(value, dict) for value in data.values()):
        return [value for value in data.values() if isinstance(value, dict)]
    return []


def load_records_with_fallback(ndjson_path: Path | None, json_path: Path | None, json_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """Load NDJSON records first, then fallback JSON records when available."""
    if ndjson_path and ndjson_path.exists():
        return load_ndjson_records(ndjson_path)
    if json_path and json_path.exists():
        return load_json_list_or_object_records(json_path, json_keys)
    return []


def to_float(value: Any) -> float | None:
    """Convert common numeric values to float, returning None for unusable values."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_start(record: dict[str, Any]) -> float | None:
    """Extract a start timestamp from a record using common field names."""
    for field in ("start", "start_time", "start_seconds"):
        value = to_float(record.get(field))
        if value is not None:
            return value
    return None


def get_end(record: dict[str, Any]) -> float | None:
    """Extract an end timestamp from a record using common field names."""
    for field in ("end", "end_time", "end_seconds"):
        value = to_float(record.get(field))
        if value is not None:
            return value
    return None


def get_speaker(record: dict[str, Any]) -> str | None:
    """Extract a speaker label from a record using common field names."""
    value = record.get("speaker") or record.get("speaker_label") or record.get("assigned_speaker")
    if value is None:
        return None
    return str(value)


def get_word_text(record: dict[str, Any]) -> str:
    """Extract word text from a record using common field names."""
    value = record.get("word") or record.get("text") or record.get("token") or ""
    return str(value)


def is_unknown_speaker(speaker: str | None) -> bool:
    """Return True if a speaker label should be treated as unknown or unassigned."""
    if speaker is None:
        return True
    return speaker.strip() in UNKNOWN_SPEAKER_LABELS or speaker.strip().upper() == "UNKNOWN_SPEAKER"


def duration_of(record: dict[str, Any]) -> float | None:
    """Return positive duration for a timestamped record, if available."""
    start = get_start(record)
    end = get_end(record)
    if start is None or end is None or end <= start:
        return None
    return end - start


def find_long_gaps(records: list[dict[str, Any]], threshold: float) -> list[dict[str, float]]:
    """Find long timestamp gaps between adjacent sorted records."""
    timed = []
    for record in records:
        start = get_start(record)
        end = get_end(record)
        if start is not None and end is not None and end > start:
            timed.append((start, end))
    timed.sort()

    gaps: list[dict[str, float]] = []
    previous_end: float | None = None
    for start, end in timed:
        if previous_end is not None and start - previous_end >= threshold:
            gaps.append(
                {
                    "start": round(previous_end, 3),
                    "end": round(start, 3),
                    "duration_seconds": round(start - previous_end, 3),
                }
            )
        previous_end = max(previous_end or end, end)
    return gaps


def compute_alignment_metrics(
    alignment_words: list[dict[str, Any]],
    duration_seconds: float | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute alignment word coverage and timestamp QC metrics.

    Args:
        alignment_words: Aligned word records.
        duration_seconds: Expected audio/source duration, if known.
        config: QC threshold configuration.

    Returns:
        Alignment metrics dictionary.

    I/O:
        None.

    Error behaviour:
        Does not raise for malformed records; counts anomalies.
    """
    word_count = len(alignment_words)
    aligned_word_count = 0
    invalid_timing_count = 0
    non_monotonic_count = 0
    long_word_count = 0
    starts: list[float] = []
    ends: list[float] = []

    previous_start: float | None = None
    for word in alignment_words:
        start = get_start(word)
        end = get_end(word)
        if start is None or end is None:
            invalid_timing_count += 1
            continue
        if end <= start:
            invalid_timing_count += 1
            continue
        if previous_start is not None and start < previous_start:
            non_monotonic_count += 1
        if end - start > 3.0:
            long_word_count += 1
        previous_start = start
        aligned_word_count += 1
        starts.append(start)
        ends.append(end)

    earliest = min(starts) if starts else None
    latest = max(ends) if ends else None
    span = latest - earliest if earliest is not None and latest is not None else None

    return {
        "word_count": word_count,
        "aligned_word_count": aligned_word_count,
        "unaligned_word_count": word_count - aligned_word_count,
        "missing_word_timing_ratio": safe_ratio(word_count - aligned_word_count, word_count),
        "invalid_word_timing_count": invalid_timing_count,
        "non_monotonic_word_count": non_monotonic_count,
        "long_word_duration_count": long_word_count,
        "earliest_word_timestamp": earliest,
        "latest_word_timestamp": latest,
        "transcript_time_span_seconds": span,
        "transcript_coverage_ratio": safe_ratio(span, duration_seconds),
        "long_gaps": find_long_gaps(alignment_words, config["gap_warning_threshold"]),
        "long_gap_count": len(find_long_gaps(alignment_words, config["gap_warning_threshold"])),
    }


def compute_diarisation_metrics(
    diarisation_segments: list[dict[str, Any]],
    duration_seconds: float | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute diarisation coverage and speaker interval QC metrics.

    Args:
        diarisation_segments: Diarisation interval records.
        duration_seconds: Expected audio/source duration, if known.
        config: QC threshold configuration.

    Returns:
        Diarisation metrics dictionary.

    I/O:
        None.

    Error behaviour:
        Does not raise for malformed records; counts anomalies.
    """
    speaker_durations: Counter[str] = Counter()
    valid_intervals = []
    invalid_count = 0
    overlap_count = 0
    short_interval_count = 0
    long_interval_count = 0

    for segment in diarisation_segments:
        start = get_start(segment)
        end = get_end(segment)
        speaker = get_speaker(segment) or "UNKNOWN_SPEAKER"
        if start is None or end is None or end <= start:
            invalid_count += 1
            continue
        duration = end - start
        if duration < config["short_turn_threshold"]:
            short_interval_count += 1
        if duration > config["long_turn_threshold"]:
            long_interval_count += 1
        speaker_durations[speaker] += duration
        valid_intervals.append((start, end, speaker))

    valid_intervals.sort()
    previous_end: float | None = None
    for start, end, _speaker in valid_intervals:
        if previous_end is not None and start < previous_end:
            overlap_count += 1
        previous_end = max(previous_end or end, end)

    total_diarised = sum(speaker_durations.values())
    top_speaker, top_duration = most_common_counter_item(speaker_durations)

    gaps = find_long_gaps(diarisation_segments, config["gap_warning_threshold"])

    return {
        "segment_count": len(diarisation_segments),
        "valid_segment_count": len(valid_intervals),
        "invalid_segment_count": invalid_count,
        "detected_speaker_count": len([speaker for speaker in speaker_durations if not is_unknown_speaker(speaker)]),
        "total_diarised_speech_seconds": round(total_diarised, 3),
        "diarisation_coverage_ratio": safe_ratio(total_diarised, duration_seconds),
        "speaker_durations": dict(speaker_durations),
        "top_speaker_by_duration": top_speaker,
        "top_speaker_duration_seconds": round(top_duration, 3) if top_duration is not None else None,
        "top_speaker_duration_ratio": safe_ratio(top_duration, total_diarised),
        "short_interval_count": short_interval_count,
        "long_interval_count": long_interval_count,
        "overlap_count": overlap_count,
        "long_gaps": gaps,
        "long_gap_count": len(gaps),
    }


def compute_word_assignment_metrics(
    speaker_words: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute word-level speaker assignment QC metrics.

    Args:
        speaker_words: Speaker-attributed word records.
        config: QC threshold configuration.

    Returns:
        Speaker assignment metrics dictionary.

    I/O:
        None.

    Error behaviour:
        Does not raise for malformed records; counts anomalies.
    """
    speaker_word_count = len(speaker_words)
    assigned_word_count = 0
    unknown_speaker_word_count = 0
    missing_timing_count = 0
    timing_anomaly_count = 0
    speaker_counts: Counter[str] = Counter()
    speaker_durations: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    unknown_spans: list[dict[str, float]] = []
    current_unknown_start: float | None = None
    current_unknown_end: float | None = None

    sorted_words = sorted(
        speaker_words,
        key=lambda record: get_start(record) if get_start(record) is not None else float("inf"),
    )

    for word in sorted_words:
        speaker = get_speaker(word)
        status = str(word.get("assignment_status") or word.get("speaker_assignment_status") or "unknown")
        status_counts[status] += 1

        start = get_start(word)
        end = get_end(word)
        duration = duration_of(word)
        if start is None or end is None:
            missing_timing_count += 1
        elif end <= start:
            timing_anomaly_count += 1

        unknown = is_unknown_speaker(speaker)
        if unknown:
            unknown_speaker_word_count += 1
            if start is not None and end is not None and end > start:
                if current_unknown_start is None:
                    current_unknown_start = start
                    current_unknown_end = end
                elif start <= (current_unknown_end or start) + config["gap_warning_threshold"]:
                    current_unknown_end = max(current_unknown_end or end, end)
                else:
                    unknown_spans.append(
                        {
                            "start": current_unknown_start,
                            "end": current_unknown_end or current_unknown_start,
                            "duration_seconds": (current_unknown_end or current_unknown_start) - current_unknown_start,
                        }
                    )
                    current_unknown_start = start
                    current_unknown_end = end
            continue

        speaker_label = speaker or "UNKNOWN_SPEAKER"
        assigned_word_count += 1
        speaker_counts[speaker_label] += 1
        if duration is not None:
            speaker_durations[speaker_label] += duration

    if current_unknown_start is not None:
        unknown_spans.append(
            {
                "start": current_unknown_start,
                "end": current_unknown_end or current_unknown_start,
                "duration_seconds": (current_unknown_end or current_unknown_start) - current_unknown_start,
            }
        )

    long_unknown_spans = [
        span
        for span in unknown_spans
        if span["duration_seconds"] >= config["unknown_span_warning_threshold"]
    ]

    top_speaker_words, top_word_count = most_common_counter_item(speaker_counts)
    top_speaker_duration, top_duration = most_common_counter_item(speaker_durations)

    gaps = find_long_gaps(speaker_words, config["gap_warning_threshold"])

    return {
        "speaker_word_count": speaker_word_count,
        "assigned_word_count": assigned_word_count,
        "unassigned_word_count": speaker_word_count - assigned_word_count,
        "unknown_speaker_word_count": unknown_speaker_word_count,
        "unknown_word_ratio": safe_ratio(unknown_speaker_word_count, speaker_word_count),
        "speaker_assignment_coverage_ratio": safe_ratio(assigned_word_count, speaker_word_count),
        "missing_word_timing_count": missing_timing_count,
        "missing_word_timing_ratio": safe_ratio(missing_timing_count, speaker_word_count),
        "timing_anomaly_count": timing_anomaly_count,
        "assigned_speaker_count": len(speaker_counts),
        "speaker_word_distribution": dict(speaker_counts),
        "speaker_duration_distribution": dict(speaker_durations),
        "assignment_status_distribution": dict(status_counts),
        "top_speaker_by_words": top_speaker_words,
        "top_speaker_word_count": top_word_count,
        "top_speaker_word_ratio": safe_ratio(top_word_count, assigned_word_count),
        "top_speaker_by_duration": top_speaker_duration,
        "top_speaker_duration_seconds": round(top_duration, 3) if top_duration is not None else None,
        "top_speaker_duration_ratio": safe_ratio(top_duration, sum(speaker_durations.values())),
        "long_unknown_spans": long_unknown_spans,
        "long_unknown_span_count": len(long_unknown_spans),
        "long_gaps": gaps,
        "long_gap_count": len(gaps),
    }


def compute_speaker_segment_metrics(
    speaker_segments: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute speaker-segment and turn-taking QC metrics.

    Args:
        speaker_segments: Speaker-attributed segment records.
        config: QC threshold configuration.

    Returns:
        Segment and turn-taking metrics dictionary.

    I/O:
        None.

    Error behaviour:
        Does not raise for malformed records; counts anomalies.
    """
    durations: list[float] = []
    words_per_segment: list[int] = []
    short_turn_count = 0
    long_turn_count = 0
    invalid_timing_count = 0
    speaker_switch_count = 0
    segment_word_total = 0

    sorted_segments = sorted(
        speaker_segments,
        key=lambda record: get_start(record) if get_start(record) is not None else float("inf"),
    )

    previous_speaker: str | None = None
    for segment in sorted_segments:
        duration = duration_of(segment)
        if duration is None:
            invalid_timing_count += 1
        else:
            durations.append(duration)
            if duration < config["short_turn_threshold"]:
                short_turn_count += 1
            if duration > config["long_turn_threshold"]:
                long_turn_count += 1

        speaker = get_speaker(segment)
        if previous_speaker is not None and speaker != previous_speaker:
            speaker_switch_count += 1
        previous_speaker = speaker

        word_count = extract_segment_word_count(segment)
        segment_word_total += word_count
        words_per_segment.append(word_count)

    return {
        "speaker_segment_count": len(speaker_segments),
        "invalid_segment_timing_count": invalid_timing_count,
        "short_turn_count": short_turn_count,
        "short_turn_ratio": safe_ratio(short_turn_count, len(speaker_segments)),
        "long_turn_count": long_turn_count,
        "speaker_switch_count": speaker_switch_count,
        "average_segment_duration": round(statistics.mean(durations), 3) if durations else None,
        "median_segment_duration": round(statistics.median(durations), 3) if durations else None,
        "average_words_per_segment": round(statistics.mean(words_per_segment), 3) if words_per_segment else None,
        "segment_word_total": segment_word_total,
    }


def extract_segment_word_count(segment: dict[str, Any]) -> int:
    """Extract a best-effort word count from a speaker segment record."""
    for field in ("word_count", "words_count", "num_words"):
        value = segment.get(field)
        if isinstance(value, int):
            return value
    words = segment.get("words")
    if isinstance(words, list):
        return len(words)
    text = segment.get("text") or segment.get("transcript") or ""
    return len(str(text).split())


def safe_ratio(numerator: Any, denominator: Any) -> float | None:
    """Safely compute a ratio, returning None when unavailable or denominator is zero."""
    num = to_float(numerator)
    den = to_float(denominator)
    if num is None or den is None or den == 0:
        return None
    return round(num / den, 6)


def most_common_counter_item(counter: Counter[str]) -> tuple[str | None, float | None]:
    """Return the most common item and count from a Counter."""
    if not counter:
        return None, None
    key, value = counter.most_common(1)[0]
    return key, value


def generate_qc_warnings(metrics: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Generate structured QC warnings from computed metrics.

    Args:
        metrics: Nested metrics dictionary.
        config: QC threshold configuration.

    Returns:
        List of warning dictionaries.

    I/O:
        None.

    Error behaviour:
        Does not raise for missing optional metrics.
    """
    warnings: list[dict[str, Any]] = []

    alignment = metrics.get("alignment", {})
    diarisation = metrics.get("diarisation", {})
    assignment = metrics.get("speaker_assignment", {})
    turns = metrics.get("turn_taking", {})

    if metrics.get("input_availability", {}).get("words_ndjson_file") is False:
        warnings.append(make_warning("optional_alignment_missing", "review", "Optional alignment word file is missing."))
    if metrics.get("input_availability", {}).get("segments_ndjson_file") is False:
        warnings.append(make_warning("optional_diarisation_missing", "review", "Optional diarisation segment file is missing."))

    if alignment and alignment.get("word_count") == 0:
        warnings.append(make_warning("no_aligned_words", "error", "No aligned words are available."))
    if above(alignment.get("missing_word_timing_ratio"), 0.05):
        warnings.append(
            make_warning(
                "alignment_missing_timing_warning",
                "warning",
                "More than 5% of aligned words are missing usable timing.",
                alignment.get("missing_word_timing_ratio"),
                0.05,
            )
        )
    if alignment.get("non_monotonic_word_count", 0) > 0:
        warnings.append(make_warning("alignment_non_monotonic_timing", "warning", "Non-monotonic aligned word timestamps were detected."))
    if below(alignment.get("transcript_coverage_ratio"), 0.50):
        warnings.append(
            make_warning(
                "low_alignment_coverage",
                "warning",
                "Transcript timing span covers less than 50% of expected duration.",
                alignment.get("transcript_coverage_ratio"),
                0.50,
            )
        )

    if diarisation and diarisation.get("segment_count") == 0:
        warnings.append(make_warning("no_diarisation_segments", "error", "No diarisation segments are available."))
    if below(diarisation.get("detected_speaker_count"), config["min_expected_speakers"]):
        warnings.append(
            make_warning(
                "low_detected_speaker_count",
                "warning",
                "Detected speaker count is lower than expected.",
                diarisation.get("detected_speaker_count"),
                config["min_expected_speakers"],
            )
        )
    if above(diarisation.get("detected_speaker_count"), config["max_expected_speakers"]):
        warnings.append(
            make_warning(
                "high_detected_speaker_count",
                "warning",
                "Detected speaker count is higher than expected.",
                diarisation.get("detected_speaker_count"),
                config["max_expected_speakers"],
            )
        )
    if below(diarisation.get("diarisation_coverage_ratio"), config["diarisation_coverage_warning_threshold"]):
        warnings.append(
            make_warning(
                "low_diarisation_coverage",
                "warning",
                "Diarisation coverage is below threshold.",
                diarisation.get("diarisation_coverage_ratio"),
                config["diarisation_coverage_warning_threshold"],
            )
        )
    if above(diarisation.get("diarisation_coverage_ratio"), config["diarisation_coverage_high_warning_threshold"]):
        warnings.append(
            make_warning(
                "high_diarisation_coverage",
                "review",
                "Diarisation coverage is unexpectedly high.",
                diarisation.get("diarisation_coverage_ratio"),
                config["diarisation_coverage_high_warning_threshold"],
            )
        )
    if diarisation.get("overlap_count", 0) > 0:
        warnings.append(make_warning("diarisation_overlaps_detected", "review", "Overlapping diarisation intervals were detected."))

    if assignment.get("speaker_word_count") == 0:
        warnings.append(make_warning("no_speaker_words", "error", "No speaker word records are available."))
    if turns.get("speaker_segment_count") == 0:
        warnings.append(make_warning("no_speaker_segments", "error", "No speaker segment records are available."))
    if above(assignment.get("unknown_word_ratio"), config["unassigned_word_ratio_warning_threshold"]):
        warnings.append(
            make_warning(
                "high_unknown_word_ratio",
                "warning",
                "Unknown or unassigned speaker word ratio is above threshold.",
                assignment.get("unknown_word_ratio"),
                config["unassigned_word_ratio_warning_threshold"],
            )
        )
    if assignment.get("long_unknown_span_count", 0) > 0:
        warnings.append(make_warning("long_unknown_speaker_spans", "warning", "Long UNKNOWN_SPEAKER spans were detected."))
    if below(assignment.get("assigned_speaker_count"), config["min_expected_speakers"]):
        warnings.append(make_warning("low_assigned_speaker_count", "warning", "Assigned speaker count is lower than expected."))
    if above(assignment.get("assigned_speaker_count"), config["max_expected_speakers"]):
        warnings.append(make_warning("high_assigned_speaker_count", "warning", "Assigned speaker count is higher than expected."))
    if above(turns.get("short_turn_ratio"), config["short_turn_ratio_warning_threshold"]):
        warnings.append(make_warning("short_turn_ratio_review", "review", "Short speaker-turn ratio is elevated; diarisation may be fragmented."))
    if above(assignment.get("top_speaker_word_ratio"), config["speaker_imbalance_warning_threshold"]):
        warnings.append(make_warning("top_speaker_word_imbalance", "review", "Top speaker accounts for a large fraction of assigned words."))
    if above(assignment.get("top_speaker_duration_ratio"), config["speaker_imbalance_warning_threshold"]):
        warnings.append(make_warning("top_speaker_duration_imbalance", "review", "Top speaker accounts for a large fraction of assigned duration."))

    if turns.get("segment_word_total") is not None and assignment.get("speaker_word_count") is not None:
        difference = abs(turns.get("segment_word_total", 0) - assignment.get("speaker_word_count", 0))
        if assignment.get("speaker_word_count", 0) and difference / assignment["speaker_word_count"] > 0.05:
            warnings.append(
                make_warning(
                    "speaker_word_segment_total_mismatch",
                    "warning",
                    "Speaker word count differs from segment-derived word total by more than 5%.",
                    difference,
                    0.05,
                )
            )

    return warnings


def make_warning(
    code: str,
    severity: str,
    message: str,
    value: Any = None,
    threshold: Any = None,
) -> dict[str, Any]:
    """Create one structured warning dictionary."""
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "value": value,
        "threshold": threshold,
    }


def above(value: Any, threshold: Any) -> bool:
    """Return True when value and threshold are numeric and value is greater than threshold."""
    value_float = to_float(value)
    threshold_float = to_float(threshold)
    return value_float is not None and threshold_float is not None and value_float > threshold_float


def below(value: Any, threshold: Any) -> bool:
    """Return True when value and threshold are numeric and value is less than threshold."""
    value_float = to_float(value)
    threshold_float = to_float(threshold)
    return value_float is not None and threshold_float is not None and value_float < threshold_float


def assign_qc_rating(warnings: list[dict[str, Any]], metrics: dict[str, Any]) -> str:
    """
    Assign an overall QC rating for one debate.

    Args:
        warnings: Structured warning list.
        metrics: Per-debate metrics.

    Returns:
        One of pass, review, warning, fail, or unknown.

    I/O:
        None.

    Error behaviour:
        Does not raise.
    """
    if any(warning.get("severity") == "error" for warning in warnings):
        return "fail"
    if not metrics.get("speaker_assignment", {}).get("speaker_word_count") and not metrics.get("turn_taking", {}).get("speaker_segment_count"):
        return "unknown"
    if any(warning.get("severity") == "warning" for warning in warnings):
        return "warning"
    if any(warning.get("severity") == "review" for warning in warnings):
        return "review"
    return "pass"


def build_qc_json(
    item: dict[str, Any],
    metrics: dict[str, Any],
    warnings: list[dict[str, Any]],
    rating: str,
    run_metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Build the per-debate QC JSON object.

    Args:
        item: Planned QC item.
        metrics: Computed metrics.
        warnings: Structured warnings.
        rating: Overall QC rating.
        run_metadata: Current run metadata.

    Returns:
        JSON-serialisable QC report object.

    I/O:
        None.

    Error behaviour:
        Does not raise for missing optional metadata.
    """
    record = item["record"]
    recommendations = build_recommendations(warnings)

    return {
        "corpus_id": item["corpus_id"],
        "qc_status": "success",
        "qc_rating": rating,
        "metadata": make_item_base(record),
        "input_paths": {
            key: str(value) if value is not None else None
            for key, value in item["input_paths"].items()
        },
        "input_availability": metrics.get("input_availability", {}),
        "metrics": {
            key: value
            for key, value in metrics.items()
            if key != "input_availability"
        },
        "warnings": warnings,
        "recommendations": recommendations,
        "run": {
            "qc_run_id": run_metadata["run_id"],
            "qc_at_utc": run_metadata["start_time"],
        },
        "error": None,
    }


def build_recommendations(warnings: list[dict[str, Any]]) -> list[str]:
    """Build human-readable manual review recommendations from warnings."""
    recommendations = [
        "Spot-check the plain-text speaker transcript against the audio.",
        "Compare detected and assigned speaker counts against the expected debate format.",
    ]
    codes = {warning.get("code") for warning in warnings}
    if "high_unknown_word_ratio" in codes or "long_unknown_speaker_spans" in codes:
        recommendations.append("Inspect long or frequent UNKNOWN_SPEAKER spans.")
    if "short_turn_ratio_review" in codes:
        recommendations.append("Review rapid speaker switches and very short turns for diarisation fragmentation.")
    if "low_diarisation_coverage" in codes or "high_diarisation_coverage" in codes:
        recommendations.append("Inspect diarisation coverage and long gaps against the audio timeline.")
    if "top_speaker_word_imbalance" in codes or "top_speaker_duration_imbalance" in codes:
        recommendations.append("Review top speakers by word count and duration for plausibility.")
    return recommendations


def render_qc_markdown(qc_json: dict[str, Any]) -> str:
    """
    Render a human-readable Markdown QC report.

    Args:
        qc_json: Per-debate QC JSON object.

    Returns:
        Markdown report string.

    I/O:
        None.

    Error behaviour:
        Does not raise for missing optional metrics.
    """
    corpus_id = qc_json["corpus_id"]
    metadata = qc_json.get("metadata", {})
    metrics = qc_json.get("metrics", {})
    alignment = metrics.get("alignment", {})
    diarisation = metrics.get("diarisation", {})
    assignment = metrics.get("speaker_assignment", {})
    turns = metrics.get("turn_taking", {})
    warnings = qc_json.get("warnings", [])

    lines = [
        f"# QC Report — `{corpus_id}`",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---:|",
        f"| QC rating | {qc_json.get('qc_rating')} |",
        f"| Title | {metadata.get('title_selected') or metadata.get('title_extracted') or ''} |",
        f"| Duration | {metadata.get('duration_string') or metadata.get('duration_seconds') or ''} |",
        f"| Alignment words | {fmt_int(alignment.get('word_count'))} |",
        f"| Detected speakers | {fmt_int(diarisation.get('detected_speaker_count'))} |",
        f"| Assigned speakers | {fmt_int(assignment.get('assigned_speaker_count'))} |",
        f"| Speaker words | {fmt_int(assignment.get('speaker_word_count'))} |",
        f"| Assigned words | {fmt_int(assignment.get('assigned_word_count'))} |",
        f"| Unknown speaker words | {fmt_int(assignment.get('unknown_speaker_word_count'))} |",
        f"| Unknown word ratio | {fmt_percent(assignment.get('unknown_word_ratio'))} |",
        f"| Diarisation coverage | {fmt_percent(diarisation.get('diarisation_coverage_ratio'))} |",
        f"| Speaker segments | {fmt_int(turns.get('speaker_segment_count'))} |",
        f"| Short turn ratio | {fmt_percent(turns.get('short_turn_ratio'))} |",
        "",
        "## Warnings",
        "",
    ]

    if warnings:
        lines.extend(["| Severity | Code | Message |", "|---|---|---|"])
        for warning in warnings:
            lines.append(
                f"| {warning.get('severity')} | `{warning.get('code')}` | {warning.get('message')} |"
            )
    else:
        lines.append("No warnings detected.")

    lines.extend(
        [
            "",
            "## Speaker Distribution",
            "",
            "| Speaker | Words | Word % | Duration seconds | Duration % |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    word_distribution = assignment.get("speaker_word_distribution", {})
    duration_distribution = assignment.get("speaker_duration_distribution", {})
    assigned_words = assignment.get("assigned_word_count") or 0
    total_duration = sum(to_float(value) or 0 for value in duration_distribution.values())

    for speaker, words in sorted(word_distribution.items(), key=lambda item: item[1], reverse=True)[:20]:
        duration = to_float(duration_distribution.get(speaker)) or 0
        lines.append(
            f"| `{speaker}` | {fmt_int(words)} | {fmt_percent(safe_ratio(words, assigned_words))} | "
            f"{fmt_float(duration)} | {fmt_percent(safe_ratio(duration, total_duration))} |"
        )

    lines.extend(["", "## Recommended Manual Checks", ""])
    for recommendation in qc_json.get("recommendations", []):
        lines.append(f"- {recommendation}")

    lines.append("")
    return "\n".join(lines)


def build_corpus_summary(
    qc_results: list[dict[str, Any]],
    run_metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Build corpus-level QC summary JSON.

    Args:
        qc_results: Successful per-debate QC JSON results.
        run_metadata: Current run metadata.

    Returns:
        Corpus-level summary JSON.

    I/O:
        None.

    Error behaviour:
        Does not raise.
    """
    rating_counts = Counter(result.get("qc_rating", "unknown") for result in qc_results)
    warning_counts = Counter()
    items: list[dict[str, Any]] = []

    total_audio = 0.0
    total_speaker_words = 0
    total_assigned_words = 0
    total_unknown_words = 0

    for result in qc_results:
        metrics = result.get("metrics", {})
        assignment = metrics.get("speaker_assignment", {})
        diarisation = metrics.get("diarisation", {})
        metadata = result.get("metadata", {})

        total_audio += to_float(metadata.get("duration_seconds")) or 0
        total_speaker_words += int(assignment.get("speaker_word_count") or 0)
        total_assigned_words += int(assignment.get("assigned_word_count") or 0)
        total_unknown_words += int(assignment.get("unknown_speaker_word_count") or 0)

        for warning in result.get("warnings", []):
            warning_counts[warning.get("code", "unknown")] += 1

        items.append(
            {
                "corpus_id": result.get("corpus_id"),
                "qc_rating": result.get("qc_rating"),
                "detected_speaker_count": diarisation.get("detected_speaker_count"),
                "assigned_speaker_count": assignment.get("assigned_speaker_count"),
                "unknown_word_ratio": assignment.get("unknown_word_ratio"),
                "diarisation_coverage_ratio": diarisation.get("diarisation_coverage_ratio"),
                "warning_count": len(result.get("warnings", [])),
            }
        )

    return {
        "run": {
            "qc_run_id": run_metadata["run_id"],
            "qc_at_utc": run_metadata["start_time"],
        },
        "summary": {
            "debates_evaluated": len(qc_results),
            "passed": rating_counts.get("pass", 0),
            "review": rating_counts.get("review", 0),
            "warning": rating_counts.get("warning", 0),
            "failed": rating_counts.get("fail", 0),
            "unknown": rating_counts.get("unknown", 0),
            "total_audio_duration_seconds": round(total_audio, 3),
            "total_speaker_words": total_speaker_words,
            "total_assigned_words": total_assigned_words,
            "total_unknown_speaker_words": total_unknown_words,
            "overall_unknown_word_ratio": safe_ratio(total_unknown_words, total_speaker_words),
        },
        "items": items,
        "common_warnings": [
            {"code": code, "count": count}
            for code, count in warning_counts.most_common()
        ],
    }


def render_corpus_summary_markdown(summary: dict[str, Any]) -> str:
    """
    Render corpus-level QC summary Markdown.

    Args:
        summary: Corpus summary JSON object.

    Returns:
        Markdown summary string.

    I/O:
        None.

    Error behaviour:
        Does not raise.
    """
    summary_data = summary.get("summary", {})
    run = summary.get("run", {})

    lines = [
        "# Jubilee Debate Speaker Diarisation QC Summary",
        "",
        "## Run",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| QC run ID | `{run.get('qc_run_id')}` |",
        f"| QC at UTC | {run.get('qc_at_utc')} |",
        f"| Debates evaluated | {summary_data.get('debates_evaluated', 0)} |",
        "",
        "## Overall Results",
        "",
        "| Rating | Count |",
        "|---|---:|",
        f"| pass | {summary_data.get('passed', 0)} |",
        f"| review | {summary_data.get('review', 0)} |",
        f"| warning | {summary_data.get('warning', 0)} |",
        f"| fail | {summary_data.get('failed', 0)} |",
        f"| unknown | {summary_data.get('unknown', 0)} |",
        "",
        "## Aggregate Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Total speaker words | {fmt_int(summary_data.get('total_speaker_words'))} |",
        f"| Total assigned words | {fmt_int(summary_data.get('total_assigned_words'))} |",
        f"| Total unknown speaker words | {fmt_int(summary_data.get('total_unknown_speaker_words'))} |",
        f"| Overall unknown word ratio | {fmt_percent(summary_data.get('overall_unknown_word_ratio'))} |",
        "",
        "## Debate Summary",
        "",
        "| Corpus ID | Rating | Speakers | Unknown word % | Diarisation coverage | Warnings |",
        "|---|---|---:|---:|---:|---:|",
    ]

    for item in summary.get("items", []):
        speakers = item.get("assigned_speaker_count") or item.get("detected_speaker_count")
        lines.append(
            f"| `{item.get('corpus_id')}` | {item.get('qc_rating')} | {fmt_int(speakers)} | "
            f"{fmt_percent(item.get('unknown_word_ratio'))} | "
            f"{fmt_percent(item.get('diarisation_coverage_ratio'))} | "
            f"{fmt_int(item.get('warning_count'))} |"
        )

    lines.extend(["", "## Common Warnings", ""])
    common_warnings = summary.get("common_warnings", [])
    if common_warnings:
        lines.extend(["| Code | Count |", "|---|---:|"])
        for warning in common_warnings:
            lines.append(f"| `{warning.get('code')}` | {warning.get('count')} |")
    else:
        lines.append("No common warnings.")

    lines.extend(
        [
            "",
            "## Recommended Next Actions",
            "",
            "- Review debates rated `warning` first.",
            "- Spot-check debates with high unknown-speaker word ratios.",
            "- Inspect debates with unexpectedly low or high speaker counts.",
            "- Compare rapid speaker-switch regions against the audio.",
            "",
        ]
    )

    return "\n".join(lines)


def write_qc_outputs(
    qc_json: dict[str, Any],
    qc_markdown: str,
    qc_json_path: Path,
    qc_md_path: Path,
) -> None:
    """
    Write per-debate QC JSON and Markdown outputs.

    Args:
        qc_json: Per-debate QC JSON object.
        qc_markdown: Rendered Markdown report.
        qc_json_path: Destination JSON path.
        qc_md_path: Destination Markdown path.

    Returns:
        None.

    I/O:
        Writes files.

    Error behaviour:
        Propagates OSError and JSON serialisation errors.
    """
    qc_json_path.parent.mkdir(parents=True, exist_ok=True)
    qc_json_path.write_text(json.dumps(qc_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    qc_md_path.write_text(qc_markdown, encoding="utf-8")


def write_qc_index(index_records: list[dict[str, Any]], qc_index_file: Path) -> None:
    """
    Write curated NDJSON QC index.

    Args:
        index_records: QC index records.
        qc_index_file: Destination NDJSON path.

    Returns:
        None.

    I/O:
        Writes the NDJSON file.

    Error behaviour:
        Propagates OSError and JSON serialisation errors.
    """
    qc_index_file.parent.mkdir(parents=True, exist_ok=True)
    with qc_index_file.open("w", encoding="utf-8") as handle:
        for record in index_records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=False) + "\n")


def write_manifests(
    manifest: dict[str, Any],
    manifest_file: Path,
    run_id: str,
) -> tuple[Path, Path]:
    """
    Write latest and timestamped manifest files.

    Args:
        manifest: JSON-serialisable manifest dictionary.
        manifest_file: Latest manifest path.
        run_id: Current run ID.

    Returns:
        Tuple of latest manifest path and per-run manifest path.

    I/O:
        Writes two JSON files.

    Error behaviour:
        Propagates OSError and JSON serialisation errors.
    """
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    per_run_manifest_file = manifest_file.parent / f"{manifest_file.stem}_{run_id}{manifest_file.suffix}"

    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False)
    manifest_file.write_text(manifest_json + "\n", encoding="utf-8")
    per_run_manifest_file.write_text(manifest_json + "\n", encoding="utf-8")

    return manifest_file, per_run_manifest_file


def process_one_item(
    item: dict[str, Any],
    args: argparse.Namespace,
    config: dict[str, Any],
    run_metadata: dict[str, Any],
    logger: logging.Logger,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Process one planned QC item and return manifest item plus per-debate QC JSON."""
    corpus_id = item["corpus_id"]
    start_time = utc_timestamp()
    monotonic_start = time.monotonic()

    speaker_words = load_records_with_fallback(
        item["input_paths"]["speaker_words_ndjson_file"],
        item["input_paths"]["speaker_words_json_file"],
        ("words", "speaker_words"),
    )
    speaker_segments = load_records_with_fallback(
        item["input_paths"]["speaker_segments_ndjson_file"],
        item["input_paths"]["speaker_segments_json_file"],
        ("segments", "speaker_segments"),
    )
    alignment_words = load_records_with_fallback(
        item["input_paths"]["words_ndjson_file"],
        item["input_paths"]["aligned_json_file"],
        ("words", "word_segments"),
    )
    diarisation_segments = load_records_with_fallback(
        item["input_paths"]["segments_ndjson_file"],
        item["input_paths"]["diarisation_json_file"],
        ("segments", "diarisation_segments"),
    )

    duration_seconds = to_float(item["record"].get("duration_seconds"))

    input_availability = {
        key: bool(path and path.exists())
        for key, path in item["input_paths"].items()
    }

    metrics = {
        "audio_duration_seconds": duration_seconds,
        "input_availability": input_availability,
        "alignment": compute_alignment_metrics(alignment_words, duration_seconds, config),
        "diarisation": compute_diarisation_metrics(diarisation_segments, duration_seconds, config),
        "speaker_assignment": compute_word_assignment_metrics(speaker_words, config),
        "turn_taking": compute_speaker_segment_metrics(speaker_segments, config),
    }

    metrics["speaker_distribution"] = {
        "top_speaker_by_words": metrics["speaker_assignment"].get("top_speaker_by_words"),
        "top_speaker_word_ratio": metrics["speaker_assignment"].get("top_speaker_word_ratio"),
        "top_speaker_by_duration": metrics["speaker_assignment"].get("top_speaker_by_duration"),
        "top_speaker_duration_ratio": metrics["speaker_assignment"].get("top_speaker_duration_ratio"),
    }

    warnings = generate_qc_warnings(metrics, config)
    rating = assign_qc_rating(warnings, metrics)
    qc_json = build_qc_json(item, metrics, warnings, rating, run_metadata)
    qc_markdown = render_qc_markdown(qc_json)

    write_qc_outputs(qc_json, qc_markdown, item["qc_json_path"], item["qc_markdown_path"])

    end_time = utc_timestamp()
    duration = round(time.monotonic() - monotonic_start, 3)

    manifest_item = make_item_base(item["record"]) | {
        "corpus_id": corpus_id,
        "qc_json_path": str(item["qc_json_path"]),
        "qc_markdown_path": str(item["qc_markdown_path"]),
        "status": "success",
        "qc_rating": rating,
        "error": None,
        "retries": 0,
        "duration_seconds": duration,
        "start_time": start_time,
        "end_time": end_time,
        "warning_count": len(warnings),
        "detected_speaker_count": metrics["diarisation"].get("detected_speaker_count"),
        "assigned_speaker_count": metrics["speaker_assignment"].get("assigned_speaker_count"),
        "unknown_word_ratio": metrics["speaker_assignment"].get("unknown_word_ratio"),
        "diarisation_coverage_ratio": metrics["diarisation"].get("diarisation_coverage_ratio"),
        "metadata": {
            "title_selected": item["record"].get("title_selected"),
            "youtube_id": item["record"].get("youtube_id"),
            "duration_seconds": item["record"].get("duration_seconds"),
        },
    }

    logger.info(
        "SUCCESS %s rating=%s warnings=%s",
        corpus_id,
        rating,
        len(warnings),
    )

    return manifest_item, qc_json


def make_item_base(record: dict[str, Any]) -> dict[str, Any]:
    """
    Preserve selected source metadata fields.

    Args:
        record: Source metadata record.

    Returns:
        Dictionary containing preserved fields present in the source record.

    I/O:
        None.

    Error behaviour:
        Does not raise for missing fields.
    """
    return {field: record.get(field) for field in PRESERVED_METADATA_FIELDS if field in record}


def make_missing_input_result(item: dict[str, Any], run_metadata: dict[str, Any]) -> dict[str, Any]:
    """Create a manifest/index result for an item missing required speaker-assignment inputs."""
    missing = [
        key
        for key in (
            "speaker_words_ndjson_file",
            "speaker_words_json_file",
            "speaker_segments_ndjson_file",
            "speaker_segments_json_file",
        )
        if not item["input_paths"].get(key) or not item["input_paths"][key].exists()
    ]
    return make_item_base(item["record"]) | {
        "corpus_id": item["corpus_id"],
        "qc_json_path": str(item["qc_json_path"]),
        "qc_markdown_path": str(item["qc_markdown_path"]),
        "status": "missing_input",
        "qc_status": "missing_input",
        "qc_rating": None,
        "qc_run_id": run_metadata["run_id"],
        "qc_at_utc": run_metadata["start_time"],
        "warning_count": 0,
        "review_flag_count": 0,
        "error_count": 0,
        "error": f"Required speaker-assignment input files are missing or incomplete: {', '.join(missing)}",
    }


def make_skipped_existing_result(item: dict[str, Any], run_metadata: dict[str, Any]) -> dict[str, Any]:
    """Create a manifest/index result for a skipped existing complete QC report."""
    return make_item_base(item["record"]) | {
        "corpus_id": item["corpus_id"],
        "qc_json_path": str(item["qc_json_path"]),
        "qc_markdown_path": str(item["qc_markdown_path"]),
        "qc_json_file": str(item["qc_json_path"]),
        "qc_markdown_file": str(item["qc_markdown_path"]),
        "status": "skipped_existing",
        "qc_status": "skipped_existing",
        "qc_rating": None,
        "qc_run_id": run_metadata["run_id"],
        "qc_at_utc": run_metadata["start_time"],
        "error": None,
        "warning_count": 0,
        "review_flag_count": 0,
        "error_count": 0,
    }


def make_failed_result(
    item: dict[str, Any],
    error: str,
    retries: int,
    start_time: str,
    duration_seconds: float,
    run_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Create a failed manifest/index result for a QC item."""
    return make_item_base(item["record"]) | {
        "corpus_id": item["corpus_id"],
        "qc_json_path": str(item["qc_json_path"]),
        "qc_markdown_path": str(item["qc_markdown_path"]),
        "qc_json_file": str(item["qc_json_path"]),
        "qc_markdown_file": str(item["qc_markdown_path"]),
        "status": "failed",
        "qc_status": "failed",
        "qc_rating": None,
        "qc_run_id": run_metadata["run_id"],
        "qc_at_utc": run_metadata["start_time"],
        "error": error,
        "retries": retries,
        "duration_seconds": duration_seconds,
        "start_time": start_time,
        "end_time": utc_timestamp(),
        "warning_count": 0,
        "review_flag_count": 0,
        "error_count": 1,
    }


def make_qc_index_record(item_result: dict[str, Any], run_metadata: dict[str, Any]) -> dict[str, Any]:
    """Build one QC index record from a manifest item or invalid record."""
    record = {field: item_result.get(field) for field in PRESERVED_METADATA_FIELDS if field in item_result}
    record.update(
        {
            "qc_json_file": item_result.get("qc_json_path") or item_result.get("qc_json_file"),
            "qc_markdown_file": item_result.get("qc_markdown_path") or item_result.get("qc_markdown_file"),
            "qc_status": item_result.get("status") or item_result.get("qc_status"),
            "qc_rating": item_result.get("qc_rating"),
            "qc_run_id": run_metadata["run_id"],
            "qc_at_utc": run_metadata["start_time"],
            "detected_speaker_count": item_result.get("detected_speaker_count"),
            "assigned_speaker_count": item_result.get("assigned_speaker_count"),
            "speaker_word_count": item_result.get("speaker_word_count"),
            "assigned_word_count": item_result.get("assigned_word_count"),
            "unknown_speaker_word_count": item_result.get("unknown_speaker_word_count"),
            "unknown_word_ratio": item_result.get("unknown_word_ratio"),
            "diarisation_coverage_ratio": item_result.get("diarisation_coverage_ratio"),
            "speaker_segment_count": item_result.get("speaker_segment_count"),
            "warning_count": item_result.get("warning_count", 0),
            "review_flag_count": item_result.get("review_flag_count", 0),
            "error_count": item_result.get("error_count", 0),
            "error": item_result.get("error"),
        }
    )
    return record


def build_config(args: argparse.Namespace) -> dict[str, Any]:
    """Build QC threshold configuration dictionary from parsed arguments."""
    return {
        "gap_warning_threshold": args.gap_warning_threshold,
        "unknown_span_warning_threshold": args.unknown_span_warning_threshold,
        "unassigned_word_ratio_warning_threshold": args.unassigned_word_ratio_warning_threshold,
        "diarisation_coverage_warning_threshold": args.diarisation_coverage_warning_threshold,
        "diarisation_coverage_high_warning_threshold": args.diarisation_coverage_high_warning_threshold,
        "min_expected_speakers": args.min_expected_speakers,
        "max_expected_speakers": args.max_expected_speakers,
        "short_turn_threshold": args.short_turn_threshold,
        "short_turn_ratio_warning_threshold": args.short_turn_ratio_warning_threshold,
        "long_turn_threshold": args.long_turn_threshold,
        "speaker_imbalance_warning_threshold": args.speaker_imbalance_warning_threshold,
        "timeout_seconds": args.timeout,
        "max_retries": args.max_retries,
        "retry_delay_seconds": args.retry_delay,
        "start_corpus_id": args.start_corpus_id,
    }


def build_run_metadata(
    args: argparse.Namespace,
    run_id: str,
    start_time: str,
    summary: dict[str, int],
    interrupted: bool,
    end_time: str | None = None,
) -> dict[str, Any]:
    """Construct run_metadata for the JSON manifest."""
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
        "speaker_index_path": str(args.speaker_index),
        "alignment_dir": str(args.alignment_dir),
        "diarisation_dir": str(args.diarisation_dir),
        "speaker_transcripts_dir": str(args.speaker_transcripts_dir),
        "output_dir": str(args.output_dir),
        "qc_index_file": str(args.qc_index_file),
        "log_file": str(args.log_file),
        "manifest_file": str(args.manifest_file),
        "config": build_config(args),
        "environment": {
            "python_version": sys.version.split()[0],
        },
        "summary": summary,
        "interrupted": interrupted,
    }


def make_summary(
    speaker_index_records: int,
    eligible_speaker_assignment_records: int,
    ignored_records: int,
    invalid_metadata: int,
    planned: int,
    attempted: int,
    succeeded: int,
    failed: int,
    missing_input: int,
    skipped_existing: int,
) -> dict[str, int]:
    """Create manifest summary dictionary."""
    return {
        "speaker_index_records": speaker_index_records,
        "eligible_speaker_assignment_records": eligible_speaker_assignment_records,
        "ignored_records": ignored_records,
        "invalid_metadata": invalid_metadata,
        "planned": planned,
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "missing_input": missing_input,
        "skipped_existing": skipped_existing,
    }


def fmt_int(value: Any) -> str:
    """Format integer-like values for Markdown."""
    if value is None:
        return ""
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def fmt_float(value: Any) -> str:
    """Format floating-point values for Markdown."""
    number = to_float(value)
    if number is None:
        return ""
    return f"{number:,.2f}"


def fmt_percent(value: Any) -> str:
    """Format ratio values as percentages for Markdown."""
    number = to_float(value)
    if number is None:
        return ""
    return f"{number * 100:.2f}%"


def main() -> int:
    """
    Run the batch Jubilee debate speaker diarisation QC workflow and return an exit code.

    Returns:
        0 for clean completion, 1 for item-level failures/missing inputs/invalid
        eligible metadata, 2 for configuration errors, and 130 for keyboard
        interruption.

    I/O:
        Reads NDJSON/JSON inputs, writes per-debate QC files, corpus summaries,
        QC index, manifests, and logs.

    Error behaviour:
        Handles configuration errors, item failures, and keyboard interruptions
        according to the documented exit-code policy.
    """
    args: argparse.Namespace | None = None
    logger: logging.Logger | None = None

    run_id = make_run_id()
    start_time = utc_timestamp()

    manifest_items: list[dict[str, Any]] = []
    qc_results: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    ignored_records: list[dict[str, Any]] = []

    total_records = 0
    eligible_count = 0
    planned_count = 0
    attempted_count = 0

    try:
        args = parse_args()
        validate_args(args)
        logger = setup_logging(args.log_file)

        config = build_config(args)
        initial_summary = make_summary(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        run_metadata = build_run_metadata(args, run_id, start_time, initial_summary, interrupted=False)

        logger.info("Starting %s run_id=%s", TOOL_NAME, run_id)
        logger.info("Speaker index: %s", args.speaker_index)
        logger.info("Alignment directory: %s", args.alignment_dir)
        logger.info("Diarisation directory: %s", args.diarisation_dir)
        logger.info("Speaker transcripts directory: %s", args.speaker_transcripts_dir)
        logger.info("Output directory: %s", args.output_dir)
        logger.info("Test mode: %s; test_limit=%s", args.test_mode, args.test_limit)
        logger.info("Reprocess: %s", args.reprocess)
        logger.info("Start corpus ID: %s", args.start_corpus_id)
        logger.info("QC config: %s", config)

        eligible_records, invalid_records, ignored_records, total_records = load_speaker_assignment_index(
            args.speaker_index
        )
        eligible_count = len(eligible_records) + len(invalid_records)

        logger.info(
            "Loaded speaker-assignment index: records=%s eligible=%s ignored=%s invalid=%s",
            total_records,
            eligible_count,
            len(ignored_records),
            len(invalid_records),
        )

        for invalid_record in invalid_records:
            logger.error(
                "FAILED_METADATA line=%s corpus_id=%s error=%s",
                invalid_record.get("line_number"),
                invalid_record.get("corpus_id"),
                invalid_record.get("error"),
            )

        planned, skipped_existing, missing_input = plan_qc_reports(
            records=eligible_records,
            alignment_dir=args.alignment_dir,
            diarisation_dir=args.diarisation_dir,
            speaker_transcripts_dir=args.speaker_transcripts_dir,
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
            logger.info("SKIPPED_EXISTING %s", item["corpus_id"])
            manifest_items.append(make_skipped_existing_result(item, run_metadata))

        for item in missing_input:
            logger.error("MISSING_INPUT %s", item["corpus_id"])
            manifest_items.append(make_missing_input_result(item, run_metadata))

        for item in planned:
            attempted_count += 1
            item_start = utc_timestamp()
            item_monotonic_start = time.monotonic()
            retries_used = 0
            total_attempts = args.max_retries + 1

            for attempt_number in range(1, total_attempts + 1):
                try:
                    logger.info(
                        "QC attempt %s/%s for %s",
                        attempt_number,
                        total_attempts,
                        item["corpus_id"],
                    )
                    manifest_item, qc_json = process_one_item(item, args, config, run_metadata, logger)
                    manifest_item["retries"] = retries_used
                    manifest_items.append(manifest_item)
                    qc_results.append(qc_json)
                    break
                except Exception as exc:  # noqa: BLE001 - per-item resiliency
                    error = str(exc)
                    logger.error("FAILED attempt %s for %s: %s", attempt_number, item["corpus_id"], error)
                    if attempt_number < total_attempts:
                        retries_used += 1
                        logger.info("Retrying %s after %s seconds", item["corpus_id"], args.retry_delay)
                        if args.retry_delay:
                            time.sleep(args.retry_delay)
                    else:
                        manifest_items.append(
                            make_failed_result(
                                item=item,
                                error=error,
                                retries=retries_used,
                                start_time=item_start,
                                duration_seconds=round(time.monotonic() - item_monotonic_start, 3),
                                run_metadata=run_metadata,
                            )
                        )

        succeeded = sum(1 for item in manifest_items if item.get("status") == "success")
        failed = sum(1 for item in manifest_items if item.get("status") == "failed")
        missing_count = sum(1 for item in manifest_items if item.get("status") == "missing_input")
        skipped_count = sum(1 for item in manifest_items if item.get("status") == "skipped_existing")

        corpus_summary = build_corpus_summary(qc_results, run_metadata)
        summary_json_path = args.output_dir / CORPUS_SUMMARY_JSON_NAME
        summary_md_path = args.output_dir / CORPUS_SUMMARY_MD_NAME
        summary_json_path.write_text(json.dumps(corpus_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary_md_path.write_text(render_corpus_summary_markdown(corpus_summary), encoding="utf-8")
        logger.info("Wrote corpus summary JSON: %s", summary_json_path)
        logger.info("Wrote corpus summary Markdown: %s", summary_md_path)

        qc_index_records = [
            make_qc_index_record(item, run_metadata)
            for item in [*manifest_items, *invalid_records]
        ]
        write_qc_index(qc_index_records, args.qc_index_file)
        logger.info("Wrote QC index: %s", args.qc_index_file)

        summary = make_summary(
            speaker_index_records=total_records,
            eligible_speaker_assignment_records=eligible_count,
            ignored_records=len(ignored_records),
            invalid_metadata=len(invalid_records),
            planned=planned_count,
            attempted=attempted_count,
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
                speaker_index_records=total_records,
                eligible_speaker_assignment_records=eligible_count,
                ignored_records=len(ignored_records),
                invalid_metadata=len(invalid_records),
                planned=planned_count,
                attempted=attempted_count,
                succeeded=sum(1 for item in manifest_items if item.get("status") == "success"),
                failed=sum(1 for item in manifest_items if item.get("status") == "failed"),
                missing_input=sum(1 for item in manifest_items if item.get("status") == "missing_input"),
                skipped_existing=sum(1 for item in manifest_items if item.get("status") == "skipped_existing"),
            )
            manifest = {
                "run_metadata": build_run_metadata(
                    args=args,
                    run_id=run_id,
                    start_time=start_time,
                    end_time=utc_timestamp(),
                    summary=summary,
                    interrupted=True,
                ),
                "items": manifest_items,
                "invalid_records": invalid_records,
                "ignored_records": ignored_records,
            }
            try:
                write_manifests(manifest, args.manifest_file, run_id)
                if manifest_items or invalid_records:
                    write_qc_index(
                        [make_qc_index_record(item, manifest["run_metadata"]) for item in [*manifest_items, *invalid_records]],
                        args.qc_index_file,
                    )
            except Exception as exc:  # noqa: BLE001 - best-effort interrupt handling
                if logger:
                    logger.error("Could not write interrupted manifest/index: %s", exc)

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