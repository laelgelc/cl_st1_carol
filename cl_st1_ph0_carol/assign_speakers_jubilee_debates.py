"""
Assign diarised speaker labels to aligned Jubilee debate transcript words.

This script reads the curated Jubilee debate alignment index and diarisation
index, matches records by corpus_id, and assigns anonymous diarised speaker
labels such as SPEAKER_00 to aligned transcript words using timestamp overlap
or midpoint matching.

Alignment inputs are resolved from the alignment index when possible, or from
the alignment directory as "<corpus_id>.aligned.json" and
"<corpus_id>.words.ndjson". Diarisation inputs are resolved from the diarisation
index when possible, or from the diarisation directory as
"<corpus_id>.diarisation.json" and "<corpus_id>.segments.ndjson".

Outputs are written to the speaker transcript output directory as speaker word
JSON/NDJSON, speaker segment JSON/NDJSON, and a readable plain-text speaker
transcript. Speaker labels are anonymous diarisation labels and are not real
participant identities.

By default, the script runs in test mode and attempts only the first planned
debate. Existing complete speaker-assignment outputs are skipped unless
--reprocess is provided, making the script safe to re-run.

Use --start-corpus-id to resume planning from a specific debate onward.

This programme performs speaker assignment only. Transcription, alignment,
diarisation, real speaker identity resolution, and quality-control reporting are
handled by separate pipeline stages.

Example:
    python assign_speakers_jubilee_debates.py

Full run:
    python assign_speakers_jubilee_debates.py --no-test-mode

Full run from a specific debate:
    python assign_speakers_jubilee_debates.py --no-test-mode --start-corpus-id jubilee_surrounded_003
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOOL_NAME = "assign_speakers_jubilee_debates.py"
TOOL_VERSION = "v1"

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_ALIGNMENT_INDEX_PATH = (
    "corpus/04_jubilee_debates_alignment/"
    "jubilee_debates_alignment_index.ndjson"
)
DEFAULT_DIARISATION_INDEX_PATH = (
    "corpus/05_jubilee_debates_diarisation/"
    "jubilee_debates_diarisation_index.ndjson"
)

DEFAULT_ALIGNMENT_DIR = "corpus/04_jubilee_debates_alignment"
DEFAULT_DIARISATION_DIR = "corpus/05_jubilee_debates_diarisation"
DEFAULT_OUTPUT_DIR = "corpus/06_jubilee_debates_speaker_transcripts"

DEFAULT_LOG_FILE = (
    "corpus/06_jubilee_debates_speaker_transcripts/"
    "assign_speakers_jubilee_debates.log"
)
DEFAULT_MANIFEST_FILE = (
    "corpus/06_jubilee_debates_speaker_transcripts/"
    "assign_speakers_jubilee_debates_manifest.json"
)
DEFAULT_SPEAKER_INDEX_FILE = (
    "corpus/06_jubilee_debates_speaker_transcripts/"
    "jubilee_debates_speaker_assignment_index.ndjson"
)

DEFAULT_ASSIGNMENT_METHOD = "overlap"
DEFAULT_MIN_OVERLAP_RATIO = 0.0
DEFAULT_UNASSIGNED_SPEAKER_LABEL = "UNKNOWN_SPEAKER"

DEFAULT_MERGE_ADJACENT = True
DEFAULT_MAX_MERGE_GAP_SECONDS = 1.0
DEFAULT_MAX_SEGMENT_DURATION_SECONDS = 30.0
DEFAULT_MAX_SEGMENT_WORDS = 120

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 1
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

OUTPUT_SPEAKER_WORDS_JSON_EXTENSION = ".speaker_words.json"
OUTPUT_SPEAKER_WORDS_NDJSON_EXTENSION = ".speaker_words.ndjson"
OUTPUT_SPEAKER_SEGMENTS_JSON_EXTENSION = ".speaker_segments.json"
OUTPUT_SPEAKER_SEGMENTS_NDJSON_EXTENSION = ".speaker_segments.ndjson"
OUTPUT_SPEAKER_TRANSCRIPT_EXTENSION = ".speaker_transcript.txt"

ELIGIBLE_ALIGNMENT_STATUSES = ("success", "skipped_existing")
ELIGIBLE_DIARISATION_STATUSES = ("success", "skipped_existing")
ALLOWED_ASSIGNMENT_METHODS = ("overlap", "midpoint")

METADATA_FIELDS_TO_PRESERVE = (
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
    "transcript_json_file",
    "aligned_json_file",
    "words_ndjson_file",
    "rttm_file",
    "diarisation_json_file",
    "segments_ndjson_file",
    "alignment_status",
    "alignment_run_id",
    "aligned_at_utc",
    "diarisation_status",
    "diarisation_run_id",
    "diarised_at_utc",
    "detected_speaker_count",
    "selected_by",
    "selection_source",
    "notes",
)


class ConfigurationError(Exception):
    """Raised when command-line configuration or required setup is invalid."""


def utc_now() -> datetime:
    """Return the current UTC datetime.

    Performs no I/O and raises no expected exceptions.
    """
    return datetime.now(timezone.utc)


def format_utc(dt: datetime) -> str:
    """Format a datetime as an ISO-8601 UTC timestamp.

    Performs no I/O and raises no expected exceptions.
    """
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_run_id(dt: datetime) -> str:
    """Create a filesystem-safe UTC run identifier.

    Performs no I/O and raises no expected exceptions.
    """
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def resolve_script_relative_path(path: Path) -> Path:
    """Resolve a path against the script directory.

    Parameters:
        path: Path supplied by defaults or command-line arguments.

    Returns:
        Absolute resolved path. Absolute paths are preserved.

    I/O:
        No filesystem reads are performed.

    Error behaviour:
        Raises only standard pathlib-related exceptions in unusual environments.
    """
    if path.is_absolute():
        return path
    return (SCRIPT_DIR / path).resolve()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the speaker-assignment programme.

    Returns:
        argparse.Namespace with resolved path arguments and processing options.

    I/O:
        Reads command-line arguments only.

    Error behaviour:
        argparse exits with status 2 for syntactically invalid arguments.
    """
    parser = argparse.ArgumentParser(
        description="Assign pyannote diarised speaker labels to WhisperX aligned Jubilee debate words."
    )

    parser.add_argument("--alignment-index", default=DEFAULT_ALIGNMENT_INDEX_PATH)
    parser.add_argument("--diarisation-index", default=DEFAULT_DIARISATION_INDEX_PATH)
    parser.add_argument("--alignment-dir", default=DEFAULT_ALIGNMENT_DIR)
    parser.add_argument("--diarisation-dir", default=DEFAULT_DIARISATION_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)

    parser.add_argument(
        "--assignment-method",
        default=DEFAULT_ASSIGNMENT_METHOD,
        choices=ALLOWED_ASSIGNMENT_METHODS,
    )
    parser.add_argument(
        "--min-overlap-ratio",
        type=float,
        default=DEFAULT_MIN_OVERLAP_RATIO,
    )
    parser.add_argument(
        "--unassigned-speaker-label",
        default=DEFAULT_UNASSIGNED_SPEAKER_LABEL,
    )

    merge_group = parser.add_mutually_exclusive_group()
    merge_group.add_argument(
        "--merge-adjacent",
        dest="merge_adjacent",
        action="store_true",
    )
    merge_group.add_argument(
        "--no-merge-adjacent",
        dest="merge_adjacent",
        action="store_false",
    )
    parser.set_defaults(merge_adjacent=DEFAULT_MERGE_ADJACENT)

    parser.add_argument("--max-merge-gap", type=float, default=DEFAULT_MAX_MERGE_GAP_SECONDS)
    parser.add_argument(
        "--max-segment-duration",
        type=float,
        default=DEFAULT_MAX_SEGMENT_DURATION_SECONDS,
    )
    parser.add_argument("--max-segment-words", type=int, default=DEFAULT_MAX_SEGMENT_WORDS)

    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument("--test-mode", dest="test_mode", action="store_true")
    test_group.add_argument("--no-test-mode", dest="test_mode", action="store_false")
    parser.set_defaults(test_mode=DEFAULT_TEST_MODE)

    parser.add_argument("--test-limit", type=int, default=DEFAULT_TEST_LIMIT)
    parser.add_argument("--reprocess", action="store_true", default=False)
    parser.add_argument("--start-corpus-id", default=None)

    parser.add_argument("--log-file", default=DEFAULT_LOG_FILE)
    parser.add_argument("--manifest-file", default=DEFAULT_MANIFEST_FILE)
    parser.add_argument("--speaker-index-file", default=DEFAULT_SPEAKER_INDEX_FILE)

    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--retry-delay", type=float, default=DEFAULT_RETRY_DELAY_SECONDS)

    args = parser.parse_args()

    for attr in (
        "alignment_index",
        "diarisation_index",
        "alignment_dir",
        "diarisation_dir",
        "output_dir",
        "log_file",
        "manifest_file",
        "speaker_index_file",
    ):
        setattr(args, attr, resolve_script_relative_path(Path(getattr(args, attr))))

    if args.start_corpus_id is not None:
        args.start_corpus_id = args.start_corpus_id.strip()

    return args


def setup_logging(log_file: Path) -> logging.Logger:
    """Configure append-only UTF-8 logging.

    Parameters:
        log_file: Log file path.

    Returns:
        Configured logger.

    I/O:
        Creates parent directories if needed and opens the log file in append mode.

    Error behaviour:
        Propagates OSError if the log file cannot be opened.
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
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and filesystem paths.

    Parameters:
        args: Parsed argument namespace.

    Returns:
        None.

    I/O:
        Checks filesystem existence and creates the output directory.

    Error behaviour:
        Raises ConfigurationError for validation failures.
    """
    if args.assignment_method not in ALLOWED_ASSIGNMENT_METHODS:
        raise ConfigurationError(f"Unsupported assignment method: {args.assignment_method}")

    if not 0.0 <= args.min_overlap_ratio <= 1.0:
        raise ConfigurationError("--min-overlap-ratio must be between 0.0 and 1.0")

    if not str(args.unassigned_speaker_label).strip():
        raise ConfigurationError("--unassigned-speaker-label must not be blank")

    if args.max_merge_gap < 0:
        raise ConfigurationError("--max-merge-gap must be greater than or equal to zero")

    if args.max_segment_duration <= 0:
        raise ConfigurationError("--max-segment-duration must be greater than zero")

    if args.max_segment_words <= 0:
        raise ConfigurationError("--max-segment-words must be greater than zero")

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

    if args.start_corpus_id is not None and not args.start_corpus_id:
        raise ConfigurationError("--start-corpus-id was provided but is empty")

    for label, path in (
        ("alignment index", args.alignment_index),
        ("diarisation index", args.diarisation_index),
    ):
        if not path.exists():
            raise ConfigurationError(f"{label} file does not exist: {path}")
        if not path.is_file():
            raise ConfigurationError(f"{label} path is not a file: {path}")

    for label, path in (
        ("alignment directory", args.alignment_dir),
        ("diarisation directory", args.diarisation_dir),
    ):
        if not path.exists():
            raise ConfigurationError(f"{label} does not exist: {path}")
        if not path.is_dir():
            raise ConfigurationError(f"{label} path is not a directory: {path}")

    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        args.speaker_index_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create output/log/manifest directory: {exc}") from exc


def load_ndjson_index(
    index_path: Path,
    status_field: str,
    eligible_statuses: tuple[str, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int]:
    """Load and filter an NDJSON index by status.

    Parameters:
        index_path: NDJSON file path.
        status_field: Name of upstream status field.
        eligible_statuses: Status values that can be processed.

    Returns:
        Tuple of eligible records, invalid eligible records, ignored records, and
        total physical records read.

    I/O:
        Reads the NDJSON file.

    Error behaviour:
        Raises ConfigurationError for unreadable files or invalid JSON lines.
    """
    eligible: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    total = 0

    try:
        with index_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue

                total += 1
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ConfigurationError(
                        f"Invalid JSON in {index_path} at line {line_number}: {exc}"
                    ) from exc

                if not isinstance(record, dict):
                    raise ConfigurationError(
                        f"Invalid NDJSON record in {index_path} at line {line_number}: expected object"
                    )

                status = record.get(status_field)
                if status not in eligible_statuses:
                    ignored.append(
                        {
                            "line_number": line_number,
                            "corpus_id": record.get("corpus_id"),
                            "status": (
                                "ignored_alignment_unavailable"
                                if status_field == "alignment_status"
                                else "ignored_diarisation_unavailable"
                            ),
                            "source_status": status,
                            "record": record,
                        }
                    )
                    continue

                corpus_id = record.get("corpus_id")
                if not isinstance(corpus_id, str) or not corpus_id.strip():
                    invalid.append(
                        {
                            "line_number": line_number,
                            "status": "failed_metadata",
                            "error": "Eligible record missing non-empty corpus_id",
                            "record": record,
                        }
                    )
                    continue

                record = dict(record)
                record["corpus_id"] = corpus_id.strip()
                record["_source_line_number"] = line_number
                eligible.append(record)
    except OSError as exc:
        raise ConfigurationError(f"Could not read NDJSON index {index_path}: {exc}") from exc

    return eligible, invalid, ignored, total


def match_alignment_and_diarisation_records(
    alignment_records: list[dict[str, Any]],
    diarisation_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Match eligible alignment and diarisation records by corpus_id.

    Parameters:
        alignment_records: Eligible alignment records in source order.
        diarisation_records: Eligible diarisation records.

    Returns:
        Matched combined records and unmatched record descriptions.

    I/O:
        None.

    Error behaviour:
        Does not raise for duplicate corpus IDs; the later diarisation record wins.
    """
    diarisation_by_id = {record["corpus_id"]: record for record in diarisation_records}
    alignment_ids = {record["corpus_id"] for record in alignment_records}
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for alignment_record in alignment_records:
        corpus_id = alignment_record["corpus_id"]
        diarisation_record = diarisation_by_id.get(corpus_id)
        if diarisation_record is None:
            unmatched.append(
                {
                    "corpus_id": corpus_id,
                    "status": "unmatched_alignment",
                    "error": "Eligible alignment record has no eligible diarisation record",
                }
            )
            continue

        metadata = {}
        metadata.update(alignment_record)
        metadata.update(diarisation_record)

        matched.append(
            {
                "corpus_id": corpus_id,
                "alignment_record": alignment_record,
                "diarisation_record": diarisation_record,
                "metadata": metadata,
            }
        )

    for diarisation_record in diarisation_records:
        corpus_id = diarisation_record["corpus_id"]
        if corpus_id not in alignment_ids:
            unmatched.append(
                {
                    "corpus_id": corpus_id,
                    "status": "unmatched_diarisation",
                    "error": "Eligible diarisation record has no eligible alignment record",
                }
            )

    return matched, unmatched


def path_from_record_field(record: dict[str, Any], field: str) -> Path | None:
    """Resolve a path stored in an index record field.

    Parameters:
        record: Metadata record.
        field: Field containing a path string.

    Returns:
        Resolved Path, or None if absent/blank.

    I/O:
        No existence checks are performed.

    Error behaviour:
        Non-string values are ignored.
    """
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        return None
    return resolve_script_relative_path(Path(value.strip()))


def resolve_alignment_paths(record: dict[str, Any], alignment_dir: Path) -> dict[str, Path | None]:
    """Resolve aligned JSON and aligned word NDJSON paths.

    Parameters:
        record: Alignment metadata record.
        alignment_dir: Fallback alignment directory.

    Returns:
        Dictionary with aligned_json_path and words_ndjson_path.

    I/O:
        Performs existence checks for preferred paths.

    Error behaviour:
        Does not raise for missing files; missing files are handled in planning.
    """
    corpus_id = record.get("corpus_id")
    preferred_json = path_from_record_field(record, "aligned_json_file")
    preferred_words = path_from_record_field(record, "words_ndjson_file")

    fallback_json = alignment_dir / f"{corpus_id}.aligned.json"
    fallback_words = alignment_dir / f"{corpus_id}.words.ndjson"

    aligned_json_path = preferred_json if preferred_json and preferred_json.is_file() else fallback_json
    words_ndjson_path = preferred_words if preferred_words and preferred_words.is_file() else fallback_words

    return {
        "aligned_json_path": aligned_json_path,
        "words_ndjson_path": words_ndjson_path,
    }


def resolve_diarisation_paths(
    record: dict[str, Any],
    diarisation_dir: Path,
) -> dict[str, Path | None]:
    """Resolve diarisation JSON and diarisation segment NDJSON paths.

    Parameters:
        record: Diarisation metadata record.
        diarisation_dir: Fallback diarisation directory.

    Returns:
        Dictionary with diarisation_json_path and segments_ndjson_path.

    I/O:
        Performs existence checks for preferred paths.

    Error behaviour:
        Does not raise for missing files; missing files are handled in planning.
    """
    corpus_id = record.get("corpus_id")
    preferred_json = path_from_record_field(record, "diarisation_json_file")
    preferred_segments = path_from_record_field(record, "segments_ndjson_file")

    fallback_json = diarisation_dir / f"{corpus_id}.diarisation.json"
    fallback_segments = diarisation_dir / f"{corpus_id}.segments.ndjson"

    diarisation_json_path = (
        preferred_json if preferred_json and preferred_json.is_file() else fallback_json
    )
    segments_ndjson_path = (
        preferred_segments if preferred_segments and preferred_segments.is_file() else fallback_segments
    )

    return {
        "diarisation_json_path": diarisation_json_path,
        "segments_ndjson_path": segments_ndjson_path,
    }


def make_output_paths(corpus_id: str, output_dir: Path) -> dict[str, Path]:
    """Build all per-debate output paths.

    Performs no I/O and raises no expected exceptions.
    """
    return {
        "speaker_words_json_path": output_dir / f"{corpus_id}{OUTPUT_SPEAKER_WORDS_JSON_EXTENSION}",
        "speaker_words_ndjson_path": output_dir / f"{corpus_id}{OUTPUT_SPEAKER_WORDS_NDJSON_EXTENSION}",
        "speaker_segments_json_path": output_dir / f"{corpus_id}{OUTPUT_SPEAKER_SEGMENTS_JSON_EXTENSION}",
        "speaker_segments_ndjson_path": output_dir / f"{corpus_id}{OUTPUT_SPEAKER_SEGMENTS_NDJSON_EXTENSION}",
        "speaker_transcript_text_path": output_dir / f"{corpus_id}{OUTPUT_SPEAKER_TRANSCRIPT_EXTENSION}",
    }


def outputs_complete(output_paths: dict[str, Path]) -> bool:
    """Return True if all required output files already exist.

    Performs filesystem existence checks only.
    """
    return all(path.is_file() for path in output_paths.values())


def plan_speaker_assignments(
    matched_records: list[dict[str, Any]],
    alignment_dir: Path,
    diarisation_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_corpus_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Create planned, skipped, and missing-input speaker-assignment records.

    Parameters:
        matched_records: Matched alignment/diarisation records.
        alignment_dir: Alignment fallback directory.
        diarisation_dir: Diarisation fallback directory.
        output_dir: Destination directory.
        test_mode: Whether to limit attempted work.
        test_limit: Maximum planned assignments in test mode.
        reprocess: Whether to overwrite existing outputs.
        start_corpus_id: Optional corpus_id at which planning starts.

    Returns:
        Tuple of planned records, skipped-existing records, and missing-input records.

    I/O:
        Checks filesystem existence of input and output files.

    Error behaviour:
        Raises ConfigurationError if start_corpus_id is not found.
    """
    records = matched_records

    if start_corpus_id:
        start_index = next(
            (idx for idx, record in enumerate(records) if record["corpus_id"] == start_corpus_id),
            None,
        )
        if start_index is None:
            raise ConfigurationError(
                f"--start-corpus-id not found among eligible matched records: {start_corpus_id}"
            )
        records = records[start_index:]

    planned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for record in records:
        corpus_id = record["corpus_id"]
        alignment_paths = resolve_alignment_paths(record["alignment_record"], alignment_dir)
        diarisation_paths = resolve_diarisation_paths(record["diarisation_record"], diarisation_dir)
        output_paths = make_output_paths(corpus_id, output_dir)

        item = {
            **record,
            **alignment_paths,
            **diarisation_paths,
            **output_paths,
        }

        missing_paths = []
        if not (
            item["words_ndjson_path"]
            and item["words_ndjson_path"].is_file()
            or item["aligned_json_path"]
            and item["aligned_json_path"].is_file()
        ):
            missing_paths.append("aligned words NDJSON or aligned JSON")

        if not (
            item["segments_ndjson_path"]
            and item["segments_ndjson_path"].is_file()
            or item["diarisation_json_path"]
            and item["diarisation_json_path"].is_file()
        ):
            missing_paths.append("diarisation segments NDJSON or diarisation JSON")

        if missing_paths:
            item["status"] = "missing_input"
            item["error"] = "Missing required input: " + "; ".join(missing_paths)
            missing.append(item)
            continue

        if not reprocess and outputs_complete(output_paths):
            item["status"] = "skipped_existing"
            item["error"] = None
            skipped.append(item)
            continue

        planned.append(item)

    if test_mode:
        planned = planned[:test_limit]

    return planned, skipped, missing


def read_json_file(path: Path) -> Any:
    """Read a UTF-8 JSON file.

    I/O:
        Reads a JSON file.

    Error behaviour:
        Propagates OSError and json.JSONDecodeError.
    """
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_ndjson_file(path: Path) -> list[dict[str, Any]]:
    """Read a UTF-8 NDJSON file as a list of objects.

    I/O:
        Reads an NDJSON file.

    Error behaviour:
        Raises ValueError if a non-object line is encountered.
    """
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"{path} line {line_number} is not a JSON object")
            records.append(value)
    return records


def extract_words_from_aligned_json(data: Any) -> list[dict[str, Any]]:
    """Extract aligned word objects from common WhisperX JSON structures.

    Performs no I/O. Returns an empty list if no known structure is found.
    """
    if isinstance(data, dict):
        if isinstance(data.get("words"), list):
            return [item for item in data["words"] if isinstance(item, dict)]

        segments = data.get("segments")
        if isinstance(segments, list):
            words = []
            for segment_index, segment in enumerate(segments, start=1):
                if not isinstance(segment, dict):
                    continue
                for word_index, word in enumerate(segment.get("words") or [], start=1):
                    if isinstance(word, dict):
                        merged = dict(word)
                        merged.setdefault("segment_id", segment.get("segment_id", segment.get("id", segment_index)))
                        merged.setdefault("word_index", len(words) + 1)
                        words.append(merged)
            return words

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    return []


def extract_segments_from_diarisation_json(data: Any) -> list[dict[str, Any]]:
    """Extract diarisation segments from common JSON structures.

    Performs no I/O. Returns an empty list if no known structure is found.
    """
    if isinstance(data, dict):
        for key in ("segments", "diarisation_segments", "speaker_segments"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    return []


def load_aligned_words(
    words_ndjson_path: Path | None,
    aligned_json_path: Path | None,
) -> list[dict[str, Any]]:
    """Load aligned word records from NDJSON or aligned JSON fallback.

    Parameters:
        words_ndjson_path: Preferred word-level NDJSON path.
        aligned_json_path: Fallback aligned JSON path.

    Returns:
        List of aligned word dictionaries.

    I/O:
        Reads one input file.

    Error behaviour:
        Raises FileNotFoundError, JSONDecodeError, ValueError, or OSError for
        unusable input files.
    """
    if words_ndjson_path and words_ndjson_path.is_file():
        return read_ndjson_file(words_ndjson_path)

    if aligned_json_path and aligned_json_path.is_file():
        return extract_words_from_aligned_json(read_json_file(aligned_json_path))

    raise FileNotFoundError("No aligned word NDJSON or aligned JSON file is available")


def load_diarisation_segments(
    segments_ndjson_path: Path | None,
    diarisation_json_path: Path | None,
) -> list[dict[str, Any]]:
    """Load diarised speaker intervals from NDJSON or JSON fallback.

    Parameters:
        segments_ndjson_path: Preferred segment NDJSON path.
        diarisation_json_path: Fallback diarisation JSON path.

    Returns:
        List of diarisation segment dictionaries.

    I/O:
        Reads one input file.

    Error behaviour:
        Raises FileNotFoundError, JSONDecodeError, ValueError, or OSError for
        unusable input files.
    """
    if segments_ndjson_path and segments_ndjson_path.is_file():
        return read_ndjson_file(segments_ndjson_path)

    if diarisation_json_path and diarisation_json_path.is_file():
        return extract_segments_from_diarisation_json(read_json_file(diarisation_json_path))

    raise FileNotFoundError("No diarisation segment NDJSON or diarisation JSON file is available")


def as_float(value: Any) -> float | None:
    """Convert a value to float, returning None for missing/invalid values."""
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def valid_interval(record: dict[str, Any]) -> tuple[float, float] | None:
    """Return a valid positive time interval from a record, or None."""
    start = as_float(record.get("start"))
    end = as_float(record.get("end"))
    if start is None or end is None or end <= start:
        return None
    return start, end


def assign_speakers_to_words(
    words: list[dict[str, Any]],
    diarisation_segments: list[dict[str, Any]],
    assignment_method: str,
    min_overlap_ratio: float,
    unassigned_speaker_label: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Assign diarised speaker labels to aligned words.

    Parameters:
        words: Aligned words with start/end times when available.
        diarisation_segments: Diarised intervals with speaker/start/end fields.
        assignment_method: "overlap" or "midpoint".
        min_overlap_ratio: Minimum accepted overlap ratio for overlap mode.
        unassigned_speaker_label: Label for unassigned words.

    Returns:
        Tuple of speaker-assigned word records and summary statistics.

    I/O:
        None.

    Error behaviour:
        Raises ValueError for unsupported assignment_method.
    """
    if assignment_method not in ALLOWED_ASSIGNMENT_METHODS:
        raise ValueError(f"Unsupported assignment method: {assignment_method}")

    usable_segments = []
    for index, segment in enumerate(diarisation_segments):
        interval = valid_interval(segment)
        speaker = segment.get("speaker")
        if interval and isinstance(speaker, str) and speaker.strip():
            start, end = interval
            usable_segments.append(
                {
                    "index": index,
                    "speaker": speaker.strip(),
                    "start": start,
                    "end": end,
                    "duration": end - start,
                }
            )

    speaker_words: list[dict[str, Any]] = []
    assigned_count = 0
    unassigned_count = 0
    missing_timing_count = 0
    multiple_candidate_count = 0

    for fallback_index, word in enumerate(words, start=1):
        output = dict(word)
        output.setdefault("word_index", fallback_index)
        interval = valid_interval(output)

        if interval is None:
            output.update(
                {
                    "speaker": unassigned_speaker_label,
                    "assignment_status": "unassigned_missing_word_timing",
                    "assignment_method": assignment_method,
                    "speaker_overlap_seconds": None,
                    "speaker_overlap_ratio": None,
                    "speaker_candidate_count": 0,
                    "speaker_candidates": [],
                }
            )
            unassigned_count += 1
            missing_timing_count += 1
            speaker_words.append(output)
            continue

        word_start, word_end = interval
        word_duration = word_end - word_start

        if assignment_method == "overlap":
            candidates = []
            for segment in usable_segments:
                overlap = max(0.0, min(word_end, segment["end"]) - max(word_start, segment["start"]))
                if overlap > 0:
                    candidates.append(
                        {
                            "speaker": segment["speaker"],
                            "overlap_seconds": overlap,
                            "overlap_ratio": overlap / word_duration if word_duration > 0 else 0.0,
                            "segment_start": segment["start"],
                            "segment_end": segment["end"],
                            "_input_index": segment["index"],
                        }
                    )

            candidates.sort(
                key=lambda item: (
                    -item["overlap_seconds"],
                    item["segment_start"],
                    item["_input_index"],
                )
            )

            if candidates and candidates[0]["overlap_ratio"] >= min_overlap_ratio:
                best = candidates[0]
                output.update(
                    {
                        "speaker": best["speaker"],
                        "assignment_status": "assigned",
                        "assignment_method": assignment_method,
                        "speaker_overlap_seconds": round(best["overlap_seconds"], 6),
                        "speaker_overlap_ratio": round(best["overlap_ratio"], 6),
                        "speaker_candidate_count": len(candidates),
                        "speaker_candidates": [
                            {
                                "speaker": candidate["speaker"],
                                "overlap_seconds": round(candidate["overlap_seconds"], 6),
                                "overlap_ratio": round(candidate["overlap_ratio"], 6),
                            }
                            for candidate in candidates[:5]
                        ],
                    }
                )
                assigned_count += 1
                if len(candidates) > 1:
                    multiple_candidate_count += 1
            else:
                status = "unassigned_no_overlap" if not candidates else "unassigned_below_min_overlap"
                output.update(
                    {
                        "speaker": unassigned_speaker_label,
                        "assignment_status": status,
                        "assignment_method": assignment_method,
                        "speaker_overlap_seconds": 0.0,
                        "speaker_overlap_ratio": 0.0,
                        "speaker_candidate_count": len(candidates),
                        "speaker_candidates": [],
                    }
                )
                unassigned_count += 1

        else:
            midpoint = (word_start + word_end) / 2.0
            candidates = [
                segment
                for segment in usable_segments
                if segment["start"] <= midpoint <= segment["end"]
            ]
            candidates.sort(key=lambda item: (item["duration"], item["start"], item["index"]))

            if candidates:
                best = candidates[0]
                output.update(
                    {
                        "speaker": best["speaker"],
                        "assignment_status": "assigned",
                        "assignment_method": assignment_method,
                        "speaker_overlap_seconds": None,
                        "speaker_overlap_ratio": None,
                        "speaker_candidate_count": len(candidates),
                        "speaker_candidates": [
                            {
                                "speaker": candidate["speaker"],
                                "segment_start": candidate["start"],
                                "segment_end": candidate["end"],
                            }
                            for candidate in candidates[:5]
                        ],
                    }
                )
                assigned_count += 1
                if len(candidates) > 1:
                    multiple_candidate_count += 1
            else:
                output.update(
                    {
                        "speaker": unassigned_speaker_label,
                        "assignment_status": "unassigned_no_midpoint_match",
                        "assignment_method": assignment_method,
                        "speaker_overlap_seconds": None,
                        "speaker_overlap_ratio": None,
                        "speaker_candidate_count": 0,
                        "speaker_candidates": [],
                    }
                )
                unassigned_count += 1

        speaker_words.append(output)

    assigned_speakers = {
        word.get("speaker")
        for word in speaker_words
        if word.get("assignment_status") == "assigned" and word.get("speaker") != unassigned_speaker_label
    }

    summary = {
        "word_count": len(words),
        "assigned_word_count": assigned_count,
        "unassigned_word_count": unassigned_count,
        "unknown_speaker_word_count": sum(
            1 for word in speaker_words if word.get("speaker") == unassigned_speaker_label
        ),
        "words_missing_timing_count": missing_timing_count,
        "multiple_speaker_candidate_word_count": multiple_candidate_count,
        "assigned_speaker_count": len(assigned_speakers),
        "assigned_speakers": sorted(assigned_speakers),
        "usable_diarisation_segment_count": len(usable_segments),
    }

    return speaker_words, summary


def clean_join_words(tokens: list[str]) -> str:
    """Join word tokens conservatively with light punctuation cleanup."""
    text = " ".join(token.strip() for token in tokens if token is not None and str(token).strip())
    text = re.sub(r"\s+([,.;:?!%])", r"\1", text)
    text = re.sub(r"([(\[{])\s+", r"\1", text)
    text = re.sub(r"\s+([)\]}])", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_speaker_segments(
    speaker_words: list[dict[str, Any]],
    merge_adjacent: bool,
    max_merge_gap: float,
    max_segment_duration: float,
    max_segment_words: int,
) -> list[dict[str, Any]]:
    """Group speaker-assigned words into readable transcript segments.

    Parameters:
        speaker_words: Speaker-assigned word records.
        merge_adjacent: Whether to merge compatible adjacent words.
        max_merge_gap: Maximum allowed inter-word gap.
        max_segment_duration: Maximum duration before forced break.
        max_segment_words: Maximum words before forced break.

    Returns:
        List of speaker transcript segment records.

    I/O:
        None.

    Error behaviour:
        Does not raise for individual missing-timing words; they are omitted from
        grouped timed transcript segments.
    """
    timed_words = []
    for source_index, word in enumerate(speaker_words, start=1):
        interval = valid_interval(word)
        if interval is None:
            continue
        start, end = interval
        timed_word = dict(word)
        timed_word["_source_index"] = source_index
        timed_word["_start"] = start
        timed_word["_end"] = end
        timed_words.append(timed_word)

    segments: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        if not current:
            return
        start = current[0]["_start"]
        end = current[-1]["_end"]
        speaker = current[0].get("speaker")
        statuses = {word.get("assignment_status") for word in current}
        segment = {
            "corpus_id": current[0].get("corpus_id"),
            "speaker_segment_index": len(segments) + 1,
            "speaker": speaker,
            "start": start,
            "end": end,
            "duration": round(end - start, 6),
            "word_count": len(current),
            "text": clean_join_words([str(word.get("word", "")) for word in current]),
            "source_word_start_index": current[0].get("word_index", current[0]["_source_index"]),
            "source_word_end_index": current[-1].get("word_index", current[-1]["_source_index"]),
            "assignment_status": (
                "assigned"
                if statuses == {"assigned"}
                else "mixed" if len(statuses) > 1 else next(iter(statuses), None)
            ),
        }
        segments.append(segment)
        current.clear()

    for word in timed_words:
        if not current:
            current.append(word)
            continue

        previous = current[-1]
        same_speaker = word.get("speaker") == previous.get("speaker")
        gap = word["_start"] - previous["_end"]
        would_duration = word["_end"] - current[0]["_start"]
        would_word_count = len(current) + 1

        should_break = (
            not merge_adjacent
            or not same_speaker
            or gap > max_merge_gap
            or would_duration > max_segment_duration
            or would_word_count > max_segment_words
        )

        if should_break:
            flush()

        current.append(word)

    flush()
    return segments


def format_seconds(seconds: float | None) -> str:
    """Format seconds as HH:MM:SS.mmm for transcript output."""
    if seconds is None:
        return "00:00:00.000"
    milliseconds_total = int(round(float(seconds) * 1000))
    milliseconds = milliseconds_total % 1000
    total_seconds = milliseconds_total // 1000
    sec = total_seconds % 60
    minutes_total = total_seconds // 60
    minute = minutes_total % 60
    hour = minutes_total // 60
    return f"{hour:02d}:{minute:02d}:{sec:02d}.{milliseconds:03d}"


def build_transcript_text(corpus_id: str, metadata: dict[str, Any], segments: list[dict[str, Any]]) -> str:
    """Build readable plain-text speaker transcript content."""
    title = metadata.get("title_selected") or metadata.get("title") or metadata.get("title_extracted")

    lines = [
        f"# {corpus_id}",
    ]

    if title:
        lines.append(f"# {title}")

    lines.extend(
        [
            "# Speaker labels are anonymous diarisation labels, not real participant identities.",
            "",
        ]
    )

    for segment in segments:
        lines.append(
            f"[{segment.get('speaker')} "
            f"{format_seconds(as_float(segment.get('start')))}-"
            f"{format_seconds(as_float(segment.get('end')))}]"
        )
        lines.append(str(segment.get("text", "")).strip())
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def json_ready_path(path: Path | None) -> str | None:
    """Convert a Path into a string suitable for JSON output."""
    if path is None:
        return None
    return str(path)


def selected_metadata(record: dict[str, Any]) -> dict[str, Any]:
    """Return selected metadata fields from a source record."""
    return {field: record.get(field) for field in METADATA_FIELDS_TO_PRESERVE if field in record}


def write_ndjson(records: list[dict[str, Any]], path: Path) -> None:
    """Write a list of JSON objects to an NDJSON file.

    I/O:
        Creates parent directories and writes the file.

    Error behaviour:
        Propagates OSError and TypeError from JSON serialization.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=False) + "\n")


def write_json(data: dict[str, Any], path: Path) -> None:
    """Write a JSON object with UTF-8 encoding."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_speaker_assignment_outputs(
    speaker_words_json: dict[str, Any],
    speaker_words: list[dict[str, Any]],
    speaker_segments_json: dict[str, Any],
    speaker_segments: list[dict[str, Any]],
    transcript_text: str,
    output_paths: dict[str, Path],
) -> None:
    """Write speaker word, segment, and plain-text transcript outputs.

    Parameters:
        speaker_words_json: Full speaker words JSON payload.
        speaker_words: Word-level NDJSON records.
        speaker_segments_json: Full speaker segments JSON payload.
        speaker_segments: Segment-level NDJSON records.
        transcript_text: Plain-text transcript.
        output_paths: Destination paths.

    Returns:
        None.

    I/O:
        Writes five output files.

    Error behaviour:
        Propagates OSError and JSON serialization errors.
    """
    write_json(speaker_words_json, output_paths["speaker_words_json_path"])
    write_ndjson(speaker_words, output_paths["speaker_words_ndjson_path"])
    write_json(speaker_segments_json, output_paths["speaker_segments_json_path"])
    write_ndjson(speaker_segments, output_paths["speaker_segments_ndjson_path"])

    output_paths["speaker_transcript_text_path"].parent.mkdir(parents=True, exist_ok=True)
    output_paths["speaker_transcript_text_path"].write_text(transcript_text, encoding="utf-8")


def write_speaker_assignment_index(
    index_records: list[dict[str, Any]],
    speaker_index_file: Path,
) -> None:
    """Write curated NDJSON speaker-assignment index.

    Parameters:
        index_records: Records for processed, skipped, missing, failed, and invalid items.
        speaker_index_file: Destination NDJSON path.

    I/O:
        Writes the speaker-assignment index.

    Error behaviour:
        Propagates OSError and JSON serialization errors.
    """
    write_ndjson(index_records, speaker_index_file)


def write_manifests(
    manifest: dict[str, Any],
    manifest_file: Path,
    run_id: str,
) -> tuple[Path, Path]:
    """Write latest and timestamped manifest files.

    Parameters:
        manifest: JSON manifest object.
        manifest_file: Latest manifest path.
        run_id: Run identifier used in timestamped manifest filename.

    Returns:
        Tuple of latest manifest path and timestamped manifest path.

    I/O:
        Writes two JSON files.

    Error behaviour:
        Propagates OSError and JSON serialization errors.
    """
    latest_path = manifest_file
    timestamped_path = manifest_file.with_name(
        f"{manifest_file.stem}_{run_id}{manifest_file.suffix}"
    )

    write_json(manifest, latest_path)
    write_json(manifest, timestamped_path)

    return latest_path, timestamped_path


def process_one_item(
    item: dict[str, Any],
    args: argparse.Namespace,
    run_id: str,
    assigned_at_utc: str,
    logger: logging.Logger,
) -> dict[str, Any]:
    """Process one planned speaker-assignment item.

    Performs file reads and writes. Raises exceptions to caller for retry handling.
    """
    corpus_id = item["corpus_id"]
    logger.info("Attempting speaker assignment: %s", corpus_id)

    words = load_aligned_words(item["words_ndjson_path"], item["aligned_json_path"])
    diarisation_segments = load_diarisation_segments(
        item["segments_ndjson_path"],
        item["diarisation_json_path"],
    )

    if not words:
        raise ValueError("No usable aligned words found")
    if not diarisation_segments:
        raise ValueError("No usable diarisation segments found")

    for word in words:
        word.setdefault("corpus_id", corpus_id)

    speaker_words, assignment_summary = assign_speakers_to_words(
        words=words,
        diarisation_segments=diarisation_segments,
        assignment_method=args.assignment_method,
        min_overlap_ratio=args.min_overlap_ratio,
        unassigned_speaker_label=args.unassigned_speaker_label,
    )

    speaker_segments = build_speaker_segments(
        speaker_words=speaker_words,
        merge_adjacent=args.merge_adjacent,
        max_merge_gap=args.max_merge_gap,
        max_segment_duration=args.max_segment_duration,
        max_segment_words=args.max_segment_words,
    )

    metadata = selected_metadata(item["metadata"])
    speaker_count = len(
        {
            segment.get("speaker")
            for segment in diarisation_segments
            if isinstance(segment.get("speaker"), str) and segment.get("speaker").strip()
        }
    )

    output_paths = {
        "speaker_words_json_path": item["speaker_words_json_path"],
        "speaker_words_ndjson_path": item["speaker_words_ndjson_path"],
        "speaker_segments_json_path": item["speaker_segments_json_path"],
        "speaker_segments_ndjson_path": item["speaker_segments_ndjson_path"],
        "speaker_transcript_text_path": item["speaker_transcript_text_path"],
    }

    speaker_words_json = {
        "corpus_id": corpus_id,
        "input_alignment_paths": {
            "aligned_json_path": json_ready_path(item["aligned_json_path"]),
            "words_ndjson_path": json_ready_path(item["words_ndjson_path"]),
        },
        "input_diarisation_paths": {
            "diarisation_json_path": json_ready_path(item["diarisation_json_path"]),
            "segments_ndjson_path": json_ready_path(item["segments_ndjson_path"]),
        },
        "speaker_assignment": {
            "assignment_method": args.assignment_method,
            "min_overlap_ratio": args.min_overlap_ratio,
            "unassigned_speaker_label": args.unassigned_speaker_label,
            "word_count": assignment_summary["word_count"],
            "assigned_word_count": assignment_summary["assigned_word_count"],
            "unassigned_word_count": assignment_summary["unassigned_word_count"],
            "unknown_speaker_word_count": assignment_summary["unknown_speaker_word_count"],
            "speaker_count": assignment_summary["assigned_speaker_count"],
            "words_missing_timing_count": assignment_summary["words_missing_timing_count"],
            "multiple_speaker_candidate_word_count": assignment_summary[
                "multiple_speaker_candidate_word_count"
            ],
            "words": speaker_words,
        },
        "metadata": metadata,
        "run": {
            "speaker_assignment_run_id": run_id,
            "assigned_at_utc": assigned_at_utc,
        },
        "status": "success",
        "error": None,
    }

    speaker_segments_json = {
        "corpus_id": corpus_id,
        "speaker_segments": {
            "segment_count": len(speaker_segments),
            "speaker_count": len(
                {
                    segment.get("speaker")
                    for segment in speaker_segments
                    if segment.get("speaker") != args.unassigned_speaker_label
                }
            ),
            "segments": speaker_segments,
        },
        "metadata": metadata,
        "run": {
            "speaker_assignment_run_id": run_id,
            "assigned_at_utc": assigned_at_utc,
        },
        "status": "success",
        "error": None,
    }

    transcript_text = build_transcript_text(corpus_id, metadata, speaker_segments)

    write_speaker_assignment_outputs(
        speaker_words_json=speaker_words_json,
        speaker_words=speaker_words,
        speaker_segments_json=speaker_segments_json,
        speaker_segments=speaker_segments,
        transcript_text=transcript_text,
        output_paths=output_paths,
    )

    result = {
        "corpus_id": corpus_id,
        "status": "success",
        "error": None,
        "word_count": assignment_summary["word_count"],
        "assigned_word_count": assignment_summary["assigned_word_count"],
        "unassigned_word_count": assignment_summary["unassigned_word_count"],
        "unknown_speaker_word_count": assignment_summary["unknown_speaker_word_count"],
        "speaker_segment_count": len(speaker_segments),
        "detected_speaker_count": item["metadata"].get("detected_speaker_count", speaker_count),
        "assigned_speaker_count": assignment_summary["assigned_speaker_count"],
        "metadata": metadata,
    }

    logger.info(
        "SUCCESS %s words=%s assigned=%s unassigned=%s segments=%s",
        corpus_id,
        result["word_count"],
        result["assigned_word_count"],
        result["unassigned_word_count"],
        result["speaker_segment_count"],
    )

    return result


def item_manifest_base(item: dict[str, Any]) -> dict[str, Any]:
    """Build common manifest path fields for an item."""
    return {
        "corpus_id": item.get("corpus_id"),
        "input_aligned_json_path": json_ready_path(item.get("aligned_json_path")),
        "input_words_ndjson_path": json_ready_path(item.get("words_ndjson_path")),
        "input_diarisation_json_path": json_ready_path(item.get("diarisation_json_path")),
        "input_diarisation_segments_path": json_ready_path(item.get("segments_ndjson_path")),
        "speaker_words_json_path": json_ready_path(item.get("speaker_words_json_path")),
        "speaker_words_ndjson_path": json_ready_path(item.get("speaker_words_ndjson_path")),
        "speaker_segments_json_path": json_ready_path(item.get("speaker_segments_json_path")),
        "speaker_segments_ndjson_path": json_ready_path(item.get("speaker_segments_ndjson_path")),
        "speaker_transcript_text_path": json_ready_path(item.get("speaker_transcript_text_path")),
    }


def index_record_from_item(
    item: dict[str, Any],
    run_id: str,
    assigned_at_utc: str,
    status: str,
    args: argparse.Namespace,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build one speaker-assignment index record."""
    metadata = selected_metadata(item.get("metadata", {}))
    result = result or {}

    record = {
        **metadata,
        "corpus_id": item.get("corpus_id"),
        "aligned_json_file": json_ready_path(item.get("aligned_json_path")),
        "words_ndjson_file": json_ready_path(item.get("words_ndjson_path")),
        "diarisation_json_file": json_ready_path(item.get("diarisation_json_path")),
        "segments_ndjson_file": json_ready_path(item.get("segments_ndjson_path")),
        "speaker_words_json_file": json_ready_path(item.get("speaker_words_json_path")),
        "speaker_words_ndjson_file": json_ready_path(item.get("speaker_words_ndjson_path")),
        "speaker_segments_json_file": json_ready_path(item.get("speaker_segments_json_path")),
        "speaker_segments_ndjson_file": json_ready_path(item.get("speaker_segments_ndjson_path")),
        "speaker_transcript_text_file": json_ready_path(item.get("speaker_transcript_text_path")),
        "speaker_assignment_status": status,
        "speaker_assignment_run_id": run_id,
        "assigned_at_utc": assigned_at_utc,
        "assignment_method": args.assignment_method,
        "min_overlap_ratio": args.min_overlap_ratio,
        "word_count": result.get("word_count"),
        "assigned_word_count": result.get("assigned_word_count"),
        "unassigned_word_count": result.get("unassigned_word_count"),
        "speaker_segment_count": result.get("speaker_segment_count"),
        "detected_speaker_count": result.get(
            "detected_speaker_count",
            item.get("metadata", {}).get("detected_speaker_count"),
        ),
        "assigned_speaker_count": result.get("assigned_speaker_count"),
        "unknown_speaker_word_count": result.get("unknown_speaker_word_count"),
        "alignment_status": item.get("metadata", {}).get("alignment_status"),
        "alignment_run_id": item.get("metadata", {}).get("alignment_run_id"),
        "diarisation_status": item.get("metadata", {}).get("diarisation_status"),
        "diarisation_run_id": item.get("metadata", {}).get("diarisation_run_id"),
        "selected_by": item.get("metadata", {}).get("selected_by"),
        "selection_source": item.get("metadata", {}).get("selection_source"),
        "notes": item.get("metadata", {}).get("notes"),
        "error": error,
    }

    return record


def build_manifest(
    args: argparse.Namespace,
    run_id: str,
    start_time: str,
    end_time: str,
    items: list[dict[str, Any]],
    invalid_records: list[dict[str, Any]],
    ignored_records: list[dict[str, Any]],
    summary: dict[str, Any],
    interrupted: bool,
) -> dict[str, Any]:
    """Build the run manifest object.

    Performs no I/O and raises no expected exceptions.
    """
    return {
        "run_metadata": {
            "run_id": run_id,
            "tool_name": TOOL_NAME,
            "tool_version": TOOL_VERSION,
            "start_time": start_time,
            "end_time": end_time,
            "test_mode": args.test_mode,
            "test_limit": args.test_limit,
            "reprocess": args.reprocess,
            "workers": args.workers,
            "alignment_index_path": str(args.alignment_index),
            "diarisation_index_path": str(args.diarisation_index),
            "alignment_dir": str(args.alignment_dir),
            "diarisation_dir": str(args.diarisation_dir),
            "output_dir": str(args.output_dir),
            "speaker_index_file": str(args.speaker_index_file),
            "log_file": str(args.log_file),
            "manifest_file": str(args.manifest_file),
            "config": {
                "assignment_method": args.assignment_method,
                "min_overlap_ratio": args.min_overlap_ratio,
                "unassigned_speaker_label": args.unassigned_speaker_label,
                "merge_adjacent": args.merge_adjacent,
                "max_merge_gap": args.max_merge_gap,
                "max_segment_duration": args.max_segment_duration,
                "max_segment_words": args.max_segment_words,
                "timeout_seconds": args.timeout,
                "max_retries": args.max_retries,
                "retry_delay_seconds": args.retry_delay,
                "start_corpus_id": args.start_corpus_id,
            },
            "environment": {
                "python_version": platform.python_version(),
                "platform": platform.platform(),
            },
            "summary": summary,
            "interrupted": interrupted,
        },
        "items": items,
        "invalid_records": invalid_records,
        "ignored_records": ignored_records,
    }


def main() -> int:
    """Run the batch Jubilee debate speaker-assignment workflow.

    Returns:
        Process exit code:
        0 for clean completion, 1 for item-level errors, 2 for configuration
        errors, and 130 for keyboard interruption.

    I/O:
        Reads indices and source JSON/NDJSON files; writes speaker outputs,
        speaker-assignment index, logs, and manifests.

    Error behaviour:
        Catches configuration errors and keyboard interruption. Per-item
        processing errors are recorded and do not stop the full run.
    """
    logger: logging.Logger | None = None

    try:
        args = parse_args()
        validate_args(args)
        logger = setup_logging(args.log_file)

        start_dt = utc_now()
        start_time = format_utc(start_dt)
        run_id = make_run_id(start_dt)
        assigned_at_utc = start_time

        logger.info("Starting %s run_id=%s", TOOL_NAME, run_id)
        logger.info("Alignment index: %s", args.alignment_index)
        logger.info("Diarisation index: %s", args.diarisation_index)
        logger.info("Alignment directory: %s", args.alignment_dir)
        logger.info("Diarisation directory: %s", args.diarisation_dir)
        logger.info("Output directory: %s", args.output_dir)
        logger.info(
            "Configuration: test_mode=%s test_limit=%s reprocess=%s start_corpus_id=%s "
            "assignment_method=%s min_overlap_ratio=%s merge_adjacent=%s",
            args.test_mode,
            args.test_limit,
            args.reprocess,
            args.start_corpus_id,
            args.assignment_method,
            args.min_overlap_ratio,
            args.merge_adjacent,
        )

        alignment_records, invalid_alignment, ignored_alignment, alignment_total = load_ndjson_index(
            args.alignment_index,
            "alignment_status",
            ELIGIBLE_ALIGNMENT_STATUSES,
        )
        diarisation_records, invalid_diarisation, ignored_diarisation, diarisation_total = (
            load_ndjson_index(
                args.diarisation_index,
                "diarisation_status",
                ELIGIBLE_DIARISATION_STATUSES,
            )
        )

        matched_records, unmatched_records = match_alignment_and_diarisation_records(
            alignment_records,
            diarisation_records,
        )

        invalid_records = invalid_alignment + invalid_diarisation
        ignored_records = ignored_alignment + ignored_diarisation + unmatched_records

        if not matched_records:
            raise ConfigurationError("No eligible matched alignment/diarisation records were found")

        planned, skipped, missing = plan_speaker_assignments(
            matched_records=matched_records,
            alignment_dir=args.alignment_dir,
            diarisation_dir=args.diarisation_dir,
            output_dir=args.output_dir,
            test_mode=args.test_mode,
            test_limit=args.test_limit,
            reprocess=args.reprocess,
            start_corpus_id=args.start_corpus_id,
        )

        logger.info(
            "Loaded records: alignment_total=%s eligible_alignment=%s diarisation_total=%s "
            "eligible_diarisation=%s matched=%s ignored=%s invalid=%s planned=%s "
            "skipped_existing=%s missing_input=%s",
            alignment_total,
            len(alignment_records),
            diarisation_total,
            len(diarisation_records),
            len(matched_records),
            len(ignored_records),
            len(invalid_records),
            len(planned),
            len(skipped),
            len(missing),
        )

        manifest_items: list[dict[str, Any]] = []
        index_records: list[dict[str, Any]] = []

        for item in skipped:
            logger.info("SKIPPED existing speaker assignment: %s", item["corpus_id"])
            manifest_items.append(
                {
                    **item_manifest_base(item),
                    "status": "skipped_existing",
                    "error": None,
                    "retries": 0,
                    "duration_seconds": 0.0,
                    "start_time": None,
                    "end_time": None,
                    "metadata": selected_metadata(item.get("metadata", {})),
                }
            )
            index_records.append(
                index_record_from_item(
                    item,
                    run_id,
                    assigned_at_utc,
                    "skipped_existing",
                    args,
                    error=None,
                )
            )

        for item in missing:
            logger.error("MISSING INPUT %s: %s", item["corpus_id"], item["error"])
            manifest_items.append(
                {
                    **item_manifest_base(item),
                    "status": "missing_input",
                    "error": item["error"],
                    "retries": 0,
                    "duration_seconds": 0.0,
                    "start_time": None,
                    "end_time": None,
                    "metadata": selected_metadata(item.get("metadata", {})),
                }
            )
            index_records.append(
                index_record_from_item(
                    item,
                    run_id,
                    assigned_at_utc,
                    "missing_input",
                    args,
                    error=item["error"],
                )
            )

        interrupted = False

        for item in planned:
            retries_used = 0
            item_start_dt = utc_now()
            item_start = format_utc(item_start_dt)
            item_result: dict[str, Any] | None = None
            last_error: str | None = None

            for attempt in range(args.max_retries + 1):
                try:
                    if attempt > 0:
                        retries_used = attempt
                        logger.info("Retry %s for %s", attempt, item["corpus_id"])
                        time.sleep(args.retry_delay)

                    item_result = process_one_item(
                        item=item,
                        args=args,
                        run_id=run_id,
                        assigned_at_utc=assigned_at_utc,
                        logger=logger,
                    )
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001 - per-item batch resiliency
                    last_error = str(exc)
                    logger.error(
                        "FAILED attempt %s for %s: %s",
                        attempt + 1,
                        item["corpus_id"],
                        last_error,
                    )

            item_end_dt = utc_now()
            item_end = format_utc(item_end_dt)
            duration = round((item_end_dt - item_start_dt).total_seconds(), 3)

            if item_result is not None and last_error is None:
                manifest_items.append(
                    {
                        **item_manifest_base(item),
                        "status": "success",
                        "error": None,
                        "retries": retries_used,
                        "duration_seconds": duration,
                        "start_time": item_start,
                        "end_time": item_end,
                        **{
                            key: item_result.get(key)
                            for key in (
                                "word_count",
                                "assigned_word_count",
                                "unassigned_word_count",
                                "speaker_segment_count",
                                "detected_speaker_count",
                                "assigned_speaker_count",
                            )
                        },
                        "metadata": item_result.get("metadata", {}),
                    }
                )
                index_records.append(
                    index_record_from_item(
                        item,
                        run_id,
                        assigned_at_utc,
                        "success",
                        args,
                        result=item_result,
                        error=None,
                    )
                )
            else:
                manifest_items.append(
                    {
                        **item_manifest_base(item),
                        "status": "failed",
                        "error": last_error,
                        "retries": retries_used,
                        "duration_seconds": duration,
                        "start_time": item_start,
                        "end_time": item_end,
                        "metadata": selected_metadata(item.get("metadata", {})),
                    }
                )
                index_records.append(
                    index_record_from_item(
                        item,
                        run_id,
                        assigned_at_utc,
                        "failed",
                        args,
                        error=last_error,
                    )
                )

        for invalid in invalid_records:
            record = invalid.get("record", {})
            index_records.append(
                {
                    "corpus_id": record.get("corpus_id"),
                    "speaker_assignment_status": "failed_metadata",
                    "speaker_assignment_run_id": run_id,
                    "assigned_at_utc": assigned_at_utc,
                    "assignment_method": args.assignment_method,
                    "min_overlap_ratio": args.min_overlap_ratio,
                    "error": invalid.get("error"),
                }
            )

        write_speaker_assignment_index(index_records, args.speaker_index_file)
        logger.info("Wrote speaker-assignment index: %s", args.speaker_index_file)

        summary = {
            "alignment_index_records": alignment_total,
            "eligible_alignment_records": len(alignment_records),
            "diarisation_index_records": diarisation_total,
            "eligible_diarisation_records": len(diarisation_records),
            "matched_records": len(matched_records),
            "ignored_records": len(ignored_records),
            "invalid_metadata": len(invalid_records),
            "planned": len(planned),
            "attempted": len(planned),
            "succeeded": sum(1 for item in manifest_items if item["status"] == "success"),
            "failed": sum(1 for item in manifest_items if item["status"] == "failed"),
            "missing_input": len(missing),
            "skipped_existing": len(skipped),
        }

        end_time = format_utc(utc_now())
        manifest = build_manifest(
            args=args,
            run_id=run_id,
            start_time=start_time,
            end_time=end_time,
            items=manifest_items,
            invalid_records=invalid_records,
            ignored_records=ignored_records,
            summary=summary,
            interrupted=interrupted,
        )

        latest_manifest, run_manifest = write_manifests(manifest, args.manifest_file, run_id)
        logger.info("Wrote latest manifest: %s", latest_manifest)
        logger.info("Wrote run manifest: %s", run_manifest)
        logger.info("Final summary: %s", summary)

        if summary["failed"] or summary["missing_input"] or summary["invalid_metadata"]:
            return 1

        return 0

    except KeyboardInterrupt:
        if logger:
            logger.error("Interrupted by user")
        return 130

    except ConfigurationError as exc:
        message = f"Configuration error: {exc}"
        if logger:
            logger.error(message)
        else:
            print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())