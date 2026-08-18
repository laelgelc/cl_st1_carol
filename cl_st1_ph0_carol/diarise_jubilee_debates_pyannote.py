#!/usr/bin/env python3
"""
Diarise Jubilee debate audio with pyannote.audio.

This script reads a curated Jubilee debate audio index from an NDJSON file,
selects records whose extracted WAV audio is available, and performs speaker
diarisation using pyannote.audio.

Source audio files are resolved from the audio index record's "audio_file" field
when available, or from the audio directory as "<corpus_id>.wav".

Diarisation outputs are written to the output directory as "<corpus_id>.rttm",
"<corpus_id>.diarisation.json", and "<corpus_id>.segments.ndjson". The JSON and
NDJSON outputs preserve anonymous diarised speaker labels such as SPEAKER_00 for
downstream speaker assignment and quality control.

By default, the script runs in test mode and attempts only the first planned
debate. Existing complete diarisation outputs are skipped unless --reprocess is
provided, making the script safe to re-run.

The recommended deployment environment is an x86_64 EC2 GPU instance using a
Python 3.11 conda environment with pyannote.audio, torch, torchaudio, CUDA
support, and Hugging Face authentication. Set HF_TOKEN in the environment before
running if the selected pyannote model requires access authentication.

Use --start-corpus-id to resume planning from a specific debate onward.

This programme performs diarisation only. Transcription, alignment, speaker
assignment, and quality-control reporting are handled by separate pipeline stages.

Example:
    python diarise_jubilee_debates_pyannote.py

Full run:
    python diarise_jubilee_debates_pyannote.py --no-test-mode

Full run from a specific debate:
    python diarise_jubilee_debates_pyannote.py --no-test-mode --start-corpus-id jubilee_surrounded_003
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOOL_NAME = "diarise_jubilee_debates_pyannote.py"
TOOL_VERSION = "v1"

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_AUDIO_INDEX_PATH = (
    "corpus/02_jubilee_debates_audio/"
    "jubilee_debates_audio_index.ndjson"
)
DEFAULT_AUDIO_DIR = "corpus/02_jubilee_debates_audio"
DEFAULT_OUTPUT_DIR = "corpus/05_jubilee_debates_diarisation"
DEFAULT_LOG_FILE = (
    "corpus/05_jubilee_debates_diarisation/"
    "diarise_jubilee_debates_pyannote.log"
)
DEFAULT_MANIFEST_FILE = (
    "corpus/05_jubilee_debates_diarisation/"
    "diarise_jubilee_debates_pyannote_manifest.json"
)
DEFAULT_DIARISATION_INDEX_FILE = (
    "corpus/05_jubilee_debates_diarisation/"
    "jubilee_debates_diarisation_index.ndjson"
)

DEFAULT_BACKEND = "pyannote"
DEFAULT_MODEL_NAME = "pyannote/speaker-diarization-3.1"
DEFAULT_DEVICE = "cuda"
DEFAULT_HF_TOKEN_ENV_VAR = "HF_TOKEN"

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 1
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 14400
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

INPUT_AUDIO_EXTENSION = ".wav"
OUTPUT_RTTM_EXTENSION = ".rttm"
OUTPUT_DIARISATION_JSON_EXTENSION = ".diarisation.json"
OUTPUT_SEGMENTS_NDJSON_EXTENSION = ".segments.ndjson"

ELIGIBLE_AUDIO_EXTRACTION_STATUSES = ("success", "skipped_existing")

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
    "audio_extraction_status",
    "audio_extraction_run_id",
    "audio_extracted_at_utc",
    "audio_codec",
    "audio_sample_rate_hz",
    "audio_sample_rate",
    "audio_channels",
    "audio_duration_seconds",
    "download_status",
    "download_run_id",
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


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the diarisation programme.

    Returns:
        argparse.Namespace containing parsed and path-resolved arguments.

    I/O:
        Reads command-line arguments from sys.argv via argparse.

    Error behaviour:
        argparse exits with code 2 for malformed command-line usage.
    """
    parser = argparse.ArgumentParser(
        description="Diarise extracted Jubilee debate WAV audio with pyannote.audio."
    )

    parser.add_argument("--audio-index", default=DEFAULT_AUDIO_INDEX_PATH)
    parser.add_argument("--audio-dir", default=DEFAULT_AUDIO_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)

    parser.add_argument("--backend", default=DEFAULT_BACKEND, choices=("pyannote",))
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--hf-token-env-var", default=DEFAULT_HF_TOKEN_ENV_VAR)
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=("cuda", "cpu", "auto"))

    parser.add_argument("--num-speakers", type=int, default=None)
    parser.add_argument("--min-speakers", type=int, default=None)
    parser.add_argument("--max-speakers", type=int, default=None)

    test_mode_group = parser.add_mutually_exclusive_group()
    test_mode_group.add_argument("--test-mode", dest="test_mode", action="store_true")
    test_mode_group.add_argument("--no-test-mode", dest="test_mode", action="store_false")
    parser.set_defaults(test_mode=DEFAULT_TEST_MODE)

    parser.add_argument("--test-limit", type=int, default=DEFAULT_TEST_LIMIT)
    parser.add_argument("--reprocess", action="store_true")
    parser.add_argument("--start-corpus-id", default=None)

    parser.add_argument("--log-file", default=DEFAULT_LOG_FILE)
    parser.add_argument("--manifest-file", default=DEFAULT_MANIFEST_FILE)
    parser.add_argument("--diarisation-index-file", default=DEFAULT_DIARISATION_INDEX_FILE)

    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--retry-delay", type=int, default=DEFAULT_RETRY_DELAY_SECONDS)

    args = parser.parse_args()

    args.audio_index = resolve_script_relative_path(Path(args.audio_index))
    args.audio_dir = resolve_script_relative_path(Path(args.audio_dir))
    args.output_dir = resolve_script_relative_path(Path(args.output_dir))
    args.log_file = resolve_script_relative_path(Path(args.log_file))
    args.manifest_file = resolve_script_relative_path(Path(args.manifest_file))
    args.diarisation_index_file = resolve_script_relative_path(
        Path(args.diarisation_index_file)
    )

    return args


def setup_logging(log_file: Path) -> logging.Logger:
    """
    Configure append-only UTF-8 logging.

    Args:
        log_file: Path to the log file.

    Returns:
        Configured programme logger.

    I/O:
        Creates the parent directory if needed and appends to the log file.

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
        Checks paths and creates output/log/manifest parent directories.

    Error behaviour:
        Raises ConfigurationError for validation failures.
    """
    if args.backend != "pyannote":
        raise ConfigurationError("--backend must be 'pyannote'.")

    if not str(args.model).strip():
        raise ConfigurationError("--model must not be blank.")

    if not str(args.device).strip():
        raise ConfigurationError("--device must not be blank.")

    if not str(args.hf_token_env_var).strip():
        raise ConfigurationError("--hf-token-env-var must not be blank.")

    if args.num_speakers is not None and args.num_speakers <= 0:
        raise ConfigurationError("--num-speakers must be a positive integer.")

    if args.min_speakers is not None and args.min_speakers <= 0:
        raise ConfigurationError("--min-speakers must be a positive integer.")

    if args.max_speakers is not None and args.max_speakers <= 0:
        raise ConfigurationError("--max-speakers must be a positive integer.")

    if (
        args.min_speakers is not None
        and args.max_speakers is not None
        and args.min_speakers > args.max_speakers
    ):
        raise ConfigurationError("--min-speakers cannot be greater than --max-speakers.")

    if args.num_speakers is not None and (
        args.min_speakers is not None or args.max_speakers is not None
    ):
        raise ConfigurationError(
            "--num-speakers cannot be combined with --min-speakers or --max-speakers."
        )

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

    if not args.audio_index.exists():
        raise ConfigurationError(f"Audio index file does not exist: {args.audio_index}")

    if not args.audio_index.is_file():
        raise ConfigurationError(f"Audio index path is not a file: {args.audio_index}")

    try:
        with args.audio_index.open("r", encoding="utf-8"):
            pass
    except OSError as exc:
        raise ConfigurationError(
            f"Audio index file is unreadable: {args.audio_index}: {exc}"
        ) from exc

    if not args.audio_dir.exists():
        raise ConfigurationError(f"Audio directory does not exist: {args.audio_dir}")

    if not args.audio_dir.is_dir():
        raise ConfigurationError(f"Audio path is not a directory: {args.audio_dir}")

    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        args.diarisation_index_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create output directories: {exc}") from exc


def check_diarisation_dependencies() -> dict[str, Any]:
    """
    Check required Python package availability.

    Returns:
        Dictionary containing dependency availability and versions.

    I/O:
        Imports required packages and reads installed package metadata.

    Error behaviour:
        Raises ConfigurationError if required packages are missing.
    """
    required_modules = ("torch", "torchaudio", "pyannote.audio", "huggingface_hub")
    info: dict[str, Any] = {"packages": {}}

    for module_name in required_modules:
        try:
            __import__(module_name)
            available = True
            error = None
        except ImportError as exc:
            available = False
            error = str(exc)

        distribution_name = module_name.replace(".", "-")
        if module_name == "pyannote.audio":
            distribution_name = "pyannote.audio"

        try:
            version = importlib.metadata.version(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"

        info["packages"][module_name] = {
            "available": available,
            "version": version,
            "error": error,
        }

    missing = [
        name
        for name, package_info in info["packages"].items()
        if not package_info["available"]
    ]
    if missing:
        raise ConfigurationError(
            "Required Python packages are not installed: " + ", ".join(missing)
        )

    return info


def check_cuda_available(device: str) -> dict[str, Any]:
    """
    Validate CUDA availability when requested.

    Args:
        device: Requested device: cuda, cpu, or auto.

    Returns:
        Dictionary containing CUDA availability and selected device metadata.

    I/O:
        Queries torch CUDA state.

    Error behaviour:
        Raises ConfigurationError if CUDA is explicitly requested but unavailable.
    """
    import torch

    cuda_available = bool(torch.cuda.is_available())
    cuda_device_name = None

    if cuda_available:
        try:
            cuda_device_name = torch.cuda.get_device_name(0)
        except Exception:  # noqa: BLE001 - device name is best-effort metadata
            cuda_device_name = "unknown"

    if device == "cuda" and not cuda_available:
        raise ConfigurationError("--device cuda was requested but CUDA is unavailable.")

    selected_device = "cuda" if device == "auto" and cuda_available else device
    if selected_device == "auto":
        selected_device = "cpu"

    return {
        "requested_device": device,
        "selected_device": selected_device,
        "cuda_available": cuda_available,
        "cuda_device_name": cuda_device_name,
    }


def get_hf_token(env_var_name: str) -> str | None:
    """
    Read Hugging Face token from an environment variable without logging it.

    Args:
        env_var_name: Environment variable name.

    Returns:
        Token string, or None if absent/blank.

    I/O:
        Reads process environment.

    Error behaviour:
        Does not raise.
    """
    token = os.environ.get(env_var_name)
    if token and token.strip():
        return token.strip()
    return None


def make_item_base(record: dict[str, Any]) -> dict[str, Any]:
    """
    Create a metadata-preserving base item dictionary.

    Args:
        record: Source metadata record.

    Returns:
        Dictionary with selected preserved metadata fields.

    I/O:
        None.

    Error behaviour:
        Does not raise for missing optional fields.
    """
    return {field: record.get(field) for field in PRESERVED_METADATA_FIELDS if field in record}


def load_audio_index(
    audio_index_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int, list[dict[str, Any]]]:
    """
    Load and validate eligible audio records from NDJSON.

    Args:
        audio_index_path: Path to the audio index.

    Returns:
        Tuple containing valid eligible records, invalid eligible records, total
        records read, ignored count, and ignored-record manifest entries.

    I/O:
        Reads the NDJSON audio index.

    Error behaviour:
        Raises ConfigurationError for invalid JSON or no eligible records.
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
                    f"Invalid NDJSON object at line {line_number}: expected JSON object."
                )

            status = record.get("audio_extraction_status")
            if status not in ELIGIBLE_AUDIO_EXTRACTION_STATUSES:
                ignored_records.append(
                    make_item_base(record)
                    | {
                        "status": "ignored_audio_unavailable",
                        "diarisation_status": "ignored_audio_unavailable",
                        "line_number": line_number,
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
                        "diarisation_status": "failed_metadata",
                        "line_number": line_number,
                        "error": "Eligible audio-index row is missing non-empty corpus_id.",
                    }
                )
                continue

            eligible_records.append(record)

    if not eligible_records and not invalid_records:
        raise ConfigurationError("No eligible audio records found in audio index.")

    return eligible_records, invalid_records, total_records, len(ignored_records), ignored_records


def resolve_audio_path(record: dict[str, Any], audio_dir: Path) -> Path:
    """
    Resolve source audio path using audio_file or fallback audio directory.

    Args:
        record: One valid eligible audio-index record.
        audio_dir: Fallback directory containing "<corpus_id>.wav" files.

    Returns:
        Preferred audio path.

    I/O:
        Checks whether the audio_file path exists when deciding whether it is usable.

    Error behaviour:
        Raises KeyError if corpus_id is absent after validation.
    """
    audio_file = record.get("audio_file")
    if isinstance(audio_file, str) and audio_file.strip():
        candidate = resolve_script_relative_path(Path(audio_file.strip()))
        if candidate.exists() and candidate.is_file():
            return candidate

    corpus_id = str(record["corpus_id"])
    return audio_dir / f"{corpus_id}{INPUT_AUDIO_EXTENSION}"


def output_paths_for_item(corpus_id: str, output_dir: Path) -> dict[str, Path]:
    """Return all per-debate output paths for one corpus_id without performing I/O."""
    return {
        "rttm_path": output_dir / f"{corpus_id}{OUTPUT_RTTM_EXTENSION}",
        "diarisation_json_path": output_dir / f"{corpus_id}{OUTPUT_DIARISATION_JSON_EXTENSION}",
        "segments_ndjson_path": output_dir / f"{corpus_id}{OUTPUT_SEGMENTS_NDJSON_EXTENSION}",
    }


def outputs_complete(paths: dict[str, Path]) -> bool:
    """Return True when all required diarisation outputs exist as files."""
    return all(path.exists() and path.is_file() for path in paths.values())


def plan_diarisations(
    records: list[dict[str, Any]],
    audio_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_corpus_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Create planned, skipped, and missing-input diarisation records.

    Args:
        records: Valid eligible audio records in input order.
        audio_dir: Fallback directory containing WAV audio.
        output_dir: Destination diarisation output directory.
        test_mode: Whether to limit planned attempts.
        test_limit: Maximum planned attempts in test mode.
        reprocess: Whether to overwrite existing outputs.
        start_corpus_id: Optional corpus_id from which planning should begin.

    Returns:
        Tuple of planned, skipped-existing, and missing-input item dictionaries.

    I/O:
        Checks source audio and output file existence.

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
                f"--start-corpus-id was not found among eligible audio records: {start_corpus_id}"
            )
        records = records[start_index:]

    planned: list[dict[str, Any]] = []
    skipped_existing: list[dict[str, Any]] = []
    missing_input: list[dict[str, Any]] = []

    for record in records:
        corpus_id = str(record["corpus_id"])
        audio_path = resolve_audio_path(record, audio_dir)
        paths = output_paths_for_item(corpus_id, output_dir)

        item = {
            "record": record,
            "corpus_id": corpus_id,
            "input_audio_path": audio_path,
            **paths,
        }

        if not audio_path.exists() or not audio_path.is_file():
            missing_input.append(item)
            continue

        if outputs_complete(paths) and not reprocess:
            skipped_existing.append(item)
            continue

        planned.append(item)

    if test_mode:
        planned = planned[:test_limit]

    return planned, skipped_existing, missing_input


def load_diarisation_pipeline(
    model_name: str,
    device: str,
    hf_token: str | None,
) -> Any:
    """
    Load the pyannote.audio diarisation pipeline.

    Args:
        model_name: Hugging Face model identifier.
        device: Selected execution device.
        hf_token: Optional Hugging Face token.

    Returns:
        Loaded pyannote Pipeline instance.

    I/O:
        May download/load model files and initialise torch device state.

    Error behaviour:
        Raises ConfigurationError when the pipeline cannot be loaded.
    """
    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise ConfigurationError(f"Could not import pyannote.audio or torch: {exc}") from exc

    try:
        try:
            pipeline = Pipeline.from_pretrained(model_name, use_auth_token=hf_token)
        except TypeError:
            pipeline = Pipeline.from_pretrained(model_name, token=hf_token)

        if pipeline is None:
            raise ConfigurationError(
                "pyannote Pipeline.from_pretrained returned None. "
                "Check Hugging Face authentication and model terms."
            )

        if device in {"cuda", "cpu"}:
            pipeline.to(torch.device(device))

        return pipeline
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001 - pyannote raises varied exception types
        message = str(exc)
        if hf_token is not None:
            message = message.replace(hf_token, "[HF_TOKEN_REDACTED]")
        raise ConfigurationError(
            "Could not load pyannote diarisation pipeline. "
            "Check model name, Hugging Face token, accepted model terms, and device. "
            f"Error: {message}"
        ) from exc


def normalise_diarisation_result(raw_diarisation: Any, corpus_id: str) -> list[dict[str, Any]]:
    """
    Normalise pyannote output into project-stable speaker interval records.

    Args:
        raw_diarisation: pyannote Annotation-like result.
        corpus_id: Stable debate identifier.

    Returns:
        List of segment dictionaries.

    I/O:
        None.

    Error behaviour:
        Raises ValueError if the pyannote output cannot be iterated.
    """
    segments: list[dict[str, Any]] = []

    diarisation = raw_diarisation
    if not hasattr(diarisation, "itertracks") and hasattr(
        raw_diarisation,
        "speaker_diarization",
    ):
        diarisation = raw_diarisation.speaker_diarization

    try:
        iterator = diarisation.itertracks(yield_label=True)
    except AttributeError as exc:
        raise ValueError("Diarisation output does not support itertracks.") from exc

    for index, (turn, _track, speaker) in enumerate(iterator, start=1):
        start = round(float(turn.start), 3)
        end = round(float(turn.end), 3)
        duration = round(max(0.0, end - start), 3)

        segments.append(
            {
                "corpus_id": corpus_id,
                "segment_index": index,
                "speaker": str(speaker),
                "start": start,
                "end": end,
                "duration": duration,
                "diarisation_status": "speech",
            }
        )

    if not segments:
        raise ValueError("Diarisation output contained no speaker segments.")

    return segments


def summarise_segments(segments: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise speaker count, segment count, and speech duration without I/O."""
    by_speaker: dict[str, dict[str, Any]] = {}
    total_speech_seconds = 0.0

    for segment in segments:
        speaker = str(segment["speaker"])
        duration = float(segment["duration"])
        total_speech_seconds += duration

        if speaker not in by_speaker:
            by_speaker[speaker] = {
                "speaker": speaker,
                "segment_count": 0,
                "total_speech_seconds": 0.0,
            }

        by_speaker[speaker]["segment_count"] += 1
        by_speaker[speaker]["total_speech_seconds"] = round(
            by_speaker[speaker]["total_speech_seconds"] + duration, 3
        )

    speakers = sorted(by_speaker.values(), key=lambda item: item["speaker"])

    return {
        "speaker_count": len(speakers),
        "segment_count": len(segments),
        "total_speech_seconds": round(total_speech_seconds, 3),
        "speakers": speakers,
    }


def write_rttm(
    speaker_segments: list[dict[str, Any]],
    rttm_path: Path,
    corpus_id: str,
) -> None:
    """
    Write speaker diarisation as RTTM.

    Args:
        speaker_segments: Normalised diarisation intervals.
        rttm_path: Destination RTTM path.
        corpus_id: Stable debate identifier used as RTTM file ID.

    Returns:
        None.

    I/O:
        Creates parent directory and writes the RTTM file.

    Error behaviour:
        Propagates OSError.
    """
    rttm_path.parent.mkdir(parents=True, exist_ok=True)

    with rttm_path.open("w", encoding="utf-8") as handle:
        for segment in speaker_segments:
            handle.write(
                "SPEAKER "
                f"{corpus_id} "
                "1 "
                f"{float(segment['start']):.3f} "
                f"{float(segment['duration']):.3f} "
                "<NA> <NA> "
                f"{segment['speaker']} "
                "<NA> <NA>\n"
            )


def write_diarisation_outputs(
    diarisation_json: dict[str, Any],
    speaker_segments: list[dict[str, Any]],
    diarisation_json_path: Path,
    segments_ndjson_path: Path,
) -> None:
    """
    Write diarisation JSON and segment-level NDJSON outputs.

    Args:
        diarisation_json: JSON-serialisable per-debate diarisation document.
        speaker_segments: Normalised diarisation intervals.
        diarisation_json_path: Destination JSON path.
        segments_ndjson_path: Destination NDJSON path.

    Returns:
        None.

    I/O:
        Creates parent directories and writes JSON/NDJSON files.

    Error behaviour:
        Propagates OSError and JSON serialisation errors.
    """
    diarisation_json_path.parent.mkdir(parents=True, exist_ok=True)
    segments_ndjson_path.parent.mkdir(parents=True, exist_ok=True)

    diarisation_json_path.write_text(
        json.dumps(diarisation_json, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    with segments_ndjson_path.open("w", encoding="utf-8") as handle:
        for segment in speaker_segments:
            handle.write(json.dumps(segment, ensure_ascii=False, sort_keys=False) + "\n")


def call_pipeline(
    pipeline: Any,
    audio_path: Path,
    num_speakers: int | None,
    min_speakers: int | None,
    max_speakers: int | None,
) -> Any:
    """Call pyannote pipeline with only non-null speaker-count constraints."""
    kwargs: dict[str, Any] = {}
    if num_speakers is not None:
        kwargs["num_speakers"] = num_speakers
    if min_speakers is not None:
        kwargs["min_speakers"] = min_speakers
    if max_speakers is not None:
        kwargs["max_speakers"] = max_speakers

    return pipeline(str(audio_path), **kwargs)


def diarise_one_debate(
    item: dict[str, Any],
    pipeline: Any,
    model_config: dict[str, Any],
    max_retries: int,
    retry_delay: int,
    logger: logging.Logger,
) -> dict[str, Any]:
    """
    Diarise one debate audio file and return a structured result.

    Args:
        item: Planned item dictionary.
        pipeline: Loaded pyannote pipeline.
        model_config: Backend/model/device/speaker-count configuration.
        max_retries: Number of retries after the initial failed attempt.
        retry_delay: Delay between failed attempts in seconds.
        logger: Configured programme logger.

    Returns:
        Structured per-item manifest result.

    I/O:
        Runs model inference and writes RTTM, JSON, and NDJSON outputs.

    Error behaviour:
        Does not raise for per-item diarisation failures; returns status "failed".
    """
    corpus_id = item["corpus_id"]
    audio_path = item["input_audio_path"]
    rttm_path = item["rttm_path"]
    diarisation_json_path = item["diarisation_json_path"]
    segments_ndjson_path = item["segments_ndjson_path"]

    start_time = utc_timestamp()
    monotonic_start = time.monotonic()
    attempts: list[dict[str, Any]] = []
    retries_used = 0
    total_attempts = max_retries + 1
    final_error: str | None = None

    for attempt_number in range(1, total_attempts + 1):
        attempt_start = utc_timestamp()
        attempt_monotonic_start = time.monotonic()

        try:
            logger.info("Diarisation attempt %s/%s for %s", attempt_number, total_attempts, corpus_id)

            raw_diarisation = call_pipeline(
                pipeline=pipeline,
                audio_path=audio_path,
                num_speakers=model_config.get("num_speakers"),
                min_speakers=model_config.get("min_speakers"),
                max_speakers=model_config.get("max_speakers"),
            )

            speaker_segments = normalise_diarisation_result(raw_diarisation, corpus_id)
            segment_summary = summarise_segments(speaker_segments)

            diarisation_json = {
                "corpus_id": corpus_id,
                "input_audio_path": str(audio_path),
                "rttm_path": str(rttm_path),
                "diarisation_json_path": str(diarisation_json_path),
                "segments_ndjson_path": str(segments_ndjson_path),
                "diarisation_model": model_config,
                "diarisation": segment_summary | {
                    "segments": [
                        {
                            key: value
                            for key, value in segment.items()
                            if key != "corpus_id"
                        }
                        for segment in speaker_segments
                    ]
                },
                "metadata": make_item_base(item["record"]),
                "run": {
                    "diarisation_run_id": model_config["run_id"],
                    "diarised_at_utc": utc_timestamp(),
                },
                "status": "success",
                "error": None,
            }

            write_rttm(speaker_segments, rttm_path, corpus_id)
            write_diarisation_outputs(
                diarisation_json=diarisation_json,
                speaker_segments=speaker_segments,
                diarisation_json_path=diarisation_json_path,
                segments_ndjson_path=segments_ndjson_path,
            )

            duration = round(time.monotonic() - monotonic_start, 3)
            end_time = utc_timestamp()

            attempts.append(
                {
                    "attempt": attempt_number,
                    "start_time": attempt_start,
                    "end_time": end_time,
                    "duration_seconds": round(time.monotonic() - attempt_monotonic_start, 3),
                    "error": None,
                }
            )

            logger.info(
                "SUCCESS %s speakers=%s segments=%s speech_seconds=%s",
                corpus_id,
                segment_summary["speaker_count"],
                segment_summary["segment_count"],
                segment_summary["total_speech_seconds"],
            )

            return make_item_base(item["record"]) | {
                "corpus_id": corpus_id,
                "input_audio_path": str(audio_path),
                "rttm_path": str(rttm_path),
                "diarisation_json_path": str(diarisation_json_path),
                "segments_ndjson_path": str(segments_ndjson_path),
                "status": "success",
                "error": None,
                "retries": retries_used,
                "duration_seconds": duration,
                "start_time": start_time,
                "end_time": end_time,
                "detected_speaker_count": segment_summary["speaker_count"],
                "diarised_segment_count": segment_summary["segment_count"],
                "total_speech_seconds": segment_summary["total_speech_seconds"],
                "metadata": make_item_base(item["record"]),
                "attempts": attempts,
            }

        except Exception as exc:  # noqa: BLE001 - per-item resiliency required
            final_error = str(exc)
            logger.error("FAILED attempt %s for %s: %s", attempt_number, corpus_id, final_error)

            attempts.append(
                {
                    "attempt": attempt_number,
                    "start_time": attempt_start,
                    "end_time": utc_timestamp(),
                    "duration_seconds": round(time.monotonic() - attempt_monotonic_start, 3),
                    "error": final_error,
                }
            )

            if attempt_number < total_attempts:
                retries_used += 1
                logger.info("Retrying %s after %s seconds", corpus_id, retry_delay)
                if retry_delay:
                    time.sleep(retry_delay)

    return make_item_base(item["record"]) | {
        "corpus_id": corpus_id,
        "input_audio_path": str(audio_path),
        "rttm_path": str(rttm_path),
        "diarisation_json_path": str(diarisation_json_path),
        "segments_ndjson_path": str(segments_ndjson_path),
        "status": "failed",
        "error": final_error or "Diarisation failed.",
        "retries": retries_used,
        "duration_seconds": round(time.monotonic() - monotonic_start, 3),
        "start_time": start_time,
        "end_time": utc_timestamp(),
        "detected_speaker_count": None,
        "diarised_segment_count": None,
        "total_speech_seconds": None,
        "metadata": make_item_base(item["record"]),
        "attempts": attempts,
    }


def make_missing_input_result(item: dict[str, Any], logger: logging.Logger) -> dict[str, Any]:
    """Create and log a missing-input manifest item."""
    error = f"Source audio file is missing: {item['input_audio_path']}"
    logger.error("MISSING_INPUT %s: %s", item["corpus_id"], item["input_audio_path"])

    return make_item_base(item["record"]) | {
        "corpus_id": item["corpus_id"],
        "input_audio_path": str(item["input_audio_path"]),
        "rttm_path": str(item["rttm_path"]),
        "diarisation_json_path": str(item["diarisation_json_path"]),
        "segments_ndjson_path": str(item["segments_ndjson_path"]),
        "status": "missing_input",
        "error": error,
        "retries": 0,
        "duration_seconds": None,
        "start_time": None,
        "end_time": None,
        "detected_speaker_count": None,
        "diarised_segment_count": None,
        "total_speech_seconds": None,
        "metadata": make_item_base(item["record"]),
    }


def make_skipped_existing_result(item: dict[str, Any], logger: logging.Logger) -> dict[str, Any]:
    """Create and log a skipped-existing manifest item."""
    logger.info("SKIPPED_EXISTING %s", item["corpus_id"])

    summary = read_existing_diarisation_summary(item["diarisation_json_path"])

    return make_item_base(item["record"]) | {
        "corpus_id": item["corpus_id"],
        "input_audio_path": str(item["input_audio_path"]),
        "rttm_path": str(item["rttm_path"]),
        "diarisation_json_path": str(item["diarisation_json_path"]),
        "segments_ndjson_path": str(item["segments_ndjson_path"]),
        "status": "skipped_existing",
        "error": None,
        "retries": 0,
        "duration_seconds": 0,
        "start_time": None,
        "end_time": None,
        "detected_speaker_count": summary.get("speaker_count"),
        "diarised_segment_count": summary.get("segment_count"),
        "total_speech_seconds": summary.get("total_speech_seconds"),
        "metadata": make_item_base(item["record"]),
    }


def read_existing_diarisation_summary(diarisation_json_path: Path) -> dict[str, Any]:
    """Read summary fields from an existing diarisation JSON file on a best-effort basis."""
    try:
        data = json.loads(diarisation_json_path.read_text(encoding="utf-8"))
        diarisation = data.get("diarisation", {})
        if isinstance(diarisation, dict):
            return {
                "speaker_count": diarisation.get("speaker_count"),
                "segment_count": diarisation.get("segment_count"),
                "total_speech_seconds": diarisation.get("total_speech_seconds"),
            }
    except Exception:
        pass

    return {
        "speaker_count": None,
        "segment_count": None,
        "total_speech_seconds": None,
    }


def make_diarisation_index_record(
    item_result: dict[str, Any],
    run_id: str,
    diarised_at_utc: str,
    model_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Build one curated diarisation index record.

    Args:
        item_result: Manifest item result.
        run_id: Current run ID.
        diarised_at_utc: End-of-run timestamp.
        model_config: Diarisation backend/model/device configuration.

    Returns:
        NDJSON-ready diarisation index record.

    I/O:
        None.

    Error behaviour:
        Does not raise for missing optional metadata.
    """
    source_metadata = item_result.get("metadata")
    if not isinstance(source_metadata, dict):
        source_metadata = {}

    record = {
        field: source_metadata.get(field, item_result.get(field))
        for field in PRESERVED_METADATA_FIELDS
        if field in source_metadata or field in item_result
    }

    record.update(
        {
            "corpus_id": item_result.get("corpus_id"),
            "audio_file": item_result.get("input_audio_path") or item_result.get("audio_file"),
            "rttm_file": item_result.get("rttm_path"),
            "diarisation_json_file": item_result.get("diarisation_json_path"),
            "segments_ndjson_file": item_result.get("segments_ndjson_path"),
            "diarisation_status": item_result.get("status"),
            "diarisation_run_id": run_id,
            "diarised_at_utc": item_result.get("end_time") or diarised_at_utc,
            "diarisation_backend": model_config.get("backend"),
            "diarisation_model_name": model_config.get("model_name"),
            "diarisation_device": model_config.get("device"),
            "num_speakers": model_config.get("num_speakers"),
            "min_speakers": model_config.get("min_speakers"),
            "max_speakers": model_config.get("max_speakers"),
            "detected_speaker_count": item_result.get("detected_speaker_count"),
            "diarised_segment_count": item_result.get("diarised_segment_count"),
            "total_speech_seconds": item_result.get("total_speech_seconds"),
            "diarisation_runtime_seconds": item_result.get("duration_seconds"),
            "error": item_result.get("error"),
        }
    )

    return record


def write_diarisation_index(
    index_records: list[dict[str, Any]],
    diarisation_index_file: Path,
) -> None:
    """
    Write curated NDJSON diarisation index.

    Args:
        index_records: JSON-serialisable index records.
        diarisation_index_file: Destination NDJSON path.

    Returns:
        None.

    I/O:
        Creates parent directory and overwrites the NDJSON file.

    Error behaviour:
        Propagates OSError and JSON serialisation errors.
    """
    diarisation_index_file.parent.mkdir(parents=True, exist_ok=True)
    with diarisation_index_file.open("w", encoding="utf-8") as handle:
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

    per_run_manifest_file = (
        manifest_file.parent / f"{manifest_file.stem}_{run_id}{manifest_file.suffix}"
    )

    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False)
    manifest_file.write_text(manifest_json + "\n", encoding="utf-8")
    per_run_manifest_file.write_text(manifest_json + "\n", encoding="utf-8")

    return manifest_file, per_run_manifest_file


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
    """Create a manifest summary dictionary without performing I/O."""
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


def build_environment_metadata(
    dependency_info: dict[str, Any] | None,
    cuda_info: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build environment metadata for the manifest."""
    packages = (dependency_info or {}).get("packages", {})

    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cuda_available": (cuda_info or {}).get("cuda_available"),
        "cuda_device_name": (cuda_info or {}).get("cuda_device_name"),
        "torch_version": packages.get("torch", {}).get("version", "unknown"),
        "torch_cuda_version": get_torch_cuda_version(),
        "torchaudio_version": packages.get("torchaudio", {}).get("version", "unknown"),
        "pyannote_audio_version": packages.get("pyannote.audio", {}).get("version", "unknown"),
        "huggingface_hub_version": packages.get("huggingface_hub", {}).get("version", "unknown"),
    }


def get_torch_cuda_version() -> str | None:
    """Return torch.version.cuda on a best-effort basis."""
    try:
        import torch

        return torch.version.cuda
    except Exception:
        return None


def build_run_metadata(
    args: argparse.Namespace,
    run_id: str,
    start_time: str,
    end_time: str | None,
    summary: dict[str, int],
    environment: dict[str, Any],
    selected_device: str | None,
    hf_token_present: bool,
    interrupted: bool = False,
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
        "audio_index_path": str(args.audio_index),
        "audio_dir": str(args.audio_dir),
        "output_dir": str(args.output_dir),
        "diarisation_index_file": str(args.diarisation_index_file),
        "log_file": str(args.log_file),
        "manifest_file": str(args.manifest_file),
        "config": {
            "backend": args.backend,
            "model_name": args.model,
            "device": selected_device or args.device,
            "requested_device": args.device,
            "num_speakers": args.num_speakers,
            "min_speakers": args.min_speakers,
            "max_speakers": args.max_speakers,
            "timeout_seconds": args.timeout,
            "max_retries": args.max_retries,
            "retry_delay_seconds": args.retry_delay,
            "start_corpus_id": args.start_corpus_id,
            "hf_token_env_var": args.hf_token_env_var,
            "huggingface_token_present": hf_token_present,
        },
        "environment": environment,
        "summary": summary,
        "interrupted": interrupted,
    }


def main() -> int:
    """
    Run the batch Jubilee debate diarisation workflow and return an exit code.

    Returns:
        0 for clean completion; 1 for item-level failures/missing/invalid metadata;
        2 for configuration errors; 130 for keyboard interruption.

    I/O:
        Reads the audio index, checks filesystem state, loads pyannote, performs
        diarisation, appends logs, writes outputs, writes an index, and writes manifests.

    Error behaviour:
        Handles expected configuration, per-item, and interrupt errors.
    """
    logger: logging.Logger | None = None
    args: argparse.Namespace | None = None

    run_id = make_run_id()
    start_time = utc_timestamp()
    end_time: str | None = None

    dependency_info: dict[str, Any] | None = None
    cuda_info: dict[str, Any] | None = None
    selected_device: str | None = None
    hf_token_present = False

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
        logger.info("Audio directory: %s", args.audio_dir)
        logger.info("Output directory: %s", args.output_dir)
        logger.info("Backend: %s", args.backend)
        logger.info("Model: %s", args.model)
        logger.info("Requested device: %s", args.device)
        logger.info(
            "Speaker constraints: num=%s min=%s max=%s",
            args.num_speakers,
            args.min_speakers,
            args.max_speakers,
        )
        logger.info("Test mode: %s; test_limit=%s", args.test_mode, args.test_limit)
        logger.info("Reprocess: %s", args.reprocess)
        logger.info("Start corpus ID: %s", args.start_corpus_id)

        dependency_info = check_diarisation_dependencies()
        logger.info("Dependency check complete.")

        cuda_info = check_cuda_available(args.device)
        selected_device = cuda_info["selected_device"]
        logger.info(
            "CUDA available=%s selected_device=%s cuda_device_name=%s",
            cuda_info["cuda_available"],
            selected_device,
            cuda_info["cuda_device_name"],
        )

        hf_token = get_hf_token(args.hf_token_env_var)
        hf_token_present = hf_token is not None
        logger.info("Hugging Face token present: %s", hf_token_present)

        eligible_records, invalid_records, total_records, ignored_count, ignored_records = load_audio_index(
            args.audio_index
        )
        eligible_count = len(eligible_records) + len(invalid_records)

        logger.info(
            "Loaded audio index: total=%s eligible=%s ignored=%s invalid=%s",
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

        planned, skipped_existing, missing_input = plan_diarisations(
            records=eligible_records,
            audio_dir=args.audio_dir,
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

        model_config = {
            "backend": args.backend,
            "model_name": args.model,
            "device": selected_device,
            "num_speakers": args.num_speakers,
            "min_speakers": args.min_speakers,
            "max_speakers": args.max_speakers,
            "run_id": run_id,
        }

        pipeline = None
        if planned:
            logger.info("Loading pyannote pipeline.")
            pipeline = load_diarisation_pipeline(
                model_name=args.model,
                device=selected_device,
                hf_token=hf_token,
            )
            logger.info("Loaded pyannote pipeline successfully.")
        else:
            logger.info("No planned diarisation jobs; pipeline loading skipped.")

        for item in planned:
            attempted_count += 1
            result = diarise_one_debate(
                item=item,
                pipeline=pipeline,
                model_config=model_config,
                max_retries=args.max_retries,
                retry_delay=args.retry_delay,
                logger=logger,
            )
            manifest_items.append(result)

        end_time = utc_timestamp()

        succeeded = sum(1 for item in manifest_items if item.get("status") == "success")
        failed = sum(1 for item in manifest_items if item.get("status") == "failed")
        missing_count = sum(1 for item in manifest_items if item.get("status") == "missing_input")
        skipped_count = sum(1 for item in manifest_items if item.get("status") == "skipped_existing")

        index_records = [
            make_diarisation_index_record(item, run_id, end_time, model_config)
            for item in [*manifest_items, *invalid_records]
            if item.get("status")
            in {"success", "failed", "skipped_existing", "missing_input", "failed_metadata"}
        ]

        write_diarisation_index(index_records, args.diarisation_index_file)
        logger.info("Wrote diarisation index: %s", args.diarisation_index_file)

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

        environment = build_environment_metadata(dependency_info, cuda_info)

        manifest = {
            "run_metadata": build_run_metadata(
                args=args,
                run_id=run_id,
                start_time=start_time,
                end_time=end_time,
                summary=summary,
                environment=environment,
                selected_device=selected_device,
                hf_token_present=hf_token_present,
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
            end_time = utc_timestamp()
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
                    end_time=end_time,
                    summary=summary,
                    environment=build_environment_metadata(dependency_info, cuda_info),
                    selected_device=selected_device,
                    hf_token_present=hf_token_present,
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