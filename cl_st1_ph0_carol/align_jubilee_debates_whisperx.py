#!/usr/bin/env python3
"""
Align Jubilee debate transcripts to audio with WhisperX.

This script reads a curated Jubilee debate transcript index from an NDJSON file,
selects records whose transcript outputs are available, and performs forced
alignment between transcript segments and the source WAV audio using WhisperX.

Source audio files are resolved from the transcript index record's "audio_file"
field when available, or from the audio directory as "<corpus_id>.wav".
Transcript JSON files are resolved from "transcript_json_file" when available,
or from the transcript directory as "<corpus_id>.json".

Alignment outputs are written to the output directory as
"<corpus_id>.aligned.json" and "<corpus_id>.words.ndjson". The aligned JSON
preserves segment-level and word-level timing information for downstream speaker
assignment. The word NDJSON provides one aligned word/token per line.

By default, the script runs in test mode and attempts only the first planned
debate. Existing alignment outputs are skipped unless --reprocess is provided,
making the script safe to re-run.

The recommended deployment environment is an x86_64 EC2 GPU instance using a
Python 3.11 conda environment with WhisperX and CUDA support.

Use --start-corpus-id to resume planning from a specific debate onward.

This programme performs alignment only. Transcription, diarisation, speaker
assignment, and quality-control reporting are handled by separate pipeline stages.

Example:
    python align_jubilee_debates_whisperx.py

Full run:
    python align_jubilee_debates_whisperx.py --no-test-mode

Full run from a specific debate:
    python align_jubilee_debates_whisperx.py --no-test-mode --start-corpus-id jubilee_surrounded_003
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOOL_NAME = "align_jubilee_debates_whisperx.py"
TOOL_VERSION = "v1"

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_TRANSCRIPT_INDEX_PATH = (
    "corpus/03_jubilee_debates_transcripts/"
    "jubilee_debates_transcript_index.ndjson"
)
DEFAULT_AUDIO_DIR = "corpus/02_jubilee_debates_audio"
DEFAULT_TRANSCRIPT_DIR = "corpus/03_jubilee_debates_transcripts"
DEFAULT_OUTPUT_DIR = "corpus/04_jubilee_debates_alignment"
DEFAULT_LOG_FILE = (
    "corpus/04_jubilee_debates_alignment/"
    "align_jubilee_debates_whisperx.log"
)
DEFAULT_MANIFEST_FILE = (
    "corpus/04_jubilee_debates_alignment/"
    "align_jubilee_debates_whisperx_manifest.json"
)
DEFAULT_ALIGNMENT_INDEX_FILE = (
    "corpus/04_jubilee_debates_alignment/"
    "jubilee_debates_alignment_index.ndjson"
)

DEFAULT_BACKEND = "whisperx"
DEFAULT_DEVICE = "cuda"
DEFAULT_LANGUAGE = "en"
DEFAULT_BATCH_SIZE = 8
DEFAULT_RETURN_CHAR_ALIGNMENTS = False
DEFAULT_INTERPOLATE_METHOD = "nearest"

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 1
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 14400
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

INPUT_AUDIO_EXTENSION = ".wav"
INPUT_TRANSCRIPT_JSON_EXTENSION = ".json"
OUTPUT_ALIGNED_JSON_EXTENSION = ".aligned.json"
OUTPUT_WORDS_NDJSON_EXTENSION = ".words.ndjson"

ELIGIBLE_TRANSCRIPTION_STATUSES = ("success", "skipped_existing")
SUPPORTED_BACKENDS = ("whisperx",)
SUPPORTED_DEVICES = ("cuda", "cpu", "auto")
SUPPORTED_INTERPOLATE_METHODS = ("nearest", "linear", "ignore")

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
    "transcript_text_file",
    "transcript_json_file",
    "transcription_status",
    "transcription_run_id",
    "transcribed_at_utc",
    "transcript_characters",
    "segment_count",
    "detected_language",
    "language_probability",
    "model_name",
    "backend",
    "device",
    "compute_type",
    "batch_size",
    "audio_extraction_status",
    "audio_extraction_run_id",
    "selected_by",
    "selection_source",
    "notes",
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


def resolve_script_relative_path(path: Path) -> Path:
    """
    Resolve relative paths against the programme directory.

    Args:
        path: Relative or absolute filesystem path.

    Returns:
        Absolute paths unchanged; relative paths resolved against SCRIPT_DIR.

    I/O:
        None.

    Error behaviour:
        Does not raise for non-existent paths.
    """
    if path.is_absolute():
        return path
    return SCRIPT_DIR / path


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the alignment programme.

    Returns:
        Parsed argparse namespace with filesystem paths resolved against SCRIPT_DIR.

    I/O:
        Reads command-line arguments through argparse.

    Error behaviour:
        argparse exits with code 2 for malformed command-line usage.
    """
    parser = argparse.ArgumentParser(
        description="Align Jubilee debate transcript segments to WAV audio with WhisperX."
    )

    parser.add_argument("--transcript-index", default=DEFAULT_TRANSCRIPT_INDEX_PATH)
    parser.add_argument("--audio-dir", default=DEFAULT_AUDIO_DIR)
    parser.add_argument("--transcript-dir", default=DEFAULT_TRANSCRIPT_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)

    parser.add_argument("--backend", default=DEFAULT_BACKEND, choices=SUPPORTED_BACKENDS)
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=SUPPORTED_DEVICES)
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)

    char_group = parser.add_mutually_exclusive_group()
    char_group.add_argument(
        "--return-char-alignments",
        dest="return_char_alignments",
        action="store_true",
    )
    char_group.add_argument(
        "--no-return-char-alignments",
        dest="return_char_alignments",
        action="store_false",
    )
    parser.set_defaults(return_char_alignments=DEFAULT_RETURN_CHAR_ALIGNMENTS)

    parser.add_argument(
        "--interpolate-method",
        default=DEFAULT_INTERPOLATE_METHOD,
        choices=SUPPORTED_INTERPOLATE_METHODS,
    )

    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument("--test-mode", dest="test_mode", action="store_true")
    test_group.add_argument("--no-test-mode", dest="test_mode", action="store_false")
    parser.set_defaults(test_mode=DEFAULT_TEST_MODE)

    parser.add_argument("--test-limit", type=int, default=DEFAULT_TEST_LIMIT)
    parser.add_argument("--reprocess", action="store_true")
    parser.add_argument("--start-corpus-id", default=None)

    parser.add_argument("--log-file", default=DEFAULT_LOG_FILE)
    parser.add_argument("--manifest-file", default=DEFAULT_MANIFEST_FILE)
    parser.add_argument("--alignment-index-file", default=DEFAULT_ALIGNMENT_INDEX_FILE)

    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--retry-delay", type=int, default=DEFAULT_RETRY_DELAY_SECONDS)

    args = parser.parse_args()

    args.transcript_index = resolve_script_relative_path(Path(args.transcript_index))
    args.audio_dir = resolve_script_relative_path(Path(args.audio_dir))
    args.transcript_dir = resolve_script_relative_path(Path(args.transcript_dir))
    args.output_dir = resolve_script_relative_path(Path(args.output_dir))
    args.log_file = resolve_script_relative_path(Path(args.log_file))
    args.manifest_file = resolve_script_relative_path(Path(args.manifest_file))
    args.alignment_index_file = resolve_script_relative_path(
        Path(args.alignment_index_file)
    )

    return args


def setup_logging(log_file: Path) -> logging.Logger:
    """
    Configure append-only UTF-8 file and console logging.

    Args:
        log_file: Destination log file path.

    Returns:
        Configured programme logger.

    I/O:
        Creates the parent directory and appends to the log file.

    Error behaviour:
        Propagates OSError if logging cannot be configured.
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
        args: Parsed and path-resolved argparse namespace.

    Returns:
        None.

    I/O:
        Checks path existence and creates output/log/manifest/index directories.

    Error behaviour:
        Raises ConfigurationError for invalid arguments or paths.
    """
    if not args.device or not str(args.device).strip():
        raise ConfigurationError("--device must not be blank.")
    if not args.language or not str(args.language).strip():
        raise ConfigurationError("--language must not be blank.")
    if args.batch_size <= 0:
        raise ConfigurationError("--batch-size must be a positive integer.")
    if args.test_limit <= 0:
        raise ConfigurationError("--test-limit must be a positive integer.")
    if args.workers <= 0:
        raise ConfigurationError("--workers must be a positive integer.")
    if args.workers != 1:
        raise ConfigurationError("Only --workers 1 is supported initially.")
    if args.timeout <= 0:
        raise ConfigurationError("--timeout must be a positive integer.")
    if args.max_retries < 0:
        raise ConfigurationError("--max-retries must be zero or positive.")
    if args.retry_delay < 0:
        raise ConfigurationError("--retry-delay must be zero or positive.")
    if args.start_corpus_id is not None and not args.start_corpus_id.strip():
        raise ConfigurationError("--start-corpus-id must not be empty.")

    if not args.transcript_index.exists():
        raise ConfigurationError(
            f"Transcript index does not exist: {args.transcript_index}"
        )
    if not args.transcript_index.is_file():
        raise ConfigurationError(
            f"Transcript index path is not a file: {args.transcript_index}"
        )

    try:
        with args.transcript_index.open("r", encoding="utf-8"):
            pass
    except OSError as exc:
        raise ConfigurationError(
            f"Transcript index file is unreadable: {args.transcript_index}: {exc}"
        ) from exc

    if not args.audio_dir.exists():
        raise ConfigurationError(f"Audio directory does not exist: {args.audio_dir}")
    if not args.audio_dir.is_dir():
        raise ConfigurationError(f"Audio path is not a directory: {args.audio_dir}")

    if not args.transcript_dir.exists():
        raise ConfigurationError(
            f"Transcript directory does not exist: {args.transcript_dir}"
        )
    if not args.transcript_dir.is_dir():
        raise ConfigurationError(
            f"Transcript path is not a directory: {args.transcript_dir}"
        )

    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        args.alignment_index_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create output directories: {exc}") from exc


def check_alignment_dependencies() -> dict[str, Any]:
    """
    Check required Python package availability.

    Returns:
        Dictionary with import availability and package versions where known.

    I/O:
        Imports Python modules.

    Error behaviour:
        Raises ConfigurationError when required packages are missing.
    """
    required = ("whisperx", "torch", "torchaudio")
    dependencies: dict[str, Any] = {}
    missing: list[str] = []

    for package_name in required:
        try:
            module = importlib.import_module(package_name)
            dependencies[package_name] = {
                "available": True,
                "version": getattr(module, "__version__", "unknown"),
            }
        except ImportError:
            dependencies[package_name] = {"available": False, "version": None}
            missing.append(package_name)

    if missing:
        raise ConfigurationError(
            "Required alignment package(s) not installed: " + ", ".join(missing)
        )

    return dependencies


def check_cuda_available(device: str) -> dict[str, Any]:
    """
    Validate CUDA availability when requested.

    Args:
        device: Requested device value: cuda, cpu, or auto.

    Returns:
        CUDA and torch environment metadata.

    I/O:
        Imports torch and queries CUDA state.

    Error behaviour:
        Raises ConfigurationError if --device cuda is requested but unavailable.
    """
    torch = importlib.import_module("torch")
    cuda_available = bool(torch.cuda.is_available())
    cuda_device_name = None

    if cuda_available:
        try:
            cuda_device_name = torch.cuda.get_device_name(0)
        except Exception:
            cuda_device_name = "unknown"

    if device == "cuda" and not cuda_available:
        raise ConfigurationError("--device cuda requested but CUDA is unavailable.")

    return {
        "cuda_available": cuda_available,
        "cuda_device_name": cuda_device_name,
        "torch_version": getattr(torch, "__version__", "unknown"),
        "torch_cuda_version": getattr(getattr(torch, "version", None), "cuda", None),
    }


def make_item_base(record: dict[str, Any]) -> dict[str, Any]:
    """Return preserved source metadata fields from a source record."""
    return {
        field: record.get(field)
        for field in PRESERVED_METADATA_FIELDS
        if field in record
    }


def load_transcript_index(
    transcript_index_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int, list[dict[str, Any]]]:
    """
    Load and validate eligible transcript records from NDJSON.

    Args:
        transcript_index_path: Source transcript index path.

    Returns:
        eligible_records, invalid_records, total_records, ignored_count,
        ignored_records.

    I/O:
        Reads the NDJSON transcript index.

    Error behaviour:
        Raises ConfigurationError for invalid JSON/object lines or no eligible
        transcript records at all.
    """
    eligible_records: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    ignored_records: list[dict[str, Any]] = []
    total_records = 0

    with transcript_index_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            total_records += 1

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ConfigurationError(
                    f"Invalid JSON in transcript index at line {line_number}: {exc}"
                ) from exc

            if not isinstance(record, dict):
                raise ConfigurationError(
                    f"Invalid NDJSON object at line {line_number}: expected object."
                )

            status = record.get("transcription_status")
            if status not in ELIGIBLE_TRANSCRIPTION_STATUSES:
                ignored_records.append(
                    make_item_base(record)
                    | {
                        "status": "ignored_transcript_unavailable",
                        "line_number": line_number,
                        "transcription_status": status,
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
                        "error": (
                            "Eligible transcript record is missing non-empty corpus_id."
                        ),
                    }
                )
                continue

            eligible_records.append(record)

    if not eligible_records and not invalid_records:
        raise ConfigurationError("No eligible transcript records found in transcript index.")

    return eligible_records, invalid_records, total_records, len(ignored_records), ignored_records


def resolve_audio_path(record: dict[str, Any], audio_dir: Path) -> Path:
    """
    Resolve source audio path using audio_file or fallback audio directory.

    Args:
        record: Eligible transcript index record.
        audio_dir: Fallback directory containing "<corpus_id>.wav".

    Returns:
        Candidate source audio path.

    I/O:
        Does not check path existence.

    Error behaviour:
        KeyError only if corpus_id is absent after earlier validation.
    """
    audio_file = record.get("audio_file")
    if isinstance(audio_file, str) and audio_file.strip():
        return resolve_script_relative_path(Path(audio_file.strip()))

    return audio_dir / f"{record['corpus_id']}{INPUT_AUDIO_EXTENSION}"


def resolve_transcript_json_path(record: dict[str, Any], transcript_dir: Path) -> Path:
    """
    Resolve transcript JSON path using transcript_json_file or fallback directory.

    Args:
        record: Eligible transcript index record.
        transcript_dir: Fallback directory containing "<corpus_id>.json".

    Returns:
        Candidate source transcript JSON path.

    I/O:
        Does not check path existence.

    Error behaviour:
        KeyError only if corpus_id is absent after earlier validation.
    """
    transcript_json_file = record.get("transcript_json_file")
    if isinstance(transcript_json_file, str) and transcript_json_file.strip():
        return resolve_script_relative_path(Path(transcript_json_file.strip()))

    return transcript_dir / f"{record['corpus_id']}{INPUT_TRANSCRIPT_JSON_EXTENSION}"


def plan_alignments(
    records: list[dict[str, Any]],
    audio_dir: Path,
    transcript_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_corpus_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Create planned, skipped, and missing-input alignment records.

    Args:
        records: Valid eligible transcript metadata records.
        audio_dir: Fallback source audio directory.
        transcript_dir: Fallback transcript JSON directory.
        output_dir: Alignment output directory.
        test_mode: Whether to limit planned attempts.
        test_limit: Maximum planned attempts in test mode.
        reprocess: Whether to overwrite existing alignment outputs.
        start_corpus_id: Optional corpus_id from which to start planning.

    Returns:
        planned, skipped_existing, missing_input item lists.

    I/O:
        Checks source and output path existence.

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
        audio_path = resolve_audio_path(record, audio_dir)
        transcript_json_path = resolve_transcript_json_path(record, transcript_dir)
        aligned_json_path = output_dir / f"{corpus_id}{OUTPUT_ALIGNED_JSON_EXTENSION}"
        words_ndjson_path = output_dir / f"{corpus_id}{OUTPUT_WORDS_NDJSON_EXTENSION}"

        item = {
            "record": record,
            "corpus_id": corpus_id,
            "audio_path": audio_path,
            "transcript_json_path": transcript_json_path,
            "aligned_json_path": aligned_json_path,
            "words_ndjson_path": words_ndjson_path,
        }

        missing_reasons = []
        if not audio_path.exists():
            missing_reasons.append(f"Source audio file is missing: {audio_path}")
        if not transcript_json_path.exists():
            missing_reasons.append(
                f"Transcript JSON file is missing: {transcript_json_path}"
            )

        if missing_reasons:
            item["missing_reasons"] = missing_reasons
            missing_input.append(item)
            continue

        complete_outputs_exist = aligned_json_path.exists() and words_ndjson_path.exists()
        if complete_outputs_exist and not reprocess:
            skipped_existing.append(item)
            continue

        planned.append(item)

    if test_mode:
        planned = planned[:test_limit]

    return planned, skipped_existing, missing_input


def load_transcript_json(transcript_json_path: Path) -> dict[str, Any]:
    """
    Load one transcript JSON file.

    Args:
        transcript_json_path: Source transcript JSON path.

    Returns:
        Parsed transcript JSON object.

    I/O:
        Reads a JSON file.

    Error behaviour:
        Raises ValueError or OSError if the file cannot be parsed/read.
    """
    with transcript_json_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("Transcript JSON root must be an object.")

    return data


def extract_segments_for_alignment(transcript_json: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract stable segment list for WhisperX alignment.

    Args:
        transcript_json: Parsed transcript JSON object.

    Returns:
        List of segment dictionaries with start/end/text and optional id.

    I/O:
        None.

    Error behaviour:
        Raises ValueError if no usable segments are found.
    """
    transcription = transcript_json.get("transcription")
    if not isinstance(transcription, dict):
        raise ValueError("Transcript JSON lacks transcription object.")

    raw_segments = transcription.get("segments")
    if not isinstance(raw_segments, list):
        raise ValueError("Transcript JSON lacks transcription.segments list.")

    segments: list[dict[str, Any]] = []
    for index, raw_segment in enumerate(raw_segments, start=1):
        if not isinstance(raw_segment, dict):
            continue

        text = raw_segment.get("text")
        if not isinstance(text, str) or not text.strip():
            continue

        segment = {
            "start": raw_segment.get("start"),
            "end": raw_segment.get("end"),
            "text": text.strip(),
        }

        if "id" in raw_segment:
            segment["id"] = raw_segment["id"]
        else:
            segment["id"] = index

        segments.append(segment)

    if not segments:
        raise ValueError("Transcript JSON contains no usable transcript segments.")

    return segments


def infer_language(
    configured_language: str,
    transcript_json: dict[str, Any],
    record: dict[str, Any],
    logger: logging.Logger,
) -> str:
    """Infer effective alignment language from config, transcript JSON, or record."""
    if configured_language != "auto":
        return configured_language

    model = transcript_json.get("model")
    transcription = transcript_json.get("transcription")

    candidates = [
        model.get("language") if isinstance(model, dict) else None,
        transcription.get("detected_language") if isinstance(transcription, dict) else None,
        record.get("detected_language"),
    ]

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    logger.warning("Could not infer language; falling back to en.")
    return "en"


def load_alignment_model(language: str, device: str) -> tuple[Any, Any]:
    """
    Load WhisperX alignment model and metadata.

    Args:
        language: Language code for alignment model loading.
        device: Runtime device.

    Returns:
        Tuple of alignment_model, alignment_metadata.

    I/O:
        Imports WhisperX and may download/load model files.

    Error behaviour:
        Raises ConfigurationError if model loading fails.
    """
    whisperx = importlib.import_module("whisperx")

    try:
        return whisperx.load_align_model(language_code=language, device=device)
    except Exception as exc:
        raise ConfigurationError(
            f"Could not load WhisperX alignment model for language {language}: {exc}"
        ) from exc


def normalise_alignment_result(raw_alignment: dict[str, Any]) -> dict[str, Any]:
    """
    Normalise WhisperX alignment output into project-stable JSON.

    Args:
        raw_alignment: Raw dictionary returned by whisperx.align.

    Returns:
        Dictionary containing normalised segments and word counts.

    I/O:
        None.

    Error behaviour:
        Raises ValueError if raw_alignment is not usable.
    """
    if not isinstance(raw_alignment, dict):
        raise ValueError("Alignment backend returned a non-dictionary result.")

    raw_segments = raw_alignment.get("segments")
    if not isinstance(raw_segments, list):
        raise ValueError("Alignment backend result lacks a segments list.")

    segments: list[dict[str, Any]] = []
    word_records: list[dict[str, Any]] = []

    for segment_index, raw_segment in enumerate(raw_segments, start=1):
        if not isinstance(raw_segment, dict):
            continue

        segment_id = raw_segment.get("id", segment_index)
        normalised_segment = {
            "id": segment_id,
            "start": raw_segment.get("start"),
            "end": raw_segment.get("end"),
            "text": raw_segment.get("text", ""),
            "words": [],
        }

        if "chars" in raw_segment:
            normalised_segment["chars"] = raw_segment["chars"]

        raw_words = raw_segment.get("words", [])
        if isinstance(raw_words, list):
            for raw_word in raw_words:
                if not isinstance(raw_word, dict):
                    continue

                word = raw_word.get("word")
                if word is None:
                    word = raw_word.get("text")

                word_record = {
                    "segment_id": segment_id,
                    "word": word,
                    "start": raw_word.get("start"),
                    "end": raw_word.get("end"),
                    "score": raw_word.get("score"),
                    "alignment_status": (
                        "aligned"
                        if raw_word.get("start") is not None and raw_word.get("end") is not None
                        else "unaligned"
                    ),
                }

                for optional_field in ("case", "chars"):
                    if optional_field in raw_word:
                        word_record[optional_field] = raw_word[optional_field]

                normalised_segment["words"].append(word_record)
                word_records.append(word_record)

        segments.append(normalised_segment)

    return {
        "segments": segments,
        "segment_count": len(segments),
        "word_count": len(word_records),
        "aligned_word_count": sum(
            1 for word in word_records if word.get("alignment_status") == "aligned"
        ),
        "unaligned_word_count": sum(
            1 for word in word_records if word.get("alignment_status") == "unaligned"
        ),
        "word_records": word_records,
    }


def write_alignment_outputs(
    aligned_json: dict[str, Any],
    word_records: list[dict[str, Any]],
    aligned_json_path: Path,
    words_ndjson_path: Path,
) -> None:
    """
    Write aligned JSON and word-level NDJSON outputs.

    Args:
        aligned_json: JSON-serialisable alignment object.
        word_records: Per-word JSON-serialisable records.
        aligned_json_path: Destination .aligned.json path.
        words_ndjson_path: Destination .words.ndjson path.

    Returns:
        None.

    I/O:
        Creates parent directories and overwrites output files.

    Error behaviour:
        Propagates OSError and JSON serialisation errors.
    """
    aligned_json_path.parent.mkdir(parents=True, exist_ok=True)
    words_ndjson_path.parent.mkdir(parents=True, exist_ok=True)

    aligned_json_path.write_text(
        json.dumps(aligned_json, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    with words_ndjson_path.open("w", encoding="utf-8") as handle:
        for index, record in enumerate(word_records, start=1):
            output_record = dict(record)
            output_record.setdefault("word_index", index)
            handle.write(json.dumps(output_record, ensure_ascii=False, sort_keys=False) + "\n")


def align_one_debate(
    item: dict[str, Any],
    alignment_model: Any,
    alignment_metadata: Any,
    model_config: dict[str, Any],
    max_retries: int,
    retry_delay: int,
    logger: logging.Logger,
) -> dict[str, Any]:
    """
    Align one debate transcript to audio and return a structured result.

    Args:
        item: Planned alignment item.
        alignment_model: Loaded WhisperX alignment model.
        alignment_metadata: WhisperX alignment metadata.
        model_config: Alignment/backend configuration.
        max_retries: Number of retries after the initial failed attempt.
        retry_delay: Delay between failed attempts in seconds.
        logger: Configured programme logger.

    Returns:
        Manifest item dictionary with status, timing, counts, and errors.

    I/O:
        Reads transcript JSON, runs WhisperX alignment, and writes output files.

    Error behaviour:
        Captures per-item errors and returns status "failed".
    """
    whisperx = importlib.import_module("whisperx")

    corpus_id = item["corpus_id"]
    record = item["record"]
    audio_path = item["audio_path"]
    transcript_json_path = item["transcript_json_path"]
    aligned_json_path = item["aligned_json_path"]
    words_ndjson_path = item["words_ndjson_path"]

    start_time = utc_timestamp()
    monotonic_start = time.monotonic()
    total_attempts = max_retries + 1
    retries_used = 0
    final_error: str | None = None

    for attempt in range(1, total_attempts + 1):
        try:
            logger.info("Alignment attempt %s/%s for %s", attempt, total_attempts, corpus_id)

            transcript_json = load_transcript_json(transcript_json_path)
            segments = extract_segments_for_alignment(transcript_json)

            raw_alignment = whisperx.align(
                segments,
                alignment_model,
                alignment_metadata,
                str(audio_path),
                model_config["device"],
                return_char_alignments=model_config["return_char_alignments"],
                interpolate_method=model_config["interpolate_method"],
            )

            normalised = normalise_alignment_result(raw_alignment)

            word_records = []
            for word_index, word in enumerate(normalised["word_records"], start=1):
                word_records.append(
                    {
                        "corpus_id": corpus_id,
                        "segment_id": word.get("segment_id"),
                        "word_index": word_index,
                        "word": word.get("word"),
                        "start": word.get("start"),
                        "end": word.get("end"),
                        "score": word.get("score"),
                        "alignment_status": word.get("alignment_status"),
                    }
                )

            end_time = utc_timestamp()
            duration = round(time.monotonic() - monotonic_start, 3)

            aligned_json = {
                "corpus_id": corpus_id,
                "input_audio_path": str(audio_path),
                "input_transcript_json_path": str(transcript_json_path),
                "aligned_json_path": str(aligned_json_path),
                "words_ndjson_path": str(words_ndjson_path),
                "alignment_model": {
                    "backend": model_config["backend"],
                    "language": model_config["language"],
                    "device": model_config["device"],
                    "batch_size": model_config["batch_size"],
                    "return_char_alignments": model_config["return_char_alignments"],
                    "interpolate_method": model_config["interpolate_method"],
                },
                "alignment": {
                    "segment_count": normalised["segment_count"],
                    "word_count": normalised["word_count"],
                    "aligned_word_count": normalised["aligned_word_count"],
                    "unaligned_word_count": normalised["unaligned_word_count"],
                    "segments": normalised["segments"],
                },
                "metadata": make_item_base(record),
                "run": {
                    "alignment_run_id": model_config["run_id"],
                    "aligned_at_utc": end_time,
                },
                "status": "success",
                "error": None,
            }

            write_alignment_outputs(
                aligned_json=aligned_json,
                word_records=word_records,
                aligned_json_path=aligned_json_path,
                words_ndjson_path=words_ndjson_path,
            )

            logger.info(
                "SUCCESS %s -> %s word_count=%s aligned=%s unaligned=%s",
                corpus_id,
                aligned_json_path,
                normalised["word_count"],
                normalised["aligned_word_count"],
                normalised["unaligned_word_count"],
            )

            return make_item_base(record) | {
                "corpus_id": corpus_id,
                "input_audio_path": str(audio_path),
                "input_transcript_json_path": str(transcript_json_path),
                "aligned_json_path": str(aligned_json_path),
                "words_ndjson_path": str(words_ndjson_path),
                "status": "success",
                "error": None,
                "retries": retries_used,
                "duration_seconds": duration,
                "start_time": start_time,
                "end_time": end_time,
                "segment_count": normalised["segment_count"],
                "word_count": normalised["word_count"],
                "aligned_word_count": normalised["aligned_word_count"],
                "unaligned_word_count": normalised["unaligned_word_count"],
                "metadata": make_item_base(record),
            }

        except Exception as exc:
            final_error = str(exc)
            logger.error("FAILED attempt %s for %s: %s", attempt, corpus_id, final_error)

            if attempt < total_attempts:
                retries_used += 1
                logger.info("Retrying %s after %s seconds", corpus_id, retry_delay)
                if retry_delay:
                    time.sleep(retry_delay)

    end_time = utc_timestamp()
    duration = round(time.monotonic() - monotonic_start, 3)

    return make_item_base(record) | {
        "corpus_id": corpus_id,
        "input_audio_path": str(audio_path),
        "input_transcript_json_path": str(transcript_json_path),
        "aligned_json_path": str(aligned_json_path),
        "words_ndjson_path": str(words_ndjson_path),
        "status": "failed",
        "error": final_error or "Alignment failed.",
        "retries": retries_used,
        "duration_seconds": duration,
        "start_time": start_time,
        "end_time": end_time,
        "segment_count": None,
        "word_count": None,
        "aligned_word_count": None,
        "unaligned_word_count": None,
        "metadata": make_item_base(record),
    }


def make_skipped_existing_result(
    item: dict[str, Any],
    model_config: dict[str, Any],
    logger: logging.Logger,
) -> dict[str, Any]:
    """Create a manifest item for a skipped complete alignment output pair."""
    logger.info("SKIPPED_EXISTING %s -> %s", item["corpus_id"], item["aligned_json_path"])

    word_count = None
    aligned_word_count = None
    unaligned_word_count = None

    try:
        word_count = 0
        aligned_word_count = 0
        unaligned_word_count = 0
        with item["words_ndjson_path"].open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                word_count += 1
                try:
                    record = json.loads(line)
                    if record.get("alignment_status") == "aligned":
                        aligned_word_count += 1
                    else:
                        unaligned_word_count += 1
                except json.JSONDecodeError:
                    unaligned_word_count += 1
    except OSError:
        word_count = None
        aligned_word_count = None
        unaligned_word_count = None

    return make_item_base(item["record"]) | {
        "corpus_id": item["corpus_id"],
        "input_audio_path": str(item["audio_path"]),
        "input_transcript_json_path": str(item["transcript_json_path"]),
        "aligned_json_path": str(item["aligned_json_path"]),
        "words_ndjson_path": str(item["words_ndjson_path"]),
        "status": "skipped_existing",
        "error": None,
        "retries": 0,
        "duration_seconds": 0,
        "start_time": None,
        "end_time": None,
        "segment_count": item["record"].get("segment_count"),
        "word_count": word_count,
        "aligned_word_count": aligned_word_count,
        "unaligned_word_count": unaligned_word_count,
        "metadata": make_item_base(item["record"]),
        "alignment_backend": model_config["backend"],
        "alignment_language": model_config["language"],
    }


def make_missing_input_result(item: dict[str, Any], logger: logging.Logger) -> dict[str, Any]:
    """Create a manifest item for missing source audio and/or transcript JSON."""
    error = "; ".join(item.get("missing_reasons", [])) or "Missing input."
    logger.error("MISSING_INPUT %s: %s", item["corpus_id"], error)

    return make_item_base(item["record"]) | {
        "corpus_id": item["corpus_id"],
        "input_audio_path": str(item["audio_path"]),
        "input_transcript_json_path": str(item["transcript_json_path"]),
        "aligned_json_path": str(item["aligned_json_path"]),
        "words_ndjson_path": str(item["words_ndjson_path"]),
        "status": "missing_input",
        "error": error,
        "retries": 0,
        "duration_seconds": None,
        "start_time": None,
        "end_time": None,
        "segment_count": None,
        "word_count": None,
        "aligned_word_count": None,
        "unaligned_word_count": None,
        "metadata": make_item_base(item["record"]),
    }


def make_alignment_index_record(
    item: dict[str, Any],
    model_config: dict[str, Any],
) -> dict[str, Any]:
    """Build one curated alignment index record."""
    record = {
        field: item.get(field)
        for field in PRESERVED_METADATA_FIELDS
        if field in item
    }

    record.update(
        {
            "corpus_id": item.get("corpus_id"),
            "audio_file": item.get("input_audio_path") or item.get("audio_file"),
            "transcript_json_file": item.get("input_transcript_json_path")
            or item.get("transcript_json_file"),
            "aligned_json_file": item.get("aligned_json_path"),
            "words_ndjson_file": item.get("words_ndjson_path"),
            "alignment_status": item.get("status"),
            "alignment_run_id": model_config["run_id"],
            "aligned_at_utc": item.get("end_time"),
            "alignment_language": model_config["language"],
            "alignment_backend": model_config["backend"],
            "alignment_device": model_config["device"],
            "word_count": item.get("word_count"),
            "aligned_word_count": item.get("aligned_word_count"),
            "unaligned_word_count": item.get("unaligned_word_count"),
            "segment_count": item.get("segment_count"),
            "error": item.get("error"),
        }
    )
    return record


def write_alignment_index(
    index_records: list[dict[str, Any]],
    alignment_index_file: Path,
) -> None:
    """
    Write curated NDJSON alignment index.

    Args:
        index_records: NDJSON-ready alignment index records.
        alignment_index_file: Destination file path.

    Returns:
        None.

    I/O:
        Creates parent directory and overwrites the alignment index file.

    Error behaviour:
        Propagates OSError and JSON serialisation errors.
    """
    alignment_index_file.parent.mkdir(parents=True, exist_ok=True)
    with alignment_index_file.open("w", encoding="utf-8") as handle:
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
        manifest: JSON-serialisable run manifest.
        manifest_file: Latest manifest path.
        run_id: Current run ID.

    Returns:
        latest_manifest_path, per_run_manifest_path.

    I/O:
        Writes two JSON manifest files.

    Error behaviour:
        Propagates OSError or JSON serialisation errors.
    """
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    per_run_manifest_file = (
        manifest_file.parent / f"{manifest_file.stem}_{run_id}{manifest_file.suffix}"
    )

    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False)
    manifest_file.write_text(manifest_json + "\n", encoding="utf-8")
    per_run_manifest_file.write_text(manifest_json + "\n", encoding="utf-8")

    return manifest_file, per_run_manifest_file


def build_environment_metadata(
    dependency_info: dict[str, Any] | None,
    cuda_info: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build manifest environment metadata."""
    dependency_info = dependency_info or {}
    cuda_info = cuda_info or {}
    return {
        "python_version": platform.python_version(),
        "cuda_available": cuda_info.get("cuda_available"),
        "cuda_device_name": cuda_info.get("cuda_device_name"),
        "torch_version": cuda_info.get("torch_version")
        or dependency_info.get("torch", {}).get("version"),
        "torch_cuda_version": cuda_info.get("torch_cuda_version"),
        "whisperx_version": dependency_info.get("whisperx", {}).get("version"),
        "torchaudio_version": dependency_info.get("torchaudio", {}).get("version"),
    }


def build_run_metadata(
    args: argparse.Namespace,
    run_id: str,
    start_time: str,
    end_time: str | None,
    model_config: dict[str, Any],
    environment: dict[str, Any],
    summary: dict[str, int],
    interrupted: bool = False,
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
        "transcript_index_path": str(args.transcript_index),
        "audio_dir": str(args.audio_dir),
        "transcript_dir": str(args.transcript_dir),
        "output_dir": str(args.output_dir),
        "alignment_index_file": str(args.alignment_index_file),
        "log_file": str(args.log_file),
        "manifest_file": str(args.manifest_file),
        "config": {
            "backend": model_config["backend"],
            "device": model_config["device"],
            "language": model_config["language"],
            "batch_size": model_config["batch_size"],
            "return_char_alignments": model_config["return_char_alignments"],
            "interpolate_method": model_config["interpolate_method"],
            "timeout_seconds": args.timeout,
            "max_retries": args.max_retries,
            "retry_delay_seconds": args.retry_delay,
            "start_corpus_id": args.start_corpus_id,
        },
        "environment": environment,
        "summary": summary,
        "interrupted": interrupted,
    }


def make_summary(
    transcript_index_records: int,
    eligible_transcript_records: int,
    ignored_transcript_records: int,
    invalid_metadata: int,
    planned: int,
    attempted: int,
    succeeded: int,
    failed: int,
    missing_input: int,
    skipped_existing: int,
) -> dict[str, int]:
    """Create a manifest summary dictionary."""
    return {
        "transcript_index_records": transcript_index_records,
        "eligible_transcript_records": eligible_transcript_records,
        "ignored_transcript_records": ignored_transcript_records,
        "invalid_metadata": invalid_metadata,
        "planned": planned,
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "missing_input": missing_input,
        "skipped_existing": skipped_existing,
    }


def main() -> int:
    """
    Run the batch Jubilee debate alignment workflow and return an exit code.

    Returns:
        Exit code:
            0 for clean completion;
            1 for item-level failures/missing inputs/invalid eligible metadata;
            2 for configuration errors;
            130 for keyboard interruption.

    I/O:
        Reads transcript index/transcript JSON files, loads WhisperX alignment
        models, aligns audio/transcripts, writes alignment outputs, appends logs,
        writes alignment index, and writes manifests.

    Error behaviour:
        Handles expected configuration, per-item, and interruption errors.
    """
    logger: logging.Logger | None = None
    args: argparse.Namespace | None = None

    run_id = make_run_id()
    start_time = utc_timestamp()

    dependency_info: dict[str, Any] | None = None
    cuda_info: dict[str, Any] | None = None

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
        logger.info("Transcript index: %s", args.transcript_index)
        logger.info("Audio directory: %s", args.audio_dir)
        logger.info("Transcript directory: %s", args.transcript_dir)
        logger.info("Output directory: %s", args.output_dir)
        logger.info(
            "Alignment config: backend=%s device=%s language=%s batch_size=%s return_char_alignments=%s interpolate_method=%s",
            args.backend,
            args.device,
            args.language,
            args.batch_size,
            args.return_char_alignments,
            args.interpolate_method,
        )
        logger.info("Test mode: %s; test_limit=%s", args.test_mode, args.test_limit)
        logger.info("Reprocess: %s", args.reprocess)
        logger.info("Start corpus ID: %s", args.start_corpus_id)

        dependency_info = check_alignment_dependencies()
        logger.info("Dependency availability: %s", dependency_info)

        cuda_info = check_cuda_available(args.device)
        logger.info(
            "CUDA available: %s; device=%s",
            cuda_info.get("cuda_available"),
            cuda_info.get("cuda_device_name"),
        )

        eligible_records, invalid_records, total_records, ignored_count, ignored_records = (
            load_transcript_index(args.transcript_index)
        )
        eligible_count = len(eligible_records) + len(invalid_records)

        logger.info(
            "Loaded transcript index: input=%s eligible=%s ignored=%s invalid=%s",
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

        planned, skipped_existing, missing_input = plan_alignments(
            records=eligible_records,
            audio_dir=args.audio_dir,
            transcript_dir=args.transcript_dir,
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

        model_config = {
            "backend": args.backend,
            "device": args.device,
            "language": "en" if args.language == "auto" else args.language,
            "configured_language": args.language,
            "batch_size": args.batch_size,
            "return_char_alignments": args.return_char_alignments,
            "interpolate_method": args.interpolate_method,
            "run_id": run_id,
        }

        for item in skipped_existing:
            manifest_items.append(make_skipped_existing_result(item, model_config, logger))

        for item in missing_input:
            manifest_items.append(make_missing_input_result(item, logger))

        alignment_model = None
        alignment_metadata = None
        if planned:
            if args.language == "auto":
                first_transcript_json = load_transcript_json(planned[0]["transcript_json_path"])
                model_config["language"] = infer_language(
                    args.language,
                    first_transcript_json,
                    planned[0]["record"],
                    logger,
                )

            logger.info("Loading alignment model for language=%s", model_config["language"])
            alignment_model, alignment_metadata = load_alignment_model(
                language=model_config["language"],
                device=args.device,
            )
            logger.info("Alignment model loaded successfully")
        else:
            logger.info("No planned alignments; model loading skipped.")

        for item in planned:
            attempted_count += 1
            manifest_items.append(
                align_one_debate(
                    item=item,
                    alignment_model=alignment_model,
                    alignment_metadata=alignment_metadata,
                    model_config=model_config,
                    max_retries=args.max_retries,
                    retry_delay=args.retry_delay,
                    logger=logger,
                )
            )

        succeeded = sum(1 for item in manifest_items if item.get("status") == "success")
        failed = sum(1 for item in manifest_items if item.get("status") == "failed")
        missing_count = sum(
            1 for item in manifest_items if item.get("status") == "missing_input"
        )
        skipped_count = sum(
            1 for item in manifest_items if item.get("status") == "skipped_existing"
        )

        alignment_index_records = [
            make_alignment_index_record(item, model_config)
            for item in [*manifest_items, *invalid_records]
            if item.get("status")
            in {"success", "failed", "skipped_existing", "missing_input", "failed_metadata"}
        ]
        write_alignment_index(alignment_index_records, args.alignment_index_file)
        logger.info("Wrote alignment index: %s", args.alignment_index_file)

        summary = make_summary(
            transcript_index_records=total_records,
            eligible_transcript_records=eligible_count,
            ignored_transcript_records=ignored_count,
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
                model_config=model_config,
                environment=build_environment_metadata(dependency_info, cuda_info),
                summary=summary,
                interrupted=False,
            ),
            "items": manifest_items,
            "invalid_records": invalid_records,
            "ignored_records": ignored_records,
        }

        latest_manifest, per_run_manifest = write_manifests(
            manifest,
            args.manifest_file,
            run_id,
        )
        logger.info("Wrote latest manifest: %s", latest_manifest)
        logger.info("Wrote per-run manifest: %s", per_run_manifest)
        logger.info(
            "Finished run: succeeded=%s failed=%s skipped_existing=%s missing_input=%s invalid_metadata=%s",
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
            fallback_config = {
                "backend": args.backend,
                "device": args.device,
                "language": "en" if args.language == "auto" else args.language,
                "configured_language": args.language,
                "batch_size": args.batch_size,
                "return_char_alignments": args.return_char_alignments,
                "interpolate_method": args.interpolate_method,
                "run_id": run_id,
            }

            summary = make_summary(
                transcript_index_records=total_records,
                eligible_transcript_records=eligible_count,
                ignored_transcript_records=ignored_count,
                invalid_metadata=len(invalid_records),
                planned=planned_count,
                attempted=attempted_count,
                succeeded=sum(1 for item in manifest_items if item.get("status") == "success"),
                failed=sum(1 for item in manifest_items if item.get("status") == "failed"),
                missing_input=sum(
                    1 for item in manifest_items if item.get("status") == "missing_input"
                ),
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
                    model_config=fallback_config,
                    environment=build_environment_metadata(dependency_info, cuda_info),
                    summary=summary,
                    interrupted=True,
                ),
                "items": manifest_items,
                "invalid_records": invalid_records,
                "ignored_records": ignored_records,
            }

            try:
                write_manifests(manifest, args.manifest_file, run_id)
            except Exception as exc:
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

    except Exception as exc:
        message = f"Unexpected error: {exc}"
        if logger:
            logger.exception(message)
        else:
            print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())