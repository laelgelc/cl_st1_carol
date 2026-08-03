#!/usr/bin/env python3
"""
Submit Jubilee debate FLAC audio files to Gemini for speaker-diarised transcription.

The programme reads a Markdown prompt template, loads GEMINI_API_KEY from env/.env
using python-dotenv, reads a Gemini-ready FLAC audio index, and submits one audio
file per planned debate to Gemini with a neutral metadata note.

Default paths are resolved relative to the directory containing this script.
Explicit relative CLI paths are resolved relative to the current working directory.

Exit codes:
    0    Completed with no failures
    1    Completed, but one or more per-debate failures occurred
    2    Global configuration or validation error
    130  Interrupted by user
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOOL_NAME = "speaker_diarisation_jubilee_debates.py"
TOOL_VERSION = "v1"

PROGRAMME_DIR = Path(__file__).resolve().parent
CWD = Path.cwd()

DEFAULT_PROMPT_TEMPLATE = "speaker_diarisation_prompts/speaker_diarisation_v1.md"
DEFAULT_ENV_FILE = "env/.env"
DEFAULT_AUDIO_DIR = "corpus/02_jubilee_debates_audio/gemini_flac"
DEFAULT_AUDIO_INDEX = "corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson"
DEFAULT_DEBATE_INDEX = "corpus/01_jubilee_debates/jubilee_debates_index.ndjson"
DEFAULT_OUTPUT_DIR = "corpus/03_jubilee_debates_speaker_diarisation"

#DEFAULT_MODEL = "gemini-3.1-pro"
DEFAULT_MODEL = gemini-3.1-pro-preview
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_OUTPUT_TOKENS = 0
DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 1
DEFAULT_WORKERS = 1
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 5.0

SUPPORTED_AUDIO_EXTENSIONS = {".flac"}

PATH_RESOLUTION_POLICY = {
    "default_paths": "resolved_relative_to_programme_directory",
    "cli_relative_paths": "resolved_relative_to_current_working_directory",
    "absolute_paths": "used_as_given",
}


class ConfigurationError(Exception):
    """Raised for global validation/configuration failures."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_timestamp() -> str:
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def make_run_id() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def path_to_str(path: Path | None) -> str | None:
    return None if path is None else path.as_posix()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def json_safe_error(exc: BaseException) -> str:
    return f"{exc.__class__.__name__}: {exc}"


def resolve_path(path: Path, source: str) -> Path:
    """
    Resolve paths according to the programme policy.

    Defaults resolve under PROGRAMME_DIR.
    Explicit CLI relatives resolve under CWD.
    Absolutes are used as given.
    """
    if path.is_absolute():
        return path
    if source == "default":
        return PROGRAMME_DIR / path
    return CWD / path


def path_meta(path: Path, source: str) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "resolved_path": resolve_path(path, source).resolve().as_posix(),
        "path_source": source,
    }


def was_supplied(flag: str) -> bool:
    return flag in sys.argv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit Jubilee debate FLAC audio to Gemini for speaker diarisation."
    )

    parser.add_argument("--prompt-template", type=Path, default=Path(DEFAULT_PROMPT_TEMPLATE))
    parser.add_argument("--env-file", type=Path, default=Path(DEFAULT_ENV_FILE))
    parser.add_argument("--audio-dir", type=Path, default=Path(DEFAULT_AUDIO_DIR))
    parser.add_argument("--audio-index", type=Path, default=Path(DEFAULT_AUDIO_INDEX))
    parser.add_argument("--debate-index", type=Path, default=Path(DEFAULT_DEBATE_INDEX))
    parser.add_argument("--output-dir", type=Path, default=Path(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)

    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument("--test-mode", dest="test_mode", action="store_true")
    test_group.add_argument("--no-test-mode", dest="test_mode", action="store_false")
    parser.set_defaults(test_mode=DEFAULT_TEST_MODE)

    parser.add_argument("--test-limit", type=int, default=DEFAULT_TEST_LIMIT)
    parser.add_argument("--start-corpus-id", default=None)
    parser.add_argument("--only-corpus-id", default=None)
    parser.add_argument("--reprocess", action="store_true")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=DEFAULT_RETRY_BACKOFF_SECONDS,
    )
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument("--manifest-file", type=Path, default=None)

    args = parser.parse_args()

    sources = {
        "prompt_template": "cli" if was_supplied("--prompt-template") else "default",
        "env_file": "cli" if was_supplied("--env-file") else "default",
        "audio_dir": "cli" if was_supplied("--audio-dir") else "default",
        "audio_index": "cli" if was_supplied("--audio-index") else "default",
        "debate_index": "cli" if was_supplied("--debate-index") else "default",
        "output_dir": "cli" if was_supplied("--output-dir") else "default",
        "log_file": "cli" if was_supplied("--log-file") else "default",
        "manifest_file": "cli" if was_supplied("--manifest-file") else "default",
    }

    args.path_sources = sources

    args.prompt_template_supplied = args.prompt_template
    args.env_file_supplied = args.env_file
    args.audio_dir_supplied = args.audio_dir
    args.audio_index_supplied = args.audio_index
    args.debate_index_supplied = args.debate_index
    args.output_dir_supplied = args.output_dir

    args.prompt_template = resolve_path(args.prompt_template, sources["prompt_template"])
    args.env_file = resolve_path(args.env_file, sources["env_file"])
    args.audio_dir = resolve_path(args.audio_dir, sources["audio_dir"])
    args.audio_index = resolve_path(args.audio_index, sources["audio_index"])
    args.debate_index = resolve_path(args.debate_index, sources["debate_index"])
    args.output_dir = resolve_path(args.output_dir, sources["output_dir"])

    if args.log_file is None:
        args.log_file_supplied = Path(DEFAULT_OUTPUT_DIR) / "speaker_diarisation_jubilee_debates.log"
        args.log_file = args.output_dir / "speaker_diarisation_jubilee_debates.log"
    else:
        args.log_file_supplied = args.log_file
        args.log_file = resolve_path(args.log_file, sources["log_file"])

    if args.manifest_file is None:
        args.manifest_file_supplied = Path(DEFAULT_OUTPUT_DIR) / "speaker_diarisation_jubilee_debates_manifest.json"
        args.manifest_file = args.output_dir / "speaker_diarisation_jubilee_debates_manifest.json"
    else:
        args.manifest_file_supplied = args.manifest_file
        args.manifest_file = resolve_path(args.manifest_file, sources["manifest_file"])

    return args


def setup_logging(log_file: Path) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(TOOL_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    formatter.converter = time.gmtime

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def validate_numeric_args(args: argparse.Namespace) -> None:
    if args.test_limit <= 0:
        raise ConfigurationError("--test-limit must be greater than zero")
    if args.workers <= 0:
        raise ConfigurationError("--workers must be greater than zero")
    if args.workers != 1:
        raise ConfigurationError("Only --workers 1 is supported in this implementation")
    if args.max_output_tokens < 0:
        raise ConfigurationError("--max-output-tokens must be zero or greater")
    if args.temperature < 0:
        raise ConfigurationError("--temperature must be zero or greater")
    if args.max_retries < 0:
        raise ConfigurationError("--max-retries must be zero or greater")
    if args.retry_backoff_seconds < 0:
        raise ConfigurationError("--retry-backoff-seconds must be zero or greater")


def load_environment(args: argparse.Namespace) -> dict[str, Any]:
    if not args.env_file.exists():
        raise ConfigurationError(f"Environment file does not exist: {args.env_file}")

    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise ConfigurationError(
            "python-dotenv is unavailable. Install it with: pip install python-dotenv"
        ) from exc

    loaded = load_dotenv(args.env_file)
    api_key = os.environ.get("GEMINI_API_KEY")

    if api_key is None or not api_key.strip():
        raise ConfigurationError("GEMINI_API_KEY is missing or empty after loading the environment file")

    return {
        "env_file": {
            "supplied_path": args.env_file_supplied.as_posix(),
            "resolved_path": args.env_file.resolve().as_posix(),
            "path_source": args.path_sources["env_file"],
        },
        "dotenv_loaded": bool(loaded),
        "gemini_api_key_present": True,
        "gemini_api_key_logged": False,
    }


def validate_gemini_sdk() -> Any:
    try:
        from google import genai
    except ImportError as exc:
        raise ConfigurationError(
            "Google Gemini Python SDK is unavailable. Install it with: pip install google-genai"
        ) from exc

    return genai


def load_prompt_template(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    if not args.prompt_template.exists():
        raise ConfigurationError(f"Prompt template file does not exist: {args.prompt_template}")
    if not args.prompt_template.is_file():
        raise ConfigurationError(f"Prompt template path is not a file: {args.prompt_template}")

    try:
        text = args.prompt_template.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"Prompt template cannot be read: {args.prompt_template}") from exc

    if not text.strip():
        raise ConfigurationError(f"Prompt template file is empty: {args.prompt_template}")

    metadata = {
        "supplied_path": args.prompt_template_supplied.as_posix(),
        "resolved_path": args.prompt_template.resolve().as_posix(),
        "path_source": args.path_sources["prompt_template"],
        "sha256": sha256_text(text),
        "character_count": len(text),
    }
    return text, metadata


def load_ndjson_required(path: Path, label: str) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        raise ConfigurationError(f"{label} path does not exist: {path}")
    if not path.is_file():
        raise ConfigurationError(f"{label} path is not a file: {path}")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    line_count = 0

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            line_count += 1

            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ConfigurationError(f"Invalid JSON in {label} on line {line_number}: {exc}") from exc

            if not isinstance(row, dict):
                raise ConfigurationError(f"{label} line {line_number} is not a JSON object")

            corpus_id = str(row.get("corpus_id", "")).strip()
            if not corpus_id:
                raise ConfigurationError(f"{label} line {line_number} lacks corpus_id")

            if corpus_id in seen:
                raise ConfigurationError(f"Duplicate corpus_id in {label}: {corpus_id}")

            seen.add(corpus_id)
            row["_line_number"] = line_number
            rows.append(row)

    if not rows:
        raise ConfigurationError(f"{label} is empty: {path}")

    return rows, line_count


def load_optional_debate_index(path: Path) -> tuple[dict[str, dict[str, Any]], bool]:
    if not path.exists():
        return {}, False

    rows, _ = load_ndjson_required(path, "debate index")
    return {str(row["corpus_id"]): row for row in rows}, True


def validate_global_inputs(args: argparse.Namespace) -> None:
    if not args.audio_dir.exists():
        raise ConfigurationError(f"Audio directory does not exist: {args.audio_dir}")
    if not args.audio_dir.is_dir():
        raise ConfigurationError(f"Audio path is not a directory: {args.audio_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with args.log_file.open("a", encoding="utf-8"):
            pass
    except OSError as exc:
        raise ConfigurationError(f"Log file cannot be created: {args.log_file}") from exc

    try:
        args.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        with args.manifest_file.open("a", encoding="utf-8"):
            pass
    except OSError as exc:
        raise ConfigurationError(f"Manifest destination cannot be written: {args.manifest_file}") from exc


def apply_plan_filters(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    plan = rows

    if args.start_corpus_id:
        start_index = next(
            (idx for idx, row in enumerate(plan) if row["corpus_id"] == args.start_corpus_id),
            None,
        )
        if start_index is None:
            raise ConfigurationError(f"--start-corpus-id not found in processing plan: {args.start_corpus_id}")
        plan = plan[start_index:]

    if args.only_corpus_id:
        if not any(row["corpus_id"] == args.only_corpus_id for row in plan):
            raise ConfigurationError(f"--only-corpus-id not found in processing plan: {args.only_corpus_id}")
        plan = [row for row in plan if row["corpus_id"] == args.only_corpus_id]

    if args.test_mode:
        plan = plan[: args.test_limit]

    return plan


def output_paths(corpus_id: str, args: argparse.Namespace) -> tuple[Path, Path]:
    return args.output_dir / f"{corpus_id}.txt", args.output_dir / f"{corpus_id}.json"


def existing_success(txt_path: Path, json_path: Path) -> tuple[bool, dict[str, Any]]:
    if not txt_path.exists() or not json_path.exists():
        return False, {}

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, {}

    return data.get("status") == "success", data


def build_metadata_note(
        corpus_id: str,
        audio_file: Path,
        audio_row: dict[str, Any],
        debate_row: dict[str, Any] | None,
) -> str:
    title = None
    debate_format = None
    youtube_id = None

    if debate_row:
        title = debate_row.get("title_selected") or debate_row.get("title_extracted")
        debate_format = debate_row.get("debate_format")
        youtube_id = debate_row.get("youtube_id")

    title = title or audio_row.get("title_selected") or audio_row.get("title_extracted")
    debate_format = debate_format or audio_row.get("debate_format")
    youtube_id = youtube_id or audio_row.get("youtube_id")

    lines = [
        "Debate audio metadata:",
        f"Corpus ID: {corpus_id}",
    ]

    if title:
        lines.append(f"Title: {title}")
    if debate_format:
        lines.append(f"Debate format: {debate_format}")
    if youtube_id:
        lines.append(f"YouTube ID: {youtube_id}")

    lines.extend(
        [
            f"Audio file: {audio_file.name}",
            "",
            "Please apply the transcription and speaker-diarisation instructions above to the attached audio file.",
        ]
    )

    return "\n".join(lines)


def build_request_text(prompt_template: str, metadata_note: str) -> str:
    return f"{prompt_template.rstrip()}\n\n{metadata_note.strip()}\n"


def extract_response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip() + "\n"

    candidates = getattr(response, "candidates", None)
    if candidates:
        parts_text: list[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if parts:
                for part in parts:
                    part_text = getattr(part, "text", None)
                    if isinstance(part_text, str):
                        parts_text.append(part_text)
        joined = "\n".join(parts_text).strip()
        if joined:
            return joined + "\n"

    return ""


def response_api_metadata(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage_metadata", None)
    candidates = getattr(response, "candidates", None)

    finish_reason = None
    safety_ratings = []

    if candidates:
        first = candidates[0]
        finish_reason = str(getattr(first, "finish_reason", None))
        ratings = getattr(first, "safety_ratings", None)
        if ratings:
            safety_ratings = [str(rating) for rating in ratings]

    return {
        "response_id": getattr(response, "response_id", None),
        "usage_metadata": str(usage) if usage is not None else {},
        "finish_reason": finish_reason,
        "safety_ratings": safety_ratings,
    }


def call_gemini(
        genai_module: Any,
        api_key: str,
        model: str,
        request_text: str,
        audio_path: Path,
        temperature: float,
        max_output_tokens: int,
        max_retries: int,
        retry_backoff_seconds: float,
        logger: logging.Logger,
        corpus_id: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    client = genai_module.Client(api_key=api_key)

    generation_config: dict[str, Any] = {"temperature": temperature}
    if max_output_tokens > 0:
        generation_config["max_output_tokens"] = max_output_tokens

    retry_errors: list[dict[str, Any]] = []
    attempts = 0
    uploaded_metadata: dict[str, Any] = {}

    for attempt in range(1, max_retries + 2):
        attempts = attempt
        try:
            logger.info("Uploading audio for %s attempt=%s", corpus_id, attempt)
            uploaded_file = client.files.upload(file=str(audio_path))

            uploaded_metadata = {
                "name": getattr(uploaded_file, "name", None),
                "uri": getattr(uploaded_file, "uri", None),
                "mime_type": getattr(uploaded_file, "mime_type", None),
                "display_name": getattr(uploaded_file, "display_name", None),
                "state": str(getattr(uploaded_file, "state", None)),
            }

            logger.info("Submitting Gemini request for %s attempt=%s", corpus_id, attempt)

            try:
                from google.genai import types

                config = types.GenerateContentConfig(**generation_config)
                response = client.models.generate_content(
                    model=model,
                    contents=[request_text, uploaded_file],
                    config=config,
                )
            except Exception:
                response = client.models.generate_content(
                    model=model,
                    contents=[request_text, uploaded_file],
                )

            text = extract_response_text(response)
            api_metadata = response_api_metadata(response)
            api_metadata["uploaded_file"] = uploaded_metadata

            retry_meta = {
                "max_retries": max_retries,
                "attempts": attempts,
                "backoff_seconds_initial": retry_backoff_seconds,
                "errors": retry_errors,
                "succeeded_after_retry": attempts > 1,
            }

            return text, api_metadata, retry_meta

        except Exception as exc:
            error_entry = {
                "attempt": attempt,
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            }
            retry_errors.append(error_entry)
            logger.warning("Gemini attempt failed for %s: %s", corpus_id, error_entry)

            if attempt >= max_retries + 1:
                retry_meta = {
                    "max_retries": max_retries,
                    "attempts": attempts,
                    "backoff_seconds_initial": retry_backoff_seconds,
                    "errors": retry_errors,
                    "succeeded_after_retry": False,
                }
                raise RuntimeError(json.dumps(retry_meta, ensure_ascii=False)) from exc

            time.sleep(retry_backoff_seconds * (2 ** (attempt - 1)))

    raise RuntimeError("Unexpected Gemini retry state")


def base_paths_metadata() -> dict[str, Any]:
    return {
        "path_resolution_policy": PATH_RESOLUTION_POLICY,
        "programme_directory": PROGRAMME_DIR.resolve().as_posix(),
        "current_working_directory": CWD.resolve().as_posix(),
    }


def methodological_notes() -> dict[str, Any]:
    return {
        "transcript_status": "model_generated_not_ground_truth",
        "speaker_labels": "anonymous_model_generated_labels",
        "speaker_label_consistency": "requested_but_not_guaranteed",
        "timestamps": "model_generated_approximate",
        "overlap_detection": "requested_but_not_guaranteed",
        "quality_note_requested": True,
        "subtitles_submitted": False,
        "video_submitted": False,
        "comments_submitted": False,
        "prior_transcript_submitted": False,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def per_debate_input_metadata(
        args: argparse.Namespace,
        corpus_id: str,
        audio_path: Path,
        txt_path: Path,
        json_path: Path,
) -> dict[str, Any]:
    rel_audio = args.audio_dir_supplied / f"{corpus_id}.flac"
    rel_txt = args.output_dir_supplied / f"{corpus_id}.txt"
    rel_json = args.output_dir_supplied / f"{corpus_id}.json"

    return {
        "audio_index": {
            "path": args.audio_index_supplied.as_posix(),
            "resolved_path": args.audio_index.resolve().as_posix(),
            "path_source": args.path_sources["audio_index"],
        },
        "debate_index": {
            "path": args.debate_index_supplied.as_posix(),
            "resolved_path": args.debate_index.resolve().as_posix(),
            "path_source": args.path_sources["debate_index"],
        },
        "audio_file": {
            "path": rel_audio.as_posix(),
            "resolved_path": audio_path.resolve().as_posix(),
        },
        "prompt_template": {
            "path": args.prompt_template_supplied.as_posix(),
            "resolved_path": args.prompt_template.resolve().as_posix(),
            "path_source": args.path_sources["prompt_template"],
        },
        "output_txt": {
            "path": rel_txt.as_posix(),
            "resolved_path": txt_path.resolve().as_posix(),
        },
        "output_json": {
            "path": rel_json.as_posix(),
            "resolved_path": json_path.resolve().as_posix(),
        },
    }


def failure_metadata(
        args: argparse.Namespace,
        corpus_id: str,
        audio_row: dict[str, Any],
        debate_row: dict[str, Any] | None,
        audio_path: Path,
        txt_path: Path,
        json_path: Path,
        prompt_meta: dict[str, Any],
        status: str,
        error: str,
        started_at: str,
        ended_at: str,
) -> dict[str, Any]:
    return {
        "programme": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "corpus_id": corpus_id,
        "status": status,
        "paths": base_paths_metadata(),
        "input": per_debate_input_metadata(args, corpus_id, audio_path, txt_path, json_path),
        "source_metadata": {
            "audio_index_row": audio_row,
            "debate_index_row": debate_row or {},
        },
        "prompt": {
            "template_path": args.prompt_template_supplied.as_posix(),
            "template_resolved_path": args.prompt_template.resolve().as_posix(),
            "template_sha256": prompt_meta.get("sha256"),
            "template_character_count": prompt_meta.get("character_count"),
        },
        "audio": {
            "filename": audio_path.name,
            "path": (args.audio_dir_supplied / audio_path.name).as_posix(),
            "resolved_path": audio_path.resolve().as_posix(),
            "submitted": False,
            "role": "primary_audio_evidence",
        },
        "model": {
            "provider": "google",
            "model": args.model,
            "temperature": args.temperature,
            "max_output_tokens": None if args.max_output_tokens == 0 else args.max_output_tokens,
        },
        "methodological_notes": methodological_notes(),
        "timing": {
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": (
                    datetime.strptime(ended_at, "%Y-%m-%dT%H:%M:%SZ")
                    - datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ")
            ).total_seconds(),
        },
        "created_at": ended_at,
        "error": error,
    }


def process_debate(
        row: dict[str, Any],
        debate_lookup: dict[str, dict[str, Any]],
        args: argparse.Namespace,
        prompt_text: str,
        prompt_meta: dict[str, Any],
        genai_module: Any,
        logger: logging.Logger,
) -> dict[str, Any]:
    corpus_id = str(row["corpus_id"])
    started_at = utc_timestamp()
    debate_row = debate_lookup.get(corpus_id)

    audio_path = args.audio_dir / f"{corpus_id}.flac"
    txt_path, json_path = output_paths(corpus_id, args)

    if not args.reprocess:
        already_success, previous = existing_success(txt_path, json_path)
        if already_success:
            logger.info("Skipped existing successful output: %s", corpus_id)
            return {
                "corpus_id": corpus_id,
                "status": "skipped_existing",
                "reason": "Existing successful output found and --reprocess was not provided.",
                "output_txt": (args.output_dir_supplied / f"{corpus_id}.txt").as_posix(),
                "output_txt_resolved": txt_path.resolve().as_posix(),
                "output_json": (args.output_dir_supplied / f"{corpus_id}.json").as_posix(),
                "output_json_resolved": json_path.resolve().as_posix(),
                "previous_model": previous.get("model", {}).get("model"),
                "previous_prompt_template_sha256": previous.get("prompt", {}).get("template_sha256"),
            }

    try:
        if not audio_path.exists():
            raise FileNotFoundError(f"Missing audio file: {audio_path}")
        if audio_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            raise ValueError(f"Unsupported audio extension: {audio_path.suffix}")
        if not audio_path.is_file():
            raise ValueError(f"Audio path is not a file: {audio_path}")

        audio_size = audio_path.stat().st_size
        if audio_size <= 0:
            raise ValueError(f"Audio file is empty: {audio_path}")

        audio_hash = sha256_file(audio_path)

    except FileNotFoundError as exc:
        ended_at = utc_timestamp()
        metadata = failure_metadata(
            args,
            corpus_id,
            row,
            debate_row,
            audio_path,
            txt_path,
            json_path,
            prompt_meta,
            "failed_missing_audio",
            str(exc),
            started_at,
            ended_at,
        )
        write_json(json_path, metadata)
        return {
            "corpus_id": corpus_id,
            "status": "failed_missing_audio",
            "audio_file": (args.audio_dir_supplied / f"{corpus_id}.flac").as_posix(),
            "audio_file_resolved": audio_path.resolve().as_posix(),
            "output_json": (args.output_dir_supplied / f"{corpus_id}.json").as_posix(),
            "error": str(exc),
        }

    except Exception as exc:
        ended_at = utc_timestamp()
        metadata = failure_metadata(
            args,
            corpus_id,
            row,
            debate_row,
            audio_path,
            txt_path,
            json_path,
            prompt_meta,
            "failed_invalid_audio",
            json_safe_error(exc),
            started_at,
            ended_at,
        )
        write_json(json_path, metadata)
        return {
            "corpus_id": corpus_id,
            "status": "failed_invalid_audio",
            "audio_file": (args.audio_dir_supplied / f"{corpus_id}.flac").as_posix(),
            "audio_file_resolved": audio_path.resolve().as_posix(),
            "output_json": (args.output_dir_supplied / f"{corpus_id}.json").as_posix(),
            "error": json_safe_error(exc),
        }

    try:
        metadata_note = build_metadata_note(corpus_id, audio_path, row, debate_row)
        request_text = build_request_text(prompt_text, metadata_note)
        request_hash = sha256_text(request_text)
        metadata_note_hash = sha256_text(metadata_note)

        api_key = os.environ["GEMINI_API_KEY"]
        response_text, api_metadata, retry_meta = call_gemini(
            genai_module=genai_module,
            api_key=api_key,
            model=args.model,
            request_text=request_text,
            audio_path=audio_path,
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
            max_retries=args.max_retries,
            retry_backoff_seconds=args.retry_backoff_seconds,
            logger=logger,
            corpus_id=corpus_id,
        )

        if not response_text.strip():
            raise ValueError("Gemini response contained no usable text")

        txt_path.parent.mkdir(parents=True, exist_ok=True)
        txt_path.write_text(response_text, encoding="utf-8")

        ended_at = utc_timestamp()

        metadata = {
            "programme": TOOL_NAME,
            "tool_version": TOOL_VERSION,
            "corpus_id": corpus_id,
            "status": "success",
            "paths": base_paths_metadata(),
            "input": per_debate_input_metadata(args, corpus_id, audio_path, txt_path, json_path),
            "source_metadata": {
                "audio_index_row": row,
                "debate_index_row": debate_row or {},
            },
            "prompt": {
                "template_path": args.prompt_template_supplied.as_posix(),
                "template_resolved_path": args.prompt_template.resolve().as_posix(),
                "template_sha256": prompt_meta["sha256"],
                "template_character_count": prompt_meta["character_count"],
                "metadata_note_included": True,
                "metadata_note_sha256": metadata_note_hash,
                "request_text_sha256": request_hash,
            },
            "audio": {
                "filename": audio_path.name,
                "path": (args.audio_dir_supplied / audio_path.name).as_posix(),
                "resolved_path": audio_path.resolve().as_posix(),
                "format": "flac",
                "sha256": audio_hash,
                "size_bytes": audio_size,
                "submitted": True,
                "role": "primary_audio_evidence",
            },
            "model": {
                "provider": "google",
                "model": args.model,
                "temperature": args.temperature,
                "temperature_sent_to_api": True,
                "max_output_tokens": None if args.max_output_tokens == 0 else args.max_output_tokens,
                "generation_config": {
                    "temperature": args.temperature,
                    **(
                        {}
                        if args.max_output_tokens == 0
                        else {"max_output_tokens": args.max_output_tokens}
                    ),
                },
            },
            "api_metadata": api_metadata,
            "response": {
                "text": response_text,
                "text_sha256": sha256_text(response_text),
                "character_count": len(response_text),
                "empty": False,
            },
            "methodological_notes": methodological_notes(),
            "timing": {
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_seconds": (
                        datetime.strptime(ended_at, "%Y-%m-%dT%H:%M:%SZ")
                        - datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ")
                ).total_seconds(),
            },
            "retry": retry_meta,
            "created_at": ended_at,
            "error": None,
        }

        write_json(json_path, metadata)
        logger.info("Success %s", corpus_id)

        return {
            "corpus_id": corpus_id,
            "status": "success",
            "audio_file": (args.audio_dir_supplied / f"{corpus_id}.flac").as_posix(),
            "audio_file_resolved": audio_path.resolve().as_posix(),
            "output_txt": (args.output_dir_supplied / f"{corpus_id}.txt").as_posix(),
            "output_txt_resolved": txt_path.resolve().as_posix(),
            "output_json": (args.output_dir_supplied / f"{corpus_id}.json").as_posix(),
            "output_json_resolved": json_path.resolve().as_posix(),
        }

    except Exception as exc:
        ended_at = utc_timestamp()

        message = json_safe_error(exc)
        status = "failed_api_request"
        if "no usable text" in str(exc).lower():
            status = "failed_empty_response"

        try:
            metadata = failure_metadata(
                args,
                corpus_id,
                row,
                debate_row,
                audio_path,
                txt_path,
                json_path,
                prompt_meta,
                status,
                message,
                started_at,
                ended_at,
            )
            metadata["audio"].update(
                {
                    "format": "flac",
                    "sha256": audio_hash,
                    "size_bytes": audio_size,
                    "submitted": status != "failed_request_construction",
                }
            )
            write_json(json_path, metadata)
        except Exception as write_exc:
            status = "failed_output_write"
            message = f"{message}; additionally failed to write per-debate JSON: {json_safe_error(write_exc)}"

        logger.error("Failed %s: %s", corpus_id, message)

        return {
            "corpus_id": corpus_id,
            "status": status,
            "audio_file": (args.audio_dir_supplied / f"{corpus_id}.flac").as_posix(),
            "audio_file_resolved": audio_path.resolve().as_posix(),
            "output_json": (args.output_dir_supplied / f"{corpus_id}.json").as_posix(),
            "output_json_resolved": json_path.resolve().as_posix(),
            "error": message,
        }


def manifest_status(items: list[dict[str, Any]]) -> str:
    failed = [item for item in items if str(item.get("status", "")).startswith("failed")]
    if failed:
        return "completed_with_failures"
    return "completed"


def write_manifests(manifest: dict[str, Any], latest_path: Path, run_id: str) -> tuple[Path, Path]:
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    run_path = latest_path.parent / f"speaker_diarisation_jubilee_debates_manifest_{run_id}.json"

    for path in (latest_path, run_path):
        with path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    return latest_path, run_path


def build_manifest(
        args: argparse.Namespace,
        run_id: str,
        started_at: str,
        ended_at: str,
        prompt_meta: dict[str, Any] | None,
        env_meta: dict[str, Any] | None,
        debate_index_loaded: bool,
        audio_rows_read: int,
        plan_count: int,
        items: list[dict[str, Any]],
        error: str | None = None,
) -> dict[str, Any]:
    counts = {
        "audio_index_rows_read": audio_rows_read,
        "debates_planned": plan_count,
        "skipped_existing": sum(1 for item in items if item.get("status") == "skipped_existing"),
        "submitted": sum(1 for item in items if item.get("status") == "success"),
        "succeeded": sum(1 for item in items if item.get("status") == "success"),
        "failed": sum(1 for item in items if str(item.get("status", "")).startswith("failed")),
        "failed_missing_audio": sum(1 for item in items if item.get("status") == "failed_missing_audio"),
        "failed_invalid_audio": sum(1 for item in items if item.get("status") == "failed_invalid_audio"),
        "failed_api_error": sum(1 for item in items if item.get("status") == "failed_api_request"),
        "failed_empty_response": sum(1 for item in items if item.get("status") == "failed_empty_response"),
    }

    return {
        "run_id": run_id,
        "programme": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "status": "failed_global_validation" if error else manifest_status(items),
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": (
                datetime.strptime(ended_at, "%Y-%m-%dT%H:%M:%SZ")
                - datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ")
        ).total_seconds(),
        "paths": base_paths_metadata(),
        "input": {
            "prompt_template": {
                "path": args.prompt_template_supplied.as_posix(),
                "resolved_path": args.prompt_template.resolve().as_posix(),
                "path_source": args.path_sources["prompt_template"],
                "sha256": None if prompt_meta is None else prompt_meta.get("sha256"),
            },
            "env_file": {
                "path": args.env_file_supplied.as_posix(),
                "resolved_path": args.env_file.resolve().as_posix(),
                "path_source": args.path_sources["env_file"],
            },
            "audio_dir": {
                "path": args.audio_dir_supplied.as_posix(),
                "resolved_path": args.audio_dir.resolve().as_posix(),
                "path_source": args.path_sources["audio_dir"],
            },
            "audio_index": {
                "path": args.audio_index_supplied.as_posix(),
                "resolved_path": args.audio_index.resolve().as_posix(),
                "path_source": args.path_sources["audio_index"],
            },
            "debate_index": {
                "path": args.debate_index_supplied.as_posix(),
                "resolved_path": args.debate_index.resolve().as_posix(),
                "path_source": args.path_sources["debate_index"],
                "loaded": debate_index_loaded,
            },
        },
        "environment": env_meta
                       or {
                           "dotenv_loaded": False,
                           "gemini_api_key_present": False,
                           "gemini_api_key_logged": False,
                       },
        "output": {
            "output_dir": {
                "path": args.output_dir_supplied.as_posix(),
                "resolved_path": args.output_dir.resolve().as_posix(),
                "path_source": args.path_sources["output_dir"],
            },
            "log_file": {
                "path": args.log_file_supplied.as_posix(),
                "resolved_path": args.log_file.resolve().as_posix(),
            },
            "manifest_file": {
                "path": args.manifest_file_supplied.as_posix(),
                "resolved_path": args.manifest_file.resolve().as_posix(),
            },
        },
        "model": {
            "provider": "google",
            "model": args.model,
            "temperature": args.temperature,
            "max_output_tokens": None if args.max_output_tokens == 0 else args.max_output_tokens,
        },
        "strategy": {
            "task": "speaker_diarisation",
            "primary_evidence": "jubilee_debate_audio_flac",
            "model_provider": "google",
            "default_model": DEFAULT_MODEL,
            "transcript_generation": "prompted_gemini_audio_understanding",
            "speaker_labels": "model_generated_consistent_anonymous_labels",
            "timestamps": "model_generated_mm_ss_turn_timestamps",
            "subtitles_submitted": False,
            "video_submitted": False,
            "youtube_comments_submitted": False,
            "prior_transcript_submitted": False,
        },
        "processing": {
            "test_mode": args.test_mode,
            "test_limit": args.test_limit,
            "start_corpus_id": args.start_corpus_id,
            "only_corpus_id": args.only_corpus_id,
            "reprocess": args.reprocess,
            "workers": args.workers,
            "max_retries": args.max_retries,
            "retry_backoff_seconds": args.retry_backoff_seconds,
        },
        "counts": counts,
        "items": items,
        "error": error,
    }


def main() -> int:
    args = parse_args()
    run_id = make_run_id()
    started_at = utc_timestamp()
    logger: logging.Logger | None = None

    items: list[dict[str, Any]] = []
    prompt_meta: dict[str, Any] | None = None
    env_meta: dict[str, Any] | None = None
    debate_index_loaded = False
    audio_rows_read = 0
    plan_count = 0

    try:
        validate_numeric_args(args)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        validate_global_inputs(args)
        logger = setup_logging(args.log_file)

        logger.info("Run started: %s", run_id)
        logger.info("Programme directory: %s", PROGRAMME_DIR.resolve())
        logger.info("Current working directory: %s", CWD.resolve())
        logger.info("Model: %s", args.model)
        logger.info("Output directory: %s", args.output_dir.resolve())

        env_meta = load_environment(args)
        genai_module = validate_gemini_sdk()
        prompt_text, prompt_meta = load_prompt_template(args)

        audio_rows, audio_rows_read = load_ndjson_required(args.audio_index, "audio index")
        debate_lookup, debate_index_loaded = load_optional_debate_index(args.debate_index)

        if not debate_index_loaded:
            logger.warning("Optional debate index not found: %s", args.debate_index)

        plan = apply_plan_filters(audio_rows, args)
        plan_count = len(plan)

        logger.info("Audio index rows read: %s", audio_rows_read)
        logger.info("Planned debates: %s", plan_count)

        for row in plan:
            corpus_id = str(row["corpus_id"])
            logger.info("Processing %s", corpus_id)
            result = process_debate(
                row=row,
                debate_lookup=debate_lookup,
                args=args,
                prompt_text=prompt_text,
                prompt_meta=prompt_meta,
                genai_module=genai_module,
                logger=logger,
            )
            items.append(result)

        ended_at = utc_timestamp()
        manifest = build_manifest(
            args=args,
            run_id=run_id,
            started_at=started_at,
            ended_at=ended_at,
            prompt_meta=prompt_meta,
            env_meta=env_meta,
            debate_index_loaded=debate_index_loaded,
            audio_rows_read=audio_rows_read,
            plan_count=plan_count,
            items=items,
            error=None,
        )

        latest, run_specific = write_manifests(manifest, args.manifest_file, run_id)

        shutil.copyfile(run_specific, latest)

        logger.info("Run %s", manifest["status"])
        logger.info("Manifest: %s", run_specific)

        return 1 if manifest["counts"]["failed"] > 0 else 0

    except KeyboardInterrupt:
        ended_at = utc_timestamp()

        if logger:
            logger.error("Interrupted by user")

        try:
            manifest = build_manifest(
                args=args,
                run_id=run_id,
                started_at=started_at,
                ended_at=ended_at,
                prompt_meta=prompt_meta,
                env_meta=env_meta,
                debate_index_loaded=debate_index_loaded,
                audio_rows_read=audio_rows_read,
                plan_count=plan_count,
                items=items,
                error="Interrupted by user",
            )
            manifest["status"] = "interrupted"
            write_manifests(manifest, args.manifest_file, run_id)
        except Exception:
            pass

        return 130

    except ConfigurationError as exc:
        message = f"Configuration error: {exc}"

        if logger:
            logger.error(message)
        else:
            print(message, file=sys.stderr)

        try:
            ended_at = utc_timestamp()
            manifest = build_manifest(
                args=args,
                run_id=run_id,
                started_at=started_at,
                ended_at=ended_at,
                prompt_meta=prompt_meta,
                env_meta=env_meta,
                debate_index_loaded=debate_index_loaded,
                audio_rows_read=audio_rows_read,
                plan_count=plan_count,
                items=items,
                error=message,
            )
            write_manifests(manifest, args.manifest_file, run_id)
        except Exception:
            pass

        return 2

    except OSError as exc:
        message = f"I/O error: {exc}"

        if logger:
            logger.exception(message)
        else:
            print(message, file=sys.stderr)

        return 2


if __name__ == "__main__":
    sys.exit(main())