#!/usr/bin/env python3
"""
Transcribe full-length Jubilee debate audio with WhisperX.

This script reads a curated Jubilee debate audio index from an NDJSON file,
selects records whose extracted WAV audio is available, and transcribes one
full-length audio file per eligible debate using Whisper Large v3 through a
WhisperX-compatible transcription backend.

Source audio files are resolved from the input record's "audio_file" field when
available, or from the input directory as "<corpus_id>.wav". Transcript outputs
are written to the output directory as "<corpus_id>.txt" and "<corpus_id>.json".

The plain-text transcript is intended for corpus linguistic analysis and human
inspection. The JSON transcript preserves segment timestamps, model
configuration, source metadata, and run metadata for reproducibility.

By default, the script runs in test mode and attempts only the first planned
debate. Existing transcript files are skipped unless --reprocess is provided,
making the script safe to re-run.

The recommended deployment environment is an x86_64 EC2 GPU instance using a
Python 3.11 conda environment with WhisperX and CUDA support.

Use --start-corpus-id to resume planning from a specific debate onward.

This programme performs transcription only. Alignment, diarisation, speaker
assignment, and quality-control reporting are handled by later pipeline stages.

Example:
    python transcribe_jubilee_debates_whisperx.py

Full run:
    python transcribe_jubilee_debates_whisperx.py --no-test-mode

Full run from a specific debate:
    python transcribe_jubilee_debates_whisperx.py --no-test-mode --start-corpus-id jubilee_surrounded_003

The script writes an append-only log file, a JSON manifest, and a curated NDJSON
transcript index for downstream WhisperX alignment.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import platform
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOOL_NAME = "transcribe_jubilee_debates_whisperx.py"
TOOL_VERSION = "v1"

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_AUDIO_INDEX_PATH = (
    "corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson"
)
DEFAULT_INPUT_DIR = "corpus/02_jubilee_debates_audio"
DEFAULT_OUTPUT_DIR = "corpus/03_jubilee_debates_transcripts"
DEFAULT_LOG_FILE = (
    "corpus/03_jubilee_debates_transcripts/"
    "transcribe_jubilee_debates_whisperx.log"
)
DEFAULT_MANIFEST_FILE = (
    "corpus/03_jubilee_debates_transcripts/"
    "transcribe_jubilee_debates_whisperx_manifest.json"
)
DEFAULT_TRANSCRIPT_INDEX_FILE = (
    "corpus/03_jubilee_debates_transcripts/"
    "jubilee_debates_transcript_index.ndjson"
)

DEFAULT_BACKEND = "whisperx"
DEFAULT_MODEL_NAME = "large-v3"
DEFAULT_DEVICE = "cuda"
DEFAULT_COMPUTE_TYPE = "float16"
DEFAULT_LANGUAGE = "en"
DEFAULT_TASK = "transcribe"
DEFAULT_BATCH_SIZE = 8
DEFAULT_VAD_FILTER = True

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 1
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 14400
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

INPUT_AUDIO_EXTENSION = ".wav"
OUTPUT_TEXT_EXTENSION = ".txt"
OUTPUT_JSON_EXTENSION = ".json"

ELIGIBLE_AUDIO_STATUSES = ("success", "skipped_existing")
SUPPORTED_BACKENDS = ("whisperx", "faster-whisper")
SUPPORTED_DEVICES = ("cuda", "cpu", "auto")
SUPPORTED_TASKS = ("transcribe", "translate")

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
    "source_video_file",
    "audio_file",
    "audio_format",
    "audio_codec",
    "audio_channels",
    "audio_sample_rate",
    "audio_sample_format",
    "audio_file_size_bytes",
    "audio_extraction_status",
    "audio_extraction_run_id",
    "audio_extracted_at_utc",
    "ffmpeg_version",
    "download_run_id",
    "downloaded_at_utc",
    "video_download_status",
    "metadata_status",
    "raw_metadata_file",
    "description_file",
    "subtitles_files",
    "selected_by",
    "selection_source",
    "notes",
)


class ConfigurationError(Exception):
    """Raised when command-line options or runtime configuration are invalid."""


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_timestamp() -> str:
    """Return an ISO-like UTC timestamp string without microseconds."""
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    """Return a compact UTC run ID suitable for filenames."""
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
    Parse command-line arguments for the Jubilee debate transcription programme.

    Returns:
        Parsed argparse namespace with paths resolved relative to SCRIPT_DIR.

    I/O:
        Reads command-line arguments through argparse.

    Error behaviour:
        argparse exits with code 2 for malformed command-line usage.
    """
    parser = argparse.ArgumentParser(
        description="Transcribe Jubilee debate WAV audio with WhisperX."
    )

    parser.add_argument("--audio-index", default=DEFAULT_AUDIO_INDEX_PATH)
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)

    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--backend", default=DEFAULT_BACKEND, choices=SUPPORTED_BACKENDS)
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=SUPPORTED_DEVICES)
    parser.add_argument("--compute-type", default=DEFAULT_COMPUTE_TYPE)
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--task", default=DEFAULT_TASK, choices=SUPPORTED_TASKS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)

    vad_group = parser.add_mutually_exclusive_group()
    vad_group.add_argument("--vad-filter", dest="vad_filter", action="store_true")
    vad_group.add_argument("--no-vad-filter", dest="vad_filter", action="store_false")
    parser.set_defaults(vad_filter=DEFAULT_VAD_FILTER)

    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument("--test-mode", dest="test_mode", action="store_true")
    test_group.add_argument("--no-test-mode", dest="test_mode", action="store_false")
    parser.set_defaults(test_mode=DEFAULT_TEST_MODE)

    parser.add_argument("--test-limit", type=int, default=DEFAULT_TEST_LIMIT)
    parser.add_argument("--reprocess", action="store_true")
    parser.add_argument("--start-corpus-id", default=None)

    parser.add_argument("--log-file", default=DEFAULT_LOG_FILE)
    parser.add_argument("--manifest-file", default=DEFAULT_MANIFEST_FILE)
    parser.add_argument("--transcript-index-file", default=DEFAULT_TRANSCRIPT_INDEX_FILE)

    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--retry-delay", type=int, default=DEFAULT_RETRY_DELAY_SECONDS)

    args = parser.parse_args()

    args.audio_index = resolve_script_relative_path(Path(args.audio_index))
    args.input_dir = resolve_script_relative_path(Path(args.input_dir))
    args.output_dir = resolve_script_relative_path(Path(args.output_dir))
    args.log_file = resolve_script_relative_path(Path(args.log_file))
    args.manifest_file = resolve_script_relative_path(Path(args.manifest_file))
    args.transcript_index_file = resolve_script_relative_path(
        Path(args.transcript_index_file)
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
        args: Parsed, path-resolved command-line arguments.

    Returns:
        None.

    I/O:
        Checks filesystem paths and creates output/log/manifest directories.

    Error behaviour:
        Raises ConfigurationError for invalid arguments or paths.
    """
    if not args.model_name or not str(args.model_name).strip():
        raise ConfigurationError("--model-name must not be blank.")
    if not args.device or not str(args.device).strip():
        raise ConfigurationError("--device must not be blank.")
    if not args.compute_type or not str(args.compute_type).strip():
        raise ConfigurationError("--compute-type must not be blank.")
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

    if not args.audio_index.exists():
        raise ConfigurationError(f"Audio index does not exist: {args.audio_index}")
    if not args.audio_index.is_file():
        raise ConfigurationError(f"Audio index path is not a file: {args.audio_index}")

    try:
        with args.audio_index.open("r", encoding="utf-8"):
            pass
    except OSError as exc:
        raise ConfigurationError(
            f"Audio index file is unreadable: {args.audio_index}: {exc}"
        ) from exc

    if not args.input_dir.exists():
        raise ConfigurationError(f"Input audio directory does not exist: {args.input_dir}")
    if not args.input_dir.is_dir():
        raise ConfigurationError(f"Input audio path is not a directory: {args.input_dir}")

    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        args.transcript_index_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create output directories: {exc}") from exc


def check_transcription_dependencies() -> dict[str, Any]:
    """
    Check required Python package availability.

    Returns:
        Dictionary with import availability and package versions where known.

    I/O:
        Imports Python modules.

    Error behaviour:
        Raises ConfigurationError when required packages are missing.
    """
    dependencies: dict[str, Any] = {}

    required = ("whisperx", "torch")
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

    try:
        faster_whisper = importlib.import_module("faster_whisper")
        dependencies["faster_whisper"] = {
            "available": True,
            "version": getattr(faster_whisper, "__version__", "unknown"),
        }
    except ImportError:
        dependencies["faster_whisper"] = {"available": False, "version": None}

    if missing:
        raise ConfigurationError(
            "Required transcription package(s) not installed: " + ", ".join(missing)
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
    return {field: record.get(field) for field in PRESERVED_METADATA_FIELDS if field in record}


def load_audio_index(
    audio_index_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int, list[dict[str, Any]]]:
    """
    Load and validate eligible audio records from the NDJSON audio index.

    Args:
        audio_index_path: Source NDJSON audio index path.

    Returns:
        eligible_records, invalid_records, total_records, ignored_count,
        ignored_records.

    I/O:
        Reads the NDJSON audio index.

    Error behaviour:
        Raises ConfigurationError for invalid JSON/object lines or no eligible
        records at all.
    """
    eligible_records: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    ignored_records: list[dict[str, Any]] = []
    total_records = 0

    with audio_index_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            total_records += 1

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ConfigurationError(
                    f"Invalid JSON in audio index at line {line_number}: {exc}"
                ) from exc

            if not isinstance(record, dict):
                raise ConfigurationError(
                    f"Invalid NDJSON object at line {line_number}: expected object."
                )

            status = record.get("audio_extraction_status")
            if status not in ELIGIBLE_AUDIO_STATUSES:
                ignored_records.append(
                    make_item_base(record)
                    | {
                        "status": "ignored_audio_unavailable",
                        "line_number": line_number,
                        "audio_extraction_status": status,
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
                        "error": "Eligible audio record is missing non-empty corpus_id.",
                    }
                )
                continue

            eligible_records.append(record)

    if not eligible_records and not invalid_records:
        raise ConfigurationError("No eligible audio records found in audio index.")

    return eligible_records, invalid_records, total_records, len(ignored_records), ignored_records


def resolve_source_audio_path(record: dict[str, Any], input_dir: Path) -> Path:
    """
    Resolve source audio path using audio_file or fallback input directory.

    Args:
        record: Eligible audio index record.
        input_dir: Fallback directory containing "<corpus_id>.wav".

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

    return input_dir / f"{record['corpus_id']}{INPUT_AUDIO_EXTENSION}"


def plan_transcriptions(
    records: list[dict[str, Any]],
    input_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_corpus_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Create planned, skipped-existing, and missing-input transcription records.

    Args:
        records: Valid eligible audio metadata records.
        input_dir: Fallback source audio directory.
        output_dir: Transcript output directory.
        test_mode: Whether to limit planned attempts.
        test_limit: Maximum planned attempts in test mode.
        reprocess: Whether to overwrite existing transcript outputs.
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
        input_audio_path = resolve_source_audio_path(record, input_dir)
        text_output_path = output_dir / f"{corpus_id}{OUTPUT_TEXT_EXTENSION}"
        json_output_path = output_dir / f"{corpus_id}{OUTPUT_JSON_EXTENSION}"

        item = {
            "record": record,
            "corpus_id": corpus_id,
            "input_audio_path": input_audio_path,
            "text_output_path": text_output_path,
            "json_output_path": json_output_path,
        }

        if not input_audio_path.exists():
            missing_input.append(item)
            continue

        complete_outputs_exist = text_output_path.exists() and json_output_path.exists()
        if complete_outputs_exist and not reprocess:
            skipped_existing.append(item)
            continue

        planned.append(item)

    if test_mode:
        planned = planned[:test_limit]

    return planned, skipped_existing, missing_input


def load_transcription_model(
    model_name: str,
    device: str,
    compute_type: str,
    backend: str,
) -> Any:
    """
    Load the Whisper/WhisperX transcription model once for the batch.

    Args:
        model_name: Whisper model name.
        device: Runtime device.
        compute_type: Faster-whisper compute type.
        backend: Backend label.

    Returns:
        Loaded model object.

    I/O:
        Imports whisperx and may download/load model files.

    Error behaviour:
        Raises ConfigurationError if model loading fails.
    """
    if backend != "whisperx":
        raise ConfigurationError(
            "The initial implementation supports the whisperx backend only."
        )

    whisperx = importlib.import_module("whisperx")

    try:
        return whisperx.load_model(model_name, device=device, compute_type=compute_type)
    except Exception as exc:
        raise ConfigurationError(f"Could not load transcription model: {exc}") from exc


def normalise_transcript_text(segment_texts: list[str]) -> str:
    """
    Create clean plain text from ordered segment texts.

    Args:
        segment_texts: Segment-level transcript text values.

    Returns:
        Clean whitespace-normalised transcript text.

    I/O:
        None.

    Error behaviour:
        Does not raise for empty input.
    """
    cleaned = [text.strip() for text in segment_texts if isinstance(text, str) and text.strip()]
    return re.sub(r"\s+", " ", " ".join(cleaned)).strip()


def normalise_segments(raw_segments: Any) -> list[dict[str, Any]]:
    """Convert backend segment output into stable segment dictionaries."""
    segments: list[dict[str, Any]] = []
    if not isinstance(raw_segments, list):
        return segments

    for index, segment in enumerate(raw_segments, start=1):
        if not isinstance(segment, dict):
            continue

        normalised = {
            "id": segment.get("id", index),
            "start": segment.get("start"),
            "end": segment.get("end"),
            "text": segment.get("text", ""),
        }

        for optional_field in ("words", "avg_logprob", "no_speech_prob"):
            if optional_field in segment:
                normalised[optional_field] = segment[optional_field]

        segments.append(normalised)

    return segments


def write_transcript_outputs(
    text: str,
    transcript_json: dict[str, Any],
    text_output_path: Path,
    json_output_path: Path,
) -> None:
    """
    Write text and JSON transcript outputs for one debate.

    Args:
        text: Plain transcript text.
        transcript_json: Structured transcript JSON.
        text_output_path: Destination .txt path.
        json_output_path: Destination .json path.

    Returns:
        None.

    I/O:
        Creates output parent directories and overwrites transcript outputs.

    Error behaviour:
        Propagates OSError/JSON serialisation errors to caller.
    """
    text_output_path.parent.mkdir(parents=True, exist_ok=True)
    json_output_path.parent.mkdir(parents=True, exist_ok=True)

    text_output_path.write_text(text + "\n", encoding="utf-8")
    json_output_path.write_text(
        json.dumps(transcript_json, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def transcribe_one_debate(
    model: Any,
    item: dict[str, Any],
    model_config: dict[str, Any],
    max_retries: int,
    retry_delay: int,
    logger: logging.Logger,
) -> dict[str, Any]:
    """
    Transcribe one Jubilee debate audio file and return a structured result.

    Args:
        model: Loaded WhisperX transcription model.
        item: Planned item containing input/output paths and source metadata.
        model_config: Model/backend configuration.
        max_retries: Number of retries after the initial failed attempt.
        retry_delay: Delay between retries in seconds.
        logger: Configured programme logger.

    Returns:
        Manifest item dictionary with status, timing, transcript stats, and errors.

    I/O:
        Runs model inference and writes .txt/.json transcript outputs.

    Error behaviour:
        Captures transcription/output errors and returns status "failed".
    """
    corpus_id = item["corpus_id"]
    input_audio_path = item["input_audio_path"]
    text_output_path = item["text_output_path"]
    json_output_path = item["json_output_path"]
    record = item["record"]

    start_time = utc_timestamp()
    monotonic_start = time.monotonic()
    total_attempts = max_retries + 1
    retries_used = 0
    final_error: str | None = None

    for attempt in range(1, total_attempts + 1):
        try:
            logger.info("Transcription attempt %s/%s for %s", attempt, total_attempts, corpus_id)

            language = None if model_config["language"] == "auto" else model_config["language"]
            result = model.transcribe(
                str(input_audio_path),
                batch_size=model_config["batch_size"],
                language=language,
                task=model_config["task"],
            )

            if not isinstance(result, dict):
                raise RuntimeError("Transcription backend returned a non-dictionary result.")

            segments = normalise_segments(result.get("segments", []))
            text = normalise_transcript_text([str(segment.get("text", "")) for segment in segments])

            if not text:
                logger.warning("Empty transcript for %s", corpus_id)

            end_time = utc_timestamp()
            duration = round(time.monotonic() - monotonic_start, 3)

            transcript_json = {
                "corpus_id": corpus_id,
                "input_audio_path": str(input_audio_path),
                "text_output_path": str(text_output_path),
                "json_output_path": str(json_output_path),
                "model": model_config,
                "transcription": {
                    "text": text,
                    "detected_language": result.get("language"),
                    "language_probability": result.get("language_probability"),
                    "duration_seconds": record.get("duration_seconds"),
                    "segment_count": len(segments),
                    "segments": segments,
                    "warning": "empty_transcript" if not text else None,
                },
                "metadata": make_item_base(record),
                "run": {
                    "transcription_run_id": model_config["run_id"],
                    "transcribed_at_utc": end_time,
                },
                "status": "success",
                "error": None,
            }

            write_transcript_outputs(text, transcript_json, text_output_path, json_output_path)

            logger.info("SUCCESS %s -> %s", corpus_id, text_output_path)

            return make_item_base(record) | {
                "corpus_id": corpus_id,
                "input_audio_path": str(input_audio_path),
                "text_output_path": str(text_output_path),
                "json_output_path": str(json_output_path),
                "status": "success",
                "error": None,
                "retries": retries_used,
                "duration_seconds": duration,
                "start_time": start_time,
                "end_time": end_time,
                "transcript_characters": len(text),
                "segment_count": len(segments),
                "detected_language": result.get("language"),
                "language_probability": result.get("language_probability"),
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
        "input_audio_path": str(input_audio_path),
        "text_output_path": str(text_output_path),
        "json_output_path": str(json_output_path),
        "status": "failed",
        "error": final_error or "Transcription failed.",
        "retries": retries_used,
        "duration_seconds": duration,
        "start_time": start_time,
        "end_time": end_time,
        "transcript_characters": None,
        "segment_count": None,
        "detected_language": None,
        "language_probability": None,
        "metadata": make_item_base(record),
    }


def make_skipped_existing_result(
    item: dict[str, Any],
    model_config: dict[str, Any],
    logger: logging.Logger,
) -> dict[str, Any]:
    """Create a manifest item for a skipped complete transcript pair."""
    logger.info("SKIPPED_EXISTING %s -> %s", item["corpus_id"], item["text_output_path"])

    transcript_characters = None
    try:
        transcript_characters = len(item["text_output_path"].read_text(encoding="utf-8").strip())
    except OSError:
        pass

    return make_item_base(item["record"]) | {
        "corpus_id": item["corpus_id"],
        "input_audio_path": str(item["input_audio_path"]),
        "text_output_path": str(item["text_output_path"]),
        "json_output_path": str(item["json_output_path"]),
        "status": "skipped_existing",
        "error": None,
        "retries": 0,
        "duration_seconds": 0,
        "start_time": None,
        "end_time": None,
        "transcript_characters": transcript_characters,
        "segment_count": None,
        "detected_language": None,
        "language_probability": None,
        "metadata": make_item_base(item["record"]),
        "model_name": model_config["model_name"],
        "backend": model_config["backend"],
    }


def make_missing_input_result(
    item: dict[str, Any],
    logger: logging.Logger,
) -> dict[str, Any]:
    """Create a manifest item for a missing source audio file."""
    error = f"Source audio file is missing: {item['input_audio_path']}"
    logger.error("MISSING_INPUT %s: %s", item["corpus_id"], item["input_audio_path"])

    return make_item_base(item["record"]) | {
        "corpus_id": item["corpus_id"],
        "input_audio_path": str(item["input_audio_path"]),
        "text_output_path": str(item["text_output_path"]),
        "json_output_path": str(item["json_output_path"]),
        "status": "missing_input",
        "error": error,
        "retries": 0,
        "duration_seconds": None,
        "start_time": None,
        "end_time": None,
        "transcript_characters": None,
        "segment_count": None,
        "detected_language": None,
        "language_probability": None,
        "metadata": make_item_base(item["record"]),
    }


def make_transcript_index_record(
    item: dict[str, Any],
    model_config: dict[str, Any],
) -> dict[str, Any]:
    """Build one curated transcript index record."""
    record = {
        field: item.get(field)
        for field in PRESERVED_METADATA_FIELDS
        if field in item
    }

    record.update(
        {
            "corpus_id": item.get("corpus_id"),
            "audio_file": item.get("input_audio_path") or item.get("audio_file"),
            "transcript_text_file": item.get("text_output_path"),
            "transcript_json_file": item.get("json_output_path"),
            "transcription_status": item.get("status"),
            "transcription_run_id": model_config["run_id"],
            "transcribed_at_utc": item.get("end_time"),
            "transcript_characters": item.get("transcript_characters"),
            "segment_count": item.get("segment_count"),
            "detected_language": item.get("detected_language"),
            "language_probability": item.get("language_probability"),
            "model_name": model_config["model_name"],
            "backend": model_config["backend"],
            "device": model_config["device"],
            "compute_type": model_config["compute_type"],
            "batch_size": model_config["batch_size"],
            "error": item.get("error"),
        }
    )
    return record


def write_transcript_index(
    index_records: list[dict[str, Any]],
    transcript_index_file: Path,
) -> None:
    """
    Write curated NDJSON transcript index for downstream alignment.

    Args:
        index_records: NDJSON-ready transcript index records.
        transcript_index_file: Destination file path.

    Returns:
        None.

    I/O:
        Creates parent directory and overwrites the transcript index file.

    Error behaviour:
        Propagates OSError or JSON serialisation errors.
    """
    transcript_index_file.parent.mkdir(parents=True, exist_ok=True)
    with transcript_index_file.open("w", encoding="utf-8") as handle:
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
        "faster_whisper_version": dependency_info.get("faster_whisper", {}).get("version"),
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
        "audio_index_path": str(args.audio_index),
        "input_dir": str(args.input_dir),
        "output_dir": str(args.output_dir),
        "transcript_index_file": str(args.transcript_index_file),
        "log_file": str(args.log_file),
        "manifest_file": str(args.manifest_file),
        "config": {
            "backend": model_config["backend"],
            "model_name": model_config["model_name"],
            "device": model_config["device"],
            "compute_type": model_config["compute_type"],
            "language": model_config["language"],
            "task": model_config["task"],
            "batch_size": model_config["batch_size"],
            "vad_filter": model_config["vad_filter"],
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
    audio_index_records: int,
    eligible_audio_records: int,
    ignored_audio_records: int,
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
        "audio_index_records": audio_index_records,
        "eligible_audio_records": eligible_audio_records,
        "ignored_audio_records": ignored_audio_records,
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
    Run the batch Jubilee debate transcription workflow.

    Returns:
        Exit code:
            0 for clean completion;
            1 for item-level failures/missing inputs/invalid eligible metadata;
            2 for configuration errors;
            130 for keyboard interruption.

    I/O:
        Reads the audio index, loads WhisperX, transcribes audio, writes
        transcripts, writes transcript index, appends logs, and writes manifests.

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
        logger.info("Audio index: %s", args.audio_index)
        logger.info("Input directory: %s", args.input_dir)
        logger.info("Output directory: %s", args.output_dir)
        logger.info(
            "Model: backend=%s model=%s device=%s compute_type=%s",
            args.backend,
            args.model_name,
            args.device,
            args.compute_type,
        )
        logger.info(
            "Transcription: language=%s task=%s batch_size=%s vad_filter=%s",
            args.language,
            args.task,
            args.batch_size,
            args.vad_filter,
        )
        logger.info("Test mode: %s; test_limit=%s", args.test_mode, args.test_limit)
        logger.info("Reprocess: %s", args.reprocess)
        logger.info("Start corpus ID: %s", args.start_corpus_id)

        dependency_info = check_transcription_dependencies()
        logger.info("Dependency availability: %s", dependency_info)

        cuda_info = check_cuda_available(args.device)
        logger.info(
            "CUDA available: %s; device=%s",
            cuda_info.get("cuda_available"),
            cuda_info.get("cuda_device_name"),
        )

        eligible_records, invalid_records, total_records, ignored_count, ignored_records = (
            load_audio_index(args.audio_index)
        )
        eligible_count = len(eligible_records) + len(invalid_records)

        logger.info(
            "Loaded audio index: input=%s eligible=%s ignored=%s invalid=%s",
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

        planned, skipped_existing, missing_input = plan_transcriptions(
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

        model_config = {
            "backend": args.backend,
            "model_name": args.model_name,
            "device": args.device,
            "compute_type": args.compute_type,
            "language": args.language,
            "task": args.task,
            "batch_size": args.batch_size,
            "vad_filter": args.vad_filter,
            "run_id": run_id,
        }

        for item in skipped_existing:
            manifest_items.append(make_skipped_existing_result(item, model_config, logger))

        for item in missing_input:
            manifest_items.append(make_missing_input_result(item, logger))

        model = None
        if planned:
            logger.info("Loading transcription model %s", args.model_name)
            model = load_transcription_model(
                model_name=args.model_name,
                device=args.device,
                compute_type=args.compute_type,
                backend=args.backend,
            )
            logger.info("Transcription model loaded successfully")
        else:
            logger.info("No planned transcriptions; model loading skipped.")

        for item in planned:
            attempted_count += 1
            manifest_items.append(
                transcribe_one_debate(
                    model=model,
                    item=item,
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

        transcript_index_records = [
            make_transcript_index_record(item, model_config)
            for item in [*manifest_items, *invalid_records]
            if item.get("status")
            in {"success", "failed", "skipped_existing", "missing_input", "failed_metadata"}
        ]
        write_transcript_index(transcript_index_records, args.transcript_index_file)
        logger.info("Wrote transcript index: %s", args.transcript_index_file)

        summary = make_summary(
            audio_index_records=total_records,
            eligible_audio_records=eligible_count,
            ignored_audio_records=ignored_count,
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
                "model_name": args.model_name,
                "device": args.device,
                "compute_type": args.compute_type,
                "language": args.language,
                "task": args.task,
                "batch_size": args.batch_size,
                "vad_filter": args.vad_filter,
                "run_id": run_id,
            }

            summary = make_summary(
                audio_index_records=total_records,
                eligible_audio_records=eligible_count,
                ignored_audio_records=ignored_count,
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