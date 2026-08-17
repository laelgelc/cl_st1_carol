# `extract_jubilee_debates_audio.py` — Programme Specification for Development

## 1. High-level Functionality Specification

### Programme Summary

`extract_jubilee_debates_audio.py` is a batch-processing programme that extracts transcription-ready and diarisation-ready audio from previously downloaded Jubilee debate video files.

The programme is part of **Corpus Linguistics — Study 1 — Carol, Phase 0**.

The purpose of this programme is to prepare full-length audio files suitable for a downstream speech-processing pipeline using:

- Whisper;
- WhisperX;
- pyannote.audio speaker diarisation.

The programme reads the curated Jubilee debate index:
```text
corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```
Each record in this index represents one selected Jubilee debate. The programme must process only records where the downloaded video is available, indicated by:
```text
download_status = success
```
or:
```text
download_status = skipped_existing
```
For each eligible row, the programme uses:

- `corpus_id` to identify the debate;
- `video_file`, when present and valid, to locate the source video;
- `<input_dir>/<corpus_id>.mp4` as a fallback source video path;
- `corpus_id` again to name the extracted audio file.

The source debate video files are expected in:
```text
corpus/01_jubilee_debates/videos/
```
The extracted audio files must be written to:
```text
corpus/02_jubilee_debates_audio/
```
Each extracted audio file must be saved as:
```text
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```
The base audio extraction command is:
```bash
ffmpeg -y -i "jubilee_surrounded_001.mp4" -vn -ac 1 -ar 16000 -sample_fmt s16 "jubilee_surrounded_001.wav"
```
The programme must generalise this command so that each eligible debate audio file is extracted as:
```bash
ffmpeg -y -i "<input_video>" -vn -ac 1 -ar 16000 -sample_fmt s16 "<output_dir>/<corpus_id>.wav"
```
For example:
```bash
ffmpeg -y \
  -i "corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4" \
  -vn \
  -ac 1 \
  -ar 16000 \
  -sample_fmt s16 \
  "corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav"
```
The output audio format is designed to be convenient for Whisper, WhisperX, and pyannote.audio:

- WAV container;
- mono audio;
- 16 kHz sample rate;
- signed 16-bit PCM sample format.

The programme extracts **full-length audio only**. It must not split, trim, segment, diarise, transcribe, or otherwise analyse the audio. Segmentation, transcription, alignment, and diarisation are separate downstream pipeline stages.

The curated audio index must be portable. File paths inside the project phase directory should be written as project-relative paths, for example:
```text
corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav
```
rather than machine-specific absolute paths such as:
```text
/home/<user>/PycharmProjects/cl_st1_carol/cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav
```
This portability is important because later processing stages may be run on a different machine, such as an EC2 GPU server.

The curated audio index must also preserve source media duration correctly:

- `duration_seconds` must remain the source video/audio duration inherited from the download index;
- `audio_extraction_duration_seconds` must store how long the ffmpeg extraction command took to run.

The programme must not overwrite source media duration with ffmpeg runtime duration.

---

## 2. Key Behaviours

The programme must implement the following behaviours:

- Read Jubilee debate metadata from an NDJSON index file.
- Process only records where `download_status` indicates that the source video is available.
- Extract the required fields:
  - `corpus_id`;
  - `download_status`;
  - source video location via `video_file` or fallback input directory.
- Build one `ffmpeg` audio extraction command per eligible debate.
- Locate source debate videos using:
  - the `video_file` field, when present and usable;
  - otherwise `<input_dir>/<corpus_id>.mp4`.
- Save extracted audio as:

  ```text
  <output_dir>/<corpus_id>.wav
  ```

- Create the output directory if it does not already exist.
- Use `ffmpeg` as the external audio extraction engine.
- Produce audio suitable for WhisperX and pyannote.audio:
  - no video stream;
  - mono channel;
  - 16 kHz sampling rate;
  - signed 16-bit PCM WAV.
- Use test mode by default, limiting processing to 5 eligible debates.
- Skip already-extracted audio files by default, supporting safe re-runs.
- Allow reprocessing with an explicit command-line option.
- Support starting from a specific `corpus_id`.
- Continue processing remaining debates if one audio extraction fails.
- Record progress and errors in an append-only log file.
- Produce a JSON manifest with run-level metadata and item-level results.
- Write both:
  - a timestamped per-run manifest;
  - a latest manifest that is overwritten on each run.
- Write a curated audio index for downstream pipeline stages.
- Write project-internal paths in the curated audio index as project-relative paths.
- Preserve source media duration as `duration_seconds`.
- Store ffmpeg runtime as `audio_extraction_duration_seconds`.
- Exit with status code `0` only when all attempted audio extractions succeed or are skipped, and there are no missing inputs or invalid eligible metadata rows.
- Exit with a non-zero status code if one or more attempted extractions fail, source videos are missing, eligible metadata rows are invalid, or there is a configuration/validation error.

---

## 3. Path Resolution Policy

The programme must resolve its default paths relative to the directory where `extract_jubilee_debates_audio.py` is located, not relative to the current working directory.

If the script is located at:
```text
cl_st1_ph0_carol/extract_jubilee_debates_audio.py
```
then the default index path:
```text
corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```
must resolve to:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```
This policy ensures that the programme works correctly whether executed from:
```text
cl_st1_carol/
```
or:
```text
cl_st1_carol/cl_st1_ph0_carol/
```
or from another current working directory.

### 3.1 Internal path base

The implementation should define a script directory equivalent to:
```python
SCRIPT_DIR = Path(__file__).resolve().parent
```
Relative default paths and relative command-line paths should be resolved against `SCRIPT_DIR`.

### 3.2 Absolute paths

If the user supplies an absolute path for arguments such as `--index`, `--input-dir`, `--output-dir`, `--log-file`, `--manifest-file`, or `--audio-index-file`, the programme must preserve that absolute path.

### 3.3 Portable paths in curated outputs

Although the programme may resolve paths internally as absolute paths, curated index files should store project-internal paths as paths relative to `SCRIPT_DIR`.

This applies to audio index fields such as:

- `source_video_file`;
- `audio_file`;
- `raw_metadata_file`;
- `description_file`;
- `subtitles_files`.

For example, if the programme internally resolves:
```text
/home/eyamrog/PycharmProjects/cl_st1_carol/cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav
```
the audio index should store:
```text
corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav
```
Paths outside the project phase directory may be preserved as supplied, because converting genuinely external paths to project-relative paths would be misleading.

The manifest may contain resolved paths for debugging, but curated index files intended for downstream stages should prefer portable project-relative paths.

---

## 4. Input / Output Specification

## 4.1 Input

### Input index file

Default path:
```text
corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```
The file is expected to be in **NDJSON** format, meaning one JSON object per line.

### Required fields

Each valid eligible record must contain:

| Field             |   Type | Description                                                      |
|-------------------|-------:|------------------------------------------------------------------|
| `corpus_id`       | string | Stable internal debate identifier, e.g. `jubilee_surrounded_001` |
| `download_status` | string | Download status from the previous pipeline stage                 |

The source video path is resolved using:

| Field        | Requirement | Description                                                               |
|--------------|-------------|---------------------------------------------------------------------------|
| `video_file` | optional    | Preferred local path to the downloaded video file when present and usable |

If `video_file` is absent, blank, or unusable, the programme must fall back to:
```text
<input_dir>/<corpus_id>.mp4
```
### Recommended metadata fields to preserve

The programme should preserve these fields in the manifest and audio index when present:

| Field               | Description                                                                           |
|---------------------|---------------------------------------------------------------------------------------|
| `debate_format`     | Debate format, e.g. `Surrounded`                                                      |
| `sample_group`      | Sample group, e.g. `carol_initial_sample`                                             |
| `sample_order`      | Order in the selected sample                                                          |
| `title`             | Selected title, if present                                                            |
| `title_selected`    | Title from the selected sample                                                        |
| `title_extracted`   | Title extracted by the download stage                                                 |
| `youtube_id`        | YouTube video ID                                                                      |
| `youtube_url`       | Original YouTube URL                                                                  |
| `webpage_url`       | Canonical YouTube URL                                                                 |
| `channel`           | Selected channel, if present                                                          |
| `channel_selected`  | Expected channel from sample                                                          |
| `channel_extracted` | Extracted channel                                                                     |
| `duration_seconds`  | Source video/audio duration in seconds; must not be overwritten by extraction runtime |
| `duration_string`   | Human-readable source duration                                                        |
| `chapters`          | Chapter metadata                                                                      |
| `subtitles_files`   | Downloaded subtitle files                                                             |
| `raw_metadata_file` | Raw `.info.json` file                                                                 |
| `description_file`  | Downloaded description file                                                           |
| `download_run_id`   | Run ID from the video download stage                                                  |
| `downloaded_at_utc` | Timestamp from the video download stage                                               |
| `yt_dlp_version`    | `yt-dlp` version from the download stage                                              |
| `selected_by`       | Selector, e.g. `Carol`                                                                |
| `selection_source`  | Selection source                                                                      |
| `notes`             | Optional notes                                                                        |
| `metadata_status`   | Metadata status from the download stage                                               |

Example record:
```json
{
  "corpus_id": "jubilee_surrounded_001",
  "debate_format": "Surrounded",
  "sample_group": "carol_initial_sample",
  "sample_order": 1,
  "title_selected": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)",
  "title_extracted": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk) | Surrounded",
  "youtube_id": "WV29R1M25n8",
  "youtube_url": "https://www.youtube.com/watch?v=WV29R1M25n8",
  "duration_seconds": 5427,
  "duration_string": "1:30:27",
  "video_file": "corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4",
  "download_status": "success",
  "metadata_status": "success"
}
```
---

## 4.2 Eligibility Rules

The programme must:

1. Read all records from the NDJSON index file.
2. Select only records where `download_status` is one of:

   ```text
   success
   skipped_existing
   ```

3. Ignore records where `download_status` is not eligible.
4. Validate that each selected record has a non-empty:
   - `corpus_id`
5. Build one planned audio extraction per valid selected record.
6. Preserve metadata order from the NDJSON index.

### Ineligible download statuses

The following values should not be eligible:
```text
failed
not_requested
failed_metadata
missing_input
null
""
missing value
```
Records ignored because of `download_status` are not errors. They are expected to be ignored because their source videos were not successfully downloaded or were not available.

### Invalid metadata rows

If a row has an eligible `download_status` but is missing `corpus_id`:

- it must not be processed;
- it should be marked as `failed_metadata` in the manifest;
- the error should be logged;
- processing should continue for other records;
- the programme should exit with code `1` after the run.

Invalid JSON lines are configuration errors and must cause exit code `2`.

---

## 4.3 Output

### Audio output directory

Default path:
```text
corpus/02_jubilee_debates_audio/
```
The programme must create this directory if it does not already exist.

### Per-debate audio output

Each extracted audio file must be saved as:
```text
<output_dir>/<corpus_id>.wav
```
Examples:
```text
corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav
corpus/02_jubilee_debates_audio/jubilee_surrounded_002.wav
corpus/02_jubilee_debates_audio/jubilee_surrounded_003.wav
```
### Source debate video input directory

Default path:
```text
corpus/01_jubilee_debates/videos/
```
Each fallback source video is expected to exist as:
```text
<input_dir>/<corpus_id>.mp4
```
Examples:
```text
corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4
corpus/01_jubilee_debates/videos/jubilee_surrounded_002.mp4
corpus/01_jubilee_debates/videos/jubilee_surrounded_003.mp4
```
### Log file

Default path:
```text
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log
```
The log file must be:

- plain text;
- UTF-8 encoded;
- append-only;
- line-oriented.

### Manifest files

The programme must write two manifest files.

#### Latest manifest

Default path:
```text
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest.json
```
This file is overwritten at the end of each run.

#### Per-run manifest

A timestamped copy must also be written using the run ID.

Filename pattern:
```text
extract_jubilee_debates_audio_manifest_<run_id>.json
```
Example:
```text
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest_20260730T210000Z.json
```
### Audio index file

Default path:
```text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```
The audio index is an NDJSON file containing one JSON object per processed, skipped, missing, or failed eligible debate item.

---

# 5. Command-line Interface

## 5.1 Default usage

The script may be run from inside `cl_st1_ph0_carol/`:
```bash
python extract_jubilee_debates_audio.py
```
or from the project root:
```bash
python cl_st1_ph0_carol/extract_jubilee_debates_audio.py
```
Both commands should resolve default paths correctly.

Default behaviour:

- input index: `corpus/01_jubilee_debates/jubilee_debates_index.ndjson`
- input directory: `corpus/01_jubilee_debates/videos/`
- output directory: `corpus/02_jubilee_debates_audio/`
- output format: `.wav`
- audio channels: `1`
- audio sample rate: `16000`
- sample format: `s16`
- test mode: enabled
- test limit: 5 debates
- reprocess: disabled
- existing `.wav` files are skipped
- one worker / sequential processing

---

## 5.2 Required arguments

There are no required command-line arguments if all default paths are used.

However, all important paths and processing controls must be configurable.

---

## 5.3 Optional arguments

### Input index file
```bash
--index PATH
```
Default:
```text
corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```
Description:

Path to the NDJSON curated debate index.

Relative paths are resolved relative to the programme directory.

---

### Input video directory
```bash
--input-dir PATH
```
Default:
```text
corpus/01_jubilee_debates/videos/
```
Description:

Directory containing source video files.

Used as a fallback when the `video_file` field is absent or unusable.

Relative paths are resolved relative to the programme directory.

---

### Output directory
```bash
--output-dir PATH
```
Default:
```text
corpus/02_jubilee_debates_audio/
```
Description:

Directory where extracted `.wav` audio files, logs, manifests, and the audio index will be saved.

Relative paths are resolved relative to the programme directory.

---

### Test mode
```bash
--test-mode
--no-test-mode
```
Default:
```text
--test-mode
```
Description:

When test mode is enabled, the programme processes only a limited number of planned audio extractions.

---

### Test limit
```bash
--test-limit N
```
Default:
```text
5
```
Description:

Maximum number of debates to attempt when test mode is enabled.

Must be a positive integer.

Example:
```bash
python extract_jubilee_debates_audio.py --test-limit 3
```
---

### Reprocess existing audio files
```bash
--reprocess
```
Default:
```text
False
```
Description:

When omitted, the programme skips any debate whose output `.wav` file already exists.

When provided, the programme extracts the audio again and overwrites the existing output file.

Example:
```bash
python extract_jubilee_debates_audio.py --no-test-mode --reprocess
```
---

### Start corpus ID
```bash
--start-corpus-id CORPUS_ID
```
Default:
```text
None
```
Description:

Optional `corpus_id` from which to start planning audio extraction.

When this option is provided, the programme must preserve metadata order but ignore all eligible debates that occur before the specified `corpus_id`. The specified debate itself must be included in the planning step.

This is useful for resuming a long extraction run from a known point without relying only on existing-file detection.

Example:
```bash
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```
If the requested `corpus_id` is not found among eligible metadata rows, the programme must fail fast with a configuration error.

---

### Log file
```bash
--log-file PATH
```
Default:
```text
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log
```
Description:

Path to the append-only log file.

Relative paths are resolved relative to the programme directory.

---

### Manifest file
```bash
--manifest-file PATH
```
Default:
```text
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest.json
```
Description:

Path to the latest manifest file. The per-run timestamped manifest should be written next to this file.

Relative paths are resolved relative to the programme directory.

---

### Audio index file
```bash
--audio-index-file PATH
```
Default:
```text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```
Description:

Path to the curated NDJSON audio index.

Relative paths are resolved relative to the programme directory.

---

### Workers
```bash
--workers N
```
Default:
```text
1
```
Description:

Number of worker processes.

For the current implementation, sequential execution with `--workers 1` is required. The architecture may allow parallel execution later.

Must be a positive integer.

---

### Timeout
```bash
--timeout SECONDS
```
Default suggestion:
```text
7200
```
Description:

Maximum allowed time for a single `ffmpeg` audio extraction process.

Jubilee debate videos can be long, so a two-hour per-item timeout is appropriate for the initial implementation.

If the timeout is reached:

- terminate the process;
- mark the item as failed;
- log the timeout;
- continue with the next debate.

---

### Maximum retries
```bash
--max-retries N
```
Default suggestion:
```text
1
```
Description:

Number of retry attempts after a failed audio extraction command.

For example, with `--max-retries 1`, each failed item may be attempted twice in total:

1. initial attempt;
2. one retry.

Must be zero or a positive integer.

---

### Retry delay
```bash
--retry-delay SECONDS
```
Default suggestion:
```text
5
```
Description:

Seconds to wait between retry attempts.

Must be zero or a positive integer.

---

## 5.4 Example commands

### Small default test run
```bash
python extract_jubilee_debates_audio.py
```
### Test run with 3 debates
```bash
python extract_jubilee_debates_audio.py --test-limit 3
```
### Test run from a specific corpus ID
```bash
python extract_jubilee_debates_audio.py \
  --test-limit 2 \
  --start-corpus-id jubilee_surrounded_003
```
### Full production run
```bash
python extract_jubilee_debates_audio.py --no-test-mode
```
### Full production run from a specific corpus ID
```bash
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```
### Full production run with explicit paths
```bash
python extract_jubilee_debates_audio.py \
  --index corpus/01_jubilee_debates/jubilee_debates_index.ndjson \
  --input-dir corpus/01_jubilee_debates/videos \
  --output-dir corpus/02_jubilee_debates_audio \
  --no-test-mode
```
### Re-extract audio even if files already exist
```bash
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --reprocess
```
---

# 6. Argument Validation

The programme must fail fast with a clear message if:

- the input index file does not exist;
- the input index path is not a file;
- the input index file is unreadable;
- the input index contains invalid JSON lines;
- no eligible records are found;
- the input video directory does not exist;
- the input video directory is not a directory;
- the output directory cannot be created;
- `--test-limit` is less than or equal to zero;
- `--workers` is less than or equal to zero;
- `--workers` is not `1` in the current sequential implementation;
- `--timeout` is less than or equal to zero;
- `--max-retries` is negative;
- `--retry-delay` is negative;
- `--start-corpus-id` is provided but empty;
- `--start-corpus-id` is provided but the corpus ID is not found among eligible metadata rows;
- `ffmpeg` is not available on the system path.

The programme should check for `ffmpeg` availability before processing begins.

Suggested check:
```bash
ffmpeg -version
```
A validation error should:

- be printed clearly to the console;
- be written to the log if logging has already been configured;
- cause the programme to exit with code `2`.

---

# 7. Environment and Configuration

This programme does not require API keys or secret environment variables.

The programme depends on the external command-line tool:
```text
ffmpeg
```
The implementation must verify that `ffmpeg` is available before starting extraction.

No Python package beyond the standard library is required for the initial implementation.

Recommended standard-library modules:

- `argparse`
- `json`
- `logging`
- `subprocess`
- `pathlib`
- `datetime`
- `time`
- `shutil`
- `sys`
- `traceback`, if needed for debugging summaries

---

# 8. Core Processing Architecture

## 8.1 High-level flow

The programme must follow this workflow:

1. **Startup**
   - Parse command-line arguments.
   - Resolve relative paths against the programme directory.
   - Validate simple argument values.
   - Generate a UTC `run_id`.
   - Ensure the output directory exists.
   - Set up logging.
   - Check that `ffmpeg` is available.

2. **Index loading**
   - Open the NDJSON input index.
   - Read records line by line.
   - Parse each JSON object.
   - Count total input records.
   - Select only records where `download_status` is eligible.
   - Validate required fields for selected records:
     - `corpus_id`
   - Preserve input order.
   - Record invalid eligible rows in the manifest.
   - Record ignored ineligible rows in the manifest.

3. **Planning**
   - If `--start-corpus-id` is provided:
     - locate the specified `corpus_id` in the eligible debate list;
     - discard all eligible debates before it;
     - include the specified debate and all following eligible debates;
     - fail fast if the specified `corpus_id` is not found.
   - For each selected eligible debate:
     - resolve the input video path using `video_file` or fallback input directory;
     - compute output path as `<output_dir>/<corpus_id>.wav`;
     - check whether the source video exists;
     - decide whether to skip or extract audio.
   - If the input source video is missing:
     - mark the item as `missing_input`;
     - log the missing input;
     - do not run `ffmpeg` for that item.
   - If the output audio file exists and `--reprocess` is not enabled:
     - mark the item as `skipped_existing`.
   - If the output file does not exist or `--reprocess` is enabled:
     - plan the item for audio extraction.
   - If test mode is enabled:
     - limit the planned extraction list to `--test-limit`.

4. **Execution**
   - For each planned item:
     - build the `ffmpeg` command;
     - run `ffmpeg`;
     - capture stdout, stderr, return code, timing, and any exception;
     - retry according to `--max-retries`;
     - mark the item as `success` or `failed`;
     - record output file size when available;
     - record ffmpeg runtime as `audio_extraction_duration_seconds`.

5. **Audio index generation**
   - Combine input metadata with audio extraction metadata.
   - Preserve source media `duration_seconds`.
   - Write ffmpeg runtime as `audio_extraction_duration_seconds`.
   - Write project-internal paths as project-relative strings.
   - Write `jubilee_debates_audio_index.ndjson`.

6. **End-of-run summary**
   - Count:
     - total input records;
     - eligible records;
     - ignored records;
     - invalid metadata rows;
     - missing input videos;
     - skipped existing audio files;
     - planned audio extractions;
     - attempted audio extractions;
     - successful audio extractions;
     - failed audio extractions.
   - Write the latest manifest.
   - Write the per-run manifest.
   - Log the final summary.
   - Exit with an appropriate status code.

7. **Interrupt handling**
   - Catch `KeyboardInterrupt`.
   - Stop cleanly.
   - Write a partial manifest where possible.
   - Log the interruption.
   - Exit with code `130`.

---

## 8.2 Separation of concerns

The implementation should be organised around the following responsibilities.

### CLI parsing
```python
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the Jubilee debate audio extraction programme."""
```
### Path resolution
```python
def resolve_script_relative_path(path: Path) -> Path:
    """Resolve relative paths against the programme directory."""
```
### Portable index paths
```python
def path_for_index(path_value: Any) -> str | None:
    """Convert project-internal paths to portable project-relative strings for curated indices."""
```
### Validation
```python
def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and external dependencies before processing."""
```
### Logging
```python
def setup_logging(log_file: Path) -> logging.Logger:
    """Configure append-only logging."""
```
### ffmpeg availability
```python
def check_ffmpeg() -> dict:
    """Check whether ffmpeg is available and return version metadata."""
```
### Index loading
```python
def load_debate_index(index_path: Path) -> tuple[list[dict], list[dict], int, int, list[dict]]:
    """Load and validate eligible debate metadata from an NDJSON index file."""
```
Suggested return values:
```text
eligible_records, invalid_records, total_records, ignored_count, ignored_records
```
### Planning
```python
def plan_audio_extractions(
    records: list[dict],
    input_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_corpus_id: str | None = None
) -> tuple[list[dict], list[dict], list[dict]]:
    """Create planned, skipped, and missing-input debate audio extraction records."""
```
Suggested return values:
```text
planned, skipped_existing, missing_input
```
### Source video resolution
```python
def resolve_source_video_path(record: dict, input_dir: Path) -> Path:
    """Resolve source video path using video_file or fallback input directory."""
```
### Command building
```python
def build_ffmpeg_command(input_path: Path, output_path: Path) -> list[str]:
    """Build the ffmpeg command for one Whisper-ready WAV extraction."""
```
### Core audio extraction function
```python
def extract_one_audio(
    corpus_id: str,
    input_path: Path,
    output_path: Path,
    timeout: int,
    max_retries: int,
    retry_delay: int,
    logger: logging.Logger
) -> dict:
    """Extract one Whisper-ready WAV audio file with ffmpeg and return a structured result."""
```
### Audio index record building
```python
def make_audio_index_record(
    item_result: dict,
    run_id: str,
    ffmpeg_info: dict
) -> dict:
    """Build one curated audio index record without corrupting source duration metadata."""
```
### Audio index writing
```python
def write_audio_index(index_records: list[dict], audio_index_file: Path) -> None:
    """Write the curated NDJSON audio index."""
```
### Manifest writing
```python
def write_manifests(
    manifest: dict,
    manifest_file: Path,
    run_id: str
) -> tuple[Path, Path]:
    """Write latest and per-run manifest files."""
```
### Main orchestration
```python
def main() -> int:
    """Run the batch Jubilee debate audio extraction workflow and return an exit code."""
```
---

# 9. Audio Extraction Behaviour

## 9.1 Base command

For each eligible debate, the programme must run:
```bash
ffmpeg -y -i "<input_path>" -vn -ac 1 -ar 16000 -sample_fmt s16 "<output_path>"
```
Example generated command:
```bash
ffmpeg -y \
  -i "corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4" \
  -vn \
  -ac 1 \
  -ar 16000 \
  -sample_fmt s16 \
  "corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav"
```
The command must be built as a list of arguments for `subprocess`, not as a shell string.

Conceptually:
```python
command = [
    "ffmpeg",
    "-y",
    "-i",
    str(input_path),
    "-vn",
    "-ac",
    "1",
    "-ar",
    "16000",
    "-sample_fmt",
    "s16",
    str(output_path),
]
```
---

## 9.2 Full-length extraction only

The programme must extract the entire audio track from each source video.

It must not:

- split audio;
- segment audio;
- trim audio;
- chunk audio;
- transcribe audio;
- diarise audio;
- align transcripts.

These operations belong to later pipeline stages.

---

## 9.3 Input filename

The source video path should be resolved in this order:

1. Use the `video_file` field when present and usable.
2. Otherwise use:

   ```text
   <input_dir>/<corpus_id>.mp4
   ```

Given:
```text
corpus_id = jubilee_surrounded_001
```
the fallback input file must be:
```text
jubilee_surrounded_001.mp4
```
The full default fallback input path must be:
```text
corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4
```
---

## 9.4 Output filename

The output filename must be derived from `corpus_id`, with `.wav` as the extension.

Given:
```text
corpus_id = jubilee_surrounded_001
```
the output file must be:
```text
jubilee_surrounded_001.wav
```
The full default output path must be:
```text
corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav
```
---

## 9.5 Audio format

The output audio must use the following format:

| Property      |                           Value | ffmpeg option           |
|---------------|--------------------------------:|-------------------------|
| Container     |                             WAV | output extension `.wav` |
| Video stream  |                         omitted | `-vn`                   |
| Channels      |                            mono | `-ac 1`                 |
| Sample rate   |                        16000 Hz | `-ar 16000`             |
| Sample format |               signed 16-bit PCM | `-sample_fmt s16`       |
| Codec         | PCM signed 16-bit little-endian | `pcm_s16le`             |

This format is intended to be suitable for Whisper, WhisperX, and pyannote.audio.

---

## 9.6 Existing files

If the output audio file already exists and `--reprocess` is not enabled:

- do not call `ffmpeg`;
- mark the item as `skipped_existing`;
- log the skip;
- include the item in the manifest;
- include the item in the audio index.

If `--reprocess` is enabled:

- call `ffmpeg`;
- allow the output to be overwritten because the command includes `-y`.

---

## 9.7 Missing source videos

If the expected source video file does not exist, the programme must:

- not call `ffmpeg`;
- mark the item as `missing_input`;
- include the expected input path in the manifest;
- include the item in the audio index;
- log the missing input;
- continue processing other debates.

Missing source videos should cause exit code `1`.

---

## 9.8 Start corpus ID behaviour

If `--start-corpus-id CORPUS_ID` is provided:

- the programme must locate `CORPUS_ID` in the eligible debate list;
- all eligible debates before `CORPUS_ID` must be ignored for planning;
- `CORPUS_ID` itself must be included;
- all following eligible debates must be included;
- existing-file skipping must still apply after the start-corpus filter;
- missing-input checking must still apply after the start-corpus filter;
- test-mode limiting must apply after the start-corpus filter and after existing-file skipping;
- if `CORPUS_ID` is not found, the programme must exit with a configuration error.

---

## 9.9 ffmpeg failures

If `ffmpeg` returns a non-zero exit code, the programme must:

- capture the failure;
- mark the debate as `failed`;
- save a short error summary in the manifest;
- log the failure;
- continue with the next debate.

The programme must not stop the entire batch because one debate fails.

---

## 9.10 Retries

For failures that may be transient, the programme should retry up to `--max-retries`.

Retry behaviour:

- retry only failed `ffmpeg` commands;
- do not retry missing-input or failed-metadata records;
- log each retry attempt;
- record the number of retries used in the manifest;
- if all attempts fail, mark the item as `failed`.

A simple fixed delay between retries is acceptable for the initial implementation.

Default retry delay:
```text
5 seconds
```
---

## 9.11 Duration metadata policy

The programme must distinguish between **source media duration** and **extraction runtime**.

### Source media duration

The field:
```text
duration_seconds
```
must preserve the source media duration inherited from the input download index.

For example:
```json
"duration_seconds": 5427
```
This means the video/audio content duration is 5,427 seconds, equivalent to:
```text
1:30:27
```
This field is used by downstream stages for transcription, alignment, diarisation, and QC coverage calculations.

### Extraction runtime

The field:
```text
audio_extraction_duration_seconds
```
must store the runtime of the ffmpeg extraction command.

For example:
```json
"audio_extraction_duration_seconds": 7.038
```
This means ffmpeg took approximately 7.038 seconds to extract the WAV file.

### Required rule

The programme must not overwrite:
```text
duration_seconds
```
with ffmpeg runtime.

The following is incorrect:
```json
"duration_seconds": 7.038
```
when the source video duration is actually:
```json
"duration_seconds": 5427
```
The correct representation is:
```json
"duration_seconds": 5427,
"audio_extraction_duration_seconds": 7.038
```
---

# 10. Audio Index Design

The programme must write a curated audio index file:
```text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```
Each line should contain one JSON object combining:

1. selected input metadata from `jubilee_debates_index.ndjson`;
2. local source video path;
3. local extracted audio path;
4. audio extraction settings;
5. extraction run metadata;
6. item status.

## 10.1 Recommended audio index fields

Each audio index record should contain:

| Field                               | Source          | Description                                                                           |
|-------------------------------------|-----------------|---------------------------------------------------------------------------------------|
| `corpus_id`                         | input           | Internal stable corpus ID                                                             |
| `debate_format`                     | input           | e.g. `Surrounded`                                                                     |
| `sample_group`                      | input           | e.g. `carol_initial_sample`                                                           |
| `sample_order`                      | input           | Sample order                                                                          |
| `title`                             | input           | Selected title, if present                                                            |
| `title_selected`                    | input           | Title from selected sample                                                            |
| `title_extracted`                   | input           | Extracted YouTube title                                                               |
| `youtube_id`                        | input           | YouTube ID                                                                            |
| `youtube_url`                       | input           | Original YouTube URL                                                                  |
| `webpage_url`                       | input           | Canonical URL                                                                         |
| `channel`                           | input           | Selected channel, if present                                                          |
| `channel_selected`                  | input           | Expected channel from sample                                                          |
| `channel_extracted`                 | input           | Extracted channel                                                                     |
| `duration_seconds`                  | input           | Source video/audio duration in seconds; must remain unchanged from the download index |
| `duration_string`                   | input           | Human-readable source duration                                                        |
| `chapters`                          | input           | Chapter metadata                                                                      |
| `source_video_file`                 | local/input     | Project-relative local video file used for extraction                                 |
| `audio_file`                        | local           | Project-relative extracted WAV audio file                                             |
| `audio_format`                      | programme       | `wav`                                                                                 |
| `audio_codec`                       | programme       | `pcm_s16le`                                                                           |
| `audio_channels`                    | programme       | `1`                                                                                   |
| `audio_sample_rate`                 | programme       | `16000`                                                                               |
| `audio_sample_format`               | programme       | `s16`                                                                                 |
| `audio_file_size_bytes`             | local           | Size of output audio file                                                             |
| `audio_extraction_status`           | programme       | `success`, `failed`, `skipped_existing`, etc.                                         |
| `audio_extraction_run_id`           | programme       | Run ID                                                                                |
| `audio_extracted_at_utc`            | programme       | Extraction timestamp                                                                  |
| `audio_extraction_duration_seconds` | programme       | Runtime of ffmpeg extraction, not source media duration                               |
| `ffmpeg_version`                    | programme       | `ffmpeg` version                                                                      |
| `download_run_id`                   | input           | Previous stage run ID                                                                 |
| `downloaded_at_utc`                 | input           | Previous stage timestamp                                                              |
| `video_download_status`             | input/programme | Previous stage video download status, if available                                    |
| `metadata_status`                   | input           | Previous stage metadata status                                                        |
| `raw_metadata_file`                 | input           | Project-relative raw `.info.json` file                                                |
| `description_file`                  | input           | Project-relative description file                                                     |
| `subtitles_files`                   | input           | Project-relative subtitle files                                                       |
| `selected_by`                       | input           | e.g. `Carol`                                                                          |
| `selection_source`                  | input           | e.g. `email`                                                                          |
| `notes`                             | input           | Optional notes                                                                        |
| `error`                             | programme       | Error message, if any                                                                 |

## 10.2 Example audio index record
```json
{
  "corpus_id": "jubilee_surrounded_001",
  "debate_format": "Surrounded",
  "sample_group": "carol_initial_sample",
  "sample_order": 1,
  "title_selected": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)",
  "title_extracted": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk) | Surrounded",
  "youtube_id": "WV29R1M25n8",
  "youtube_url": "https://www.youtube.com/watch?v=WV29R1M25n8",
  "webpage_url": "https://www.youtube.com/watch?v=WV29R1M25n8",
  "duration_seconds": 5427,
  "duration_string": "1:30:27",
  "chapters": [
    {
      "start_time": 0,
      "title": "Intro",
      "end_time": 45
    }
  ],
  "source_video_file": "corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4",
  "audio_file": "corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav",
  "audio_format": "wav",
  "audio_codec": "pcm_s16le",
  "audio_channels": 1,
  "audio_sample_rate": 16000,
  "audio_sample_format": "s16",
  "audio_file_size_bytes": 173651160,
  "audio_extraction_status": "success",
  "audio_extraction_run_id": "20260817T190013Z",
  "audio_extracted_at_utc": "2026-08-17T19:00:20Z",
  "audio_extraction_duration_seconds": 7.038,
  "ffmpeg_version": "ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers",
  "download_run_id": "20260817T182305Z",
  "downloaded_at_utc": "2026-08-17T18:23:05Z",
  "video_download_status": "skipped_existing",
  "metadata_status": "skipped_existing",
  "raw_metadata_file": "corpus/01_jubilee_debates/metadata_raw/jubilee_surrounded_001.info.json",
  "description_file": "corpus/01_jubilee_debates/descriptions/jubilee_surrounded_001.description",
  "subtitles_files": [
    "corpus/01_jubilee_debates/subtitles/jubilee_surrounded_001.en-orig.vtt",
    "corpus/01_jubilee_debates/subtitles/jubilee_surrounded_001.en.vtt"
  ],
  "selected_by": "Carol",
  "selection_source": "email",
  "notes": null,
  "error": null
}
```
---

# 11. JSON Manifest Design

## 11.1 Manifest structure

The manifest must use this general structure:
```json
{
  "run_metadata": {
    "run_id": "20260817T190013Z",
    "tool_name": "extract_jubilee_debates_audio.py",
    "tool_version": "v1",
    "start_time": "2026-08-17T19:00:13Z",
    "end_time": "2026-08-17T19:01:01Z",
    "test_mode": false,
    "test_limit": 5,
    "reprocess": true,
    "workers": 1,
    "index_path": "corpus/01_jubilee_debates/jubilee_debates_index.ndjson",
    "input_dir": "corpus/01_jubilee_debates/videos",
    "output_dir": "corpus/02_jubilee_debates_audio",
    "audio_index_file": "corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson",
    "log_file": "corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log",
    "manifest_file": "corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest.json",
    "config": {
      "output_format": "wav",
      "audio_channels": 1,
      "audio_sample_rate": 16000,
      "audio_codec": "pcm_s16le",
      "audio_sample_format": "s16",
      "timeout_seconds": 7200,
      "max_retries": 1,
      "retry_delay_seconds": 5,
      "start_corpus_id": null
    },
    "ffmpeg": {
      "available": true,
      "version": "ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers"
    },
    "summary": {
      "input_records": 5,
      "eligible_records": 5,
      "ignored_records": 0,
      "invalid_records": 0,
      "planned_items": 5,
      "attempted_items": 5,
      "succeeded": 5,
      "failed": 0,
      "missing_input": 0,
      "skipped_existing": 0
    },
    "interrupted": false
  },
  "items": [
    {
      "corpus_id": "jubilee_surrounded_001",
      "youtube_id": "WV29R1M25n8",
      "youtube_url": "https://www.youtube.com/watch?v=WV29R1M25n8",
      "title_selected": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)",
      "title_extracted": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk) | Surrounded",
      "debate_format": "Surrounded",
      "duration_seconds": 5427,
      "duration_string": "1:30:27",
      "input_path": "corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4",
      "output_path": "corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav",
      "status": "success",
      "error": null,
      "return_code": 0,
      "retries": 0,
      "audio_extraction_duration_seconds": 7.038,
      "start_time": "2026-08-17T19:00:13Z",
      "end_time": "2026-08-17T19:00:20Z",
      "output_file_size_bytes": 173651160,
      "metadata": {
        "command": [
          "ffmpeg",
          "-y",
          "-i",
          "corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4",
          "-vn",
          "-ac",
          "1",
          "-ar",
          "16000",
          "-sample_fmt",
          "s16",
          "corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav"
        ],
        "attempts": []
      }
    }
  ],
  "invalid_records": [],
  "ignored_records": []
}
```
If no start corpus ID is provided, the manifest should record:
```json
"start_corpus_id": null
```
The manifest item field `duration_seconds` should preserve source media duration. The field `audio_extraction_duration_seconds` should record ffmpeg runtime.

## 11.2 Required item statuses

The following statuses must be supported:

| Status                   | Meaning                                                             |
|--------------------------|---------------------------------------------------------------------|
| `success`                | Audio was extracted successfully                                    |
| `failed`                 | Audio extraction was attempted but `ffmpeg` failed                  |
| `skipped_existing`       | Output audio file already existed and `--reprocess` was not enabled |
| `missing_input`          | Source video file was missing                                       |
| `failed_metadata`        | Input index record was invalid and could not be planned             |
| `ignored_not_downloaded` | Record was ignored because video download was not successful        |
| `interrupted`            | Processing stopped due to keyboard interruption                     |

---

## 11.3 Error field

The `error` field must be:

- `null` when there is no error;
- a short string when an error occurs.

For `ffmpeg` failures, the error should usually be derived from `stderr`.

Example:
```json
{
  "corpus_id": "jubilee_surrounded_001",
  "input_path": "corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4",
  "output_path": "corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav",
  "status": "failed",
  "error": "Invalid data found when processing input",
  "return_code": 1,
  "retries": 1
}
```
---

# 12. Logging Specification

The programme must write an append-only log file.

Default:
```text
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log
```
## Log format

Each line should follow this format:
```text
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```
Example:
```text
[2026-07-30 21:00:00] INFO  Starting extract_jubilee_debates_audio.py run_id=20260730T210000Z
```
## Required log events

The programme must log:

- startup;
- run ID;
- parsed configuration summary;
- resolved input index path;
- resolved input video directory;
- resolved output directory;
- audio extraction settings:
  - output format;
  - channel count;
  - sample rate;
  - sample format;
  - codec;
- test mode status;
- test limit;
- reprocess setting;
- start corpus ID, if provided;
- `ffmpeg` availability and version if available;
- number of input records read;
- number of eligible records;
- number of ignored records;
- number of invalid metadata records;
- number of planned audio extractions;
- each skipped existing audio file;
- each missing source video;
- each extraction attempt;
- each successful audio extraction;
- each failed audio extraction;
- each retry attempt;
- audio index write path;
- manifest write paths;
- end-of-run summary;
- keyboard interrupts;
- validation/configuration errors.

## Example log lines
```text
[2026-07-30 21:00:00] INFO  Starting extract_jubilee_debates_audio.py run_id=20260730T210000Z
[2026-07-30 21:00:00] INFO  Input index: corpus/01_jubilee_debates/jubilee_debates_index.ndjson
[2026-07-30 21:00:00] INFO  Input video directory: corpus/01_jubilee_debates/videos
[2026-07-30 21:00:00] INFO  Output directory: corpus/02_jubilee_debates_audio
[2026-07-30 21:00:00] INFO  Audio format: wav; channels=1; sample_rate=16000; codec=pcm_s16le; sample_fmt=s16
[2026-07-30 21:00:00] INFO  Test mode: true; test_limit=5
[2026-07-30 21:00:01] INFO  ffmpeg version: ffmpeg version ...
[2026-07-30 21:00:02] INFO  Loaded records: input=5 eligible=5 ignored=0 invalid=0
[2026-07-30 21:01:00] INFO  SUCCESS jubilee_surrounded_001 -> corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav
[2026-07-30 21:30:00] INFO  Wrote audio index: corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
[2026-07-30 21:30:00] INFO  Wrote latest manifest: corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest.json
[2026-07-30 21:30:00] INFO  Finished run: succeeded=5 failed=0 skipped_existing=0 missing_input=0 invalid_records=0
```
---

# 13. Error Handling and Resiliency

## 13.1 Configuration errors

Configuration errors must stop the programme before extraction begins.

Examples:

- input index file missing;
- input index file unreadable;
- input index contains invalid JSON;
- no eligible records found;
- input directory missing;
- output directory cannot be created;
- invalid command-line arguments;
- start corpus ID not found when `--start-corpus-id` is provided;
- `ffmpeg` is not installed or not found.

The programme must exit with code `2`.

---

## 13.2 Per-item errors

Per-item errors must not stop the full run.

Examples:

- source video file missing;
- unreadable source video file;
- unsupported video format;
- video file with no usable audio stream;
- `ffmpeg` timeout;
- `ffmpeg` non-zero return code;
- output file cannot be written.

For each per-item error:

- mark the item as one of:
  - `missing_input`;
  - `failed_metadata`;
  - `failed`
- capture a short error message;
- log the error;
- continue to the next item.

The programme must exit with code `1` if one or more per-item errors occur.

---

## 13.3 Keyboard interruption

If the user interrupts the programme with `Ctrl+C`, the programme must:

- stop processing;
- mark the run as interrupted in the manifest;
- write a partial manifest with completed results so far, where possible;
- log the interruption;
- exit with code `130`.

The manifest should include:
```json
"interrupted": true
```
inside `run_metadata`.

---

## 13.4 Exit codes

The programme must use the following exit-code conventions:

| Exit code | Meaning                                                                                                                 |
|----------:|-------------------------------------------------------------------------------------------------------------------------|
|       `0` | Completed with no failed attempted audio extractions, no missing inputs, and no invalid eligible metadata rows          |
|       `1` | Completed, but one or more audio extractions failed, source videos were missing, or eligible metadata rows were invalid |
|       `2` | Configuration or validation error                                                                                       |
|     `130` | Interrupted by user                                                                                                     |

Skipped existing files are not failures.

Records where `download_status` is not eligible are not failures.

---

# 14. Docstrings and In-code Documentation

The implementation must include clear docstrings.

## 14.1 Module-level docstring

At the top of `extract_jubilee_debates_audio.py`, include a module-level docstring explaining:

- purpose of the programme;
- expected input index file;
- source debate video input directory;
- audio output directory;
- use of `ffmpeg`;
- WhisperX/pyannote-ready audio format;
- default test mode;
- resumability behaviour;
- start-corpus-ID support;
- full-length extraction only;
- portable curated index paths;
- source-duration preservation;
- separate extraction-runtime metadata;
- example commands.

Suggested module docstring:
```python
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
relative to SCRIPT_DIR instead of as machine-specific absolute paths.

The curated audio index preserves source media duration in "duration_seconds" and
records ffmpeg runtime separately as "audio_extraction_duration_seconds".
"""
```
---

## 14.2 Function docstrings

All major functions must include docstrings describing:

- purpose;
- parameters;
- return values;
- whether the function performs I/O;
- error behaviour.

At minimum, docstrings are required for:

- `parse_args`
- `resolve_script_relative_path`
- `path_for_index`
- `validate_args`
- `setup_logging`
- `check_ffmpeg`
- `load_debate_index`
- `resolve_source_video_path`
- `plan_audio_extractions`
- `build_ffmpeg_command`
- `extract_one_audio`
- `make_audio_index_record`
- `write_audio_index`
- `write_manifests`
- `main`

---

# 15. Suggested Constants

The implementation should define constants near the top of the file:
```python
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
```
---

# 16. Development Notes

## 16.1 Initial implementation scope

The first implementation should prioritise:

- correct sequential execution;
- reliable input index reading;
- robust eligibility filtering by `download_status`;
- robust source-video path resolution;
- correct full-length audio extraction;
- correct Whisper-ready WAV format;
- reliable logging;
- robust manifest output;
- robust audio index output;
- safe resumability;
- optional start-corpus-ID support;
- clear error handling;
- script-relative path resolution;
- portable project-relative paths in the curated audio index;
- preserving source media duration;
- separating extraction runtime from media duration.

Parallel extraction can be prepared architecturally but does not need to be implemented in the first version.

## 16.2 Downstream pipeline note

This programme only prepares audio files.

Downstream stages may include:

- voice activity detection;
- transcript generation with Whisper or WhisperX;
- word-level or segment-level alignment;
- speaker diarisation with pyannote.audio;
- speaker-attributed transcript construction;
- quality-control reporting.

Those stages should have separate specifications and manifests.

---

# 17. Acceptance Criteria

The programme is considered complete when the following conditions are met:

1. Running from inside `cl_st1_ph0_carol/` works:

   ```bash
   python extract_jubilee_debates_audio.py
   ```

2. Running from the project root works:

   ```bash
   python cl_st1_ph0_carol/extract_jubilee_debates_audio.py
   ```

3. Default relative paths are resolved relative to the programme directory, not the current working directory.

4. The programme reads:

   ```text
   corpus/01_jubilee_debates/jubilee_debates_index.ndjson
   ```

5. The programme processes only records whose `download_status` indicates successful video availability.

6. The programme uses source video paths from `video_file` when available and usable.

7. The programme falls back to source videos from:

   ```text
   corpus/01_jubilee_debates/videos/
   ```

8. Each fallback source video is expected to exist as:

   ```text
   corpus/01_jubilee_debates/videos/<corpus_id>.mp4
   ```

9. The programme creates the output directory if needed:

   ```text
   corpus/02_jubilee_debates_audio/
   ```

10. Each extracted audio file is saved as:

    ```text
    corpus/02_jubilee_debates_audio/<corpus_id>.wav
    ```

11. The `ffmpeg` command is equivalent to:

    ```bash
    ffmpeg -y -i "<input_video>" -vn -ac 1 -ar 16000 -sample_fmt s16 "corpus/02_jubilee_debates_audio/<corpus_id>.wav"
    ```

12. The output audio is:
    - WAV;
    - mono;
    - 16 kHz;
    - signed 16-bit PCM.

13. Existing `.wav` files are skipped unless `--reprocess` is used.

14. Failed audio extractions do not stop the full batch.

15. Missing source videos are marked as `missing_input`.

16. Invalid eligible metadata rows are marked as `failed_metadata`.

17. The programme supports starting from a specific corpus ID with:

    ```bash
    --start-corpus-id CORPUS_ID
    ```

18. When `--start-corpus-id CORPUS_ID` is provided, the programme plans audio extraction from that corpus ID onward, preserving metadata order.

19. If `--start-corpus-id CORPUS_ID` is not found among eligible rows, the programme exits with a configuration error.

20. A log file is written at:

    ```text
    corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log
    ```

21. A latest manifest is written at:

    ```text
    corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest.json
    ```

22. A timestamped per-run manifest is also written.

23. An audio index is written at:

    ```text
    corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
    ```

24. The manifest records:
    - run metadata;
    - configuration;
    - `ffmpeg` version;
    - start corpus ID, if any;
    - per-item status;
    - errors;
    - timings;
    - summary counts;
    - generated `ffmpeg` command.

25. The audio index records:
    - source metadata;
    - source video path;
    - extracted audio path;
    - audio format metadata;
    - extraction status;
    - extraction run ID;
    - extraction timestamp.

26. The audio index writes project-internal file paths as project-relative paths, for example:

    ```text
    corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav
    ```

    rather than:

    ```text
    /home/<user>/PycharmProjects/cl_st1_carol/cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav
    ```

27. The audio index preserves source media duration in:

    ```text
    duration_seconds
    ```

    For example:

    ```json
    "duration_seconds": 5427
    ```

28. The audio index records ffmpeg runtime separately in:

    ```text
    audio_extraction_duration_seconds
    ```

    For example:

    ```json
    "audio_extraction_duration_seconds": 7.038
    ```

29. The programme must not overwrite source media `duration_seconds` with ffmpeg runtime duration.

30. The programme exits with:
    - `0` if all attempted audio extractions succeed or are skipped and there are no missing inputs or invalid eligible metadata rows;
    - `1` if any attempted extraction fails, any eligible input video is missing, or any eligible metadata row is invalid;
    - `2` for configuration errors;
    - `130` for keyboard interruption.

31. The programme does not segment, transcribe, align, diarise, or analyse audio.

---

# 18. Short README Section

The following section can be added to project documentation.

## Extract Jubilee debate audio

The `extract_jubilee_debates_audio.py` programme extracts Whisper-ready audio from downloaded Jubilee debate videos.

It reads the curated debate index:
```text
corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```
Only records whose `download_status` indicates that the source video is available are processed.

Source videos are resolved from the `video_file` field when available. Otherwise, videos are read from:
```text
corpus/01_jubilee_debates/videos/
```
Each fallback source video is expected to exist as:
```text
corpus/01_jubilee_debates/videos/<corpus_id>.mp4
```
Audio files are written to:
```text
corpus/02_jubilee_debates_audio/
```
Each audio file is named after its `corpus_id`:
```text
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```
The generated audio extraction command is equivalent to:
```bash
ffmpeg -y -i "<input_video>" -vn -ac 1 -ar 16000 -sample_fmt s16 "corpus/02_jubilee_debates_audio/<corpus_id>.wav"
```
The resulting audio is suitable for Whisper, WhisperX, and pyannote.audio:

- WAV format;
- mono;
- 16 kHz;
- signed 16-bit PCM.

The generated audio index uses portable project-relative paths.

The field `duration_seconds` preserves the original media duration. The field `audio_extraction_duration_seconds` records how long ffmpeg took to extract the WAV file.

Default test run:
```bash
python extract_jubilee_debates_audio.py
```
This processes up to 5 eligible debates.

Full run:
```bash
python extract_jubilee_debates_audio.py --no-test-mode
```
To resume planning from a specific corpus ID onward, use:
```bash
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```
The programme is safe to re-run: existing audio files are skipped by default.

To force re-extraction, use:
```bash
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --reprocess
```
The programme writes:
```text
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest.json
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```
A timestamped per-run manifest is also created for each execution.

This programme extracts full-length audio only. Transcription, alignment, segmentation, and diarisation should be handled by later pipeline stages.

---

# 19. Validation Commands

After running full audio extraction, the following checks are recommended.

## Check extraction statuses
```bash
grep -o '"audio_extraction_status": "[^"]*"' corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```
Expected values should be:
```text
"audio_extraction_status": "success"
```
or, on a safe rerun:
```text
"audio_extraction_status": "skipped_existing"
```
## Check source media durations
```bash
grep -o '"duration_seconds": [0-9.]*' corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```
Expected values for the current five-debate sample are approximately:
```text
5427
6053
5903
6818
5387
```
## Check ffmpeg runtime values
```bash
grep -o '"audio_extraction_duration_seconds": [0-9.]*' corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```
These values should be much smaller than source media duration and represent the runtime of the extraction process.

## Check portability
```bash
grep -n '/home/' corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```
Expected result: no output.

---

# 20. Design Decision Summary

| Decision                                        | Rationale                                                                                 |
|-------------------------------------------------|-------------------------------------------------------------------------------------------|
| Extract WAV only                                | Keeps the programme focused on WhisperX and pyannote.audio preparation                    |
| Use mono audio                                  | Common ASR/diarisation preprocessing format                                               |
| Use 16 kHz sample rate                          | Standard and efficient for Whisper-family pipelines                                       |
| Use signed 16-bit PCM                           | Broad compatibility and stable downstream handling                                        |
| Extract full-length audio only                  | Keeps this stage simple, auditable, and reproducible                                      |
| Defer segmentation                              | Segmentation has separate concerns around timestamps, chunk manifests, and reconstruction |
| Defer transcription and diarisation             | Those are downstream analytical stages                                                    |
| Use `corpus_id` for filenames                   | Stable, clean, research-oriented naming                                                   |
| Use script-relative path resolution             | Prevents accidental path errors when running from different directories                   |
| Write an audio index                            | Makes downstream WhisperX and pyannote.audio stages easier                                |
| Write project-relative paths in the audio index | Makes downstream metadata portable between local machines and EC2                         |
| Preserve source `duration_seconds`              | Keeps duration-based transcription, diarisation, and QC metrics meaningful                |
| Store extraction runtime separately             | Allows ffmpeg performance tracking without corrupting source media metadata               |
| Write logs and manifests                        | Supports reproducibility and auditability                                                 |
