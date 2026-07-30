# `extract_jubilee_debates_audio.py` — Programme Specification for Development

## 1. Programme Summary

`extract_jubilee_debates_audio.py` is a batch-processing programme that extracts full-length audio files from previously downloaded Jubilee debate video files.

The programme is part of **Corpus Linguistics — Study 1 — Carol, Phase 0: Speaker Diarisation Test**.

The main research motivation is to prepare audio files for testing whether **Gemini 1.5 Pro** can transcribe long, provocative debates while differentiating speaker turns.

The source video files are produced by:

```text
cl_st1_ph0_carol/download_jubilee_debates.py
```

and are expected to be located in:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/
```

The programme reads the curated Jubilee debate index:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```

For each eligible debate, it extracts a full-length audio file into:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/
```

The programme supports multiple audio extraction profiles:

1. `gemini_flac` — default, lossless compressed audio for Gemini testing;
2. `gemini_wav` — uncompressed high-quality WAV for Gemini testing;
3. `whisper_wav` — 16 kHz mono WAV compatible with Whisper/WhisperX-style pipelines.

The default profile should be:

```text
gemini_flac
```

because it preserves more acoustic information than the Whisper-style 16 kHz mono profile while reducing file size compared with uncompressed WAV.

---

## 2. Scope

### 2.1 In scope

This programme must:

- read the curated Jubilee debate index;
- identify successfully downloaded video files;
- validate required metadata fields;
- locate source video files;
- extract **full-length audio** from each video file;
- support configurable audio extraction profiles;
- write extracted audio files to a dedicated output directory;
- write an updated audio index;
- write logs;
- write latest and timestamped run manifests;
- support safe re-runs by skipping existing outputs;
- support reprocessing;
- support starting from a specific `corpus_id`;
- continue processing after per-item failures.

### 2.2 Out of scope

This programme must **not** segment audio files.

Audio segmentation should be handled by a later pipeline programme, for example:

```text
segment_jubilee_debates_audio.py
```

or similar.

Segmentation is intentionally deferred because it will require a separate design for:

- fixed-duration segmentation;
- chapter-based segmentation;
- time-offset preservation;
- Gemini upload constraints;
- segment-level manifests;
- prompt batching;
- reconstruction of full transcripts from segment-level outputs.

---

## 3. Path Resolution Policy

The programme must resolve its **default paths relative to the directory where `extract_jubilee_debates_audio.py` is located**, not relative to the current working directory.

If the script is located at:

```text
cl_st1_ph0_carol/extract_jubilee_debates_audio.py
```

then the default input index path:

```text
corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```

must resolve to:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```

and the default output directory:

```text
corpus/02_jubilee_debates_audio/
```

must resolve to:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/
```

This policy ensures that the programme works correctly whether executed from:

```text
cl_st1_carol/
```

or from:

```text
cl_st1_carol/cl_st1_ph0_carol/
```

or from another current working directory.

### 3.1 Internal path base

The implementation should define a script directory equivalent to:

```python
SCRIPT_DIR = Path(__file__).resolve().parent
```

Relative default paths should then be resolved against `SCRIPT_DIR`.

### 3.2 Absolute paths

If the user supplies an absolute path for arguments such as `--index`, `--input-dir`, `--output-dir`, `--log-file`, `--manifest-file`, or `--audio-index-file`, the programme must preserve that absolute path.

### 3.3 Relative command-line paths

For consistency with the download programme, relative command-line paths should also be resolved relative to the programme directory.

---

## 4. Default Paths

The following defaults are relative to the programme directory `cl_st1_ph0_carol/`.

### Input curated debate index

Default argument value:

```text
corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```

Resolved project path:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```

### Source video directory

Default argument value:

```text
corpus/01_jubilee_debates/videos/
```

Resolved project path:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/
```

### Audio output directory

Default argument value:

```text
corpus/02_jubilee_debates_audio/
```

Resolved project path:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/
```

### Latest run manifest

Default argument value:

```text
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest.json
```

Resolved project path:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest.json
```

### Timestamped run manifest pattern

Resolved project path pattern:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest_<run_id>.json
```

### Log file

Default argument value:

```text
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log
```

Resolved project path:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log
```

### Audio index file

Default argument value:

```text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```

Resolved project path:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```

---

## 5. Output Directory Structure

The programme should organise outputs as follows:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/
├── gemini_flac/
│   ├── jubilee_surrounded_001.flac
│   ├── jubilee_surrounded_002.flac
│   └── ...
├── gemini_wav/
│   ├── jubilee_surrounded_001.wav
│   ├── jubilee_surrounded_002.wav
│   └── ...
├── whisper_wav/
│   ├── jubilee_surrounded_001.wav
│   ├── jubilee_surrounded_002.wav
│   └── ...
├── jubilee_debates_audio_index.ndjson
├── extract_jubilee_debates_audio.log
├── extract_jubilee_debates_audio_manifest.json
└── extract_jubilee_debates_audio_manifest_<run_id>.json
```

The programme does not need to create all profile subdirectories on every run. It should create at least the subdirectory corresponding to the selected profile.

For the default profile, the output directory should be:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/
```

---

## 6. Input Specification

The input file is an NDJSON curated index generated by `download_jubilee_debates.py`.

Default resolved path:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```

Each line is a JSON object representing one debate.

### 6.1 Required input fields

Each eligible record must contain:

| Field             |   Type | Description                                               |
|-------------------|-------:|-----------------------------------------------------------|
| `corpus_id`       | string | Internal corpus identifier, e.g. `jubilee_surrounded_001` |
| `video_file`      | string | Path to the downloaded video file                         |
| `download_status` | string | Download status from the previous pipeline stage          |

### 6.2 Recommended input fields to preserve

The programme should preserve these fields in the audio index and manifest when present:

| Field               | Description                                |
|---------------------|--------------------------------------------|
| `debate_format`     | Debate format, e.g. `Surrounded`           |
| `sample_group`      | Sample group, e.g. `carol_initial_sample`  |
| `sample_order`      | Order in Carol’s sample                    |
| `title_selected`    | Title from Carol’s sample                  |
| `title_extracted`   | Title extracted by `yt-dlp`                |
| `youtube_id`        | YouTube video ID                           |
| `youtube_url`       | Original YouTube URL                       |
| `webpage_url`       | Canonical YouTube URL                      |
| `channel_selected`  | Expected channel from sample               |
| `channel_extracted` | Extracted channel                          |
| `duration_seconds`  | Video duration in seconds                  |
| `duration_string`   | Human-readable duration                    |
| `chapters`          | Chapter metadata                           |
| `subtitles_files`   | Existing subtitle files                    |
| `raw_metadata_file` | Raw `.info.json` file                      |
| `description_file`  | Description file                           |
| `download_run_id`   | Run ID from video download stage           |
| `downloaded_at_utc` | Timestamp from video download stage        |
| `yt_dlp_version`    | `yt-dlp` version from video download stage |
| `selected_by`       | Selector, e.g. `Carol`                     |
| `selection_source`  | e.g. `email`                               |
| `notes`             | Optional notes                             |

### 6.3 Example input record

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
  "video_file": "cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4",
  "download_status": "success",
  "metadata_status": "success"
}
```

---

## 7. Eligibility Rules

The programme must:

1. read all records from the input NDJSON index;
2. select records whose `download_status` is `success` or `skipped_existing`;
3. validate that each selected record has a non-empty `corpus_id`;
4. locate the source video file using:
    - the `video_file` field, when present and valid;
    - otherwise `<input_dir>/<corpus_id>.mp4`;
5. verify that the source video file exists;
6. preserve record order from the input index.

### 7.1 Download status eligibility

The following `download_status` values should be eligible:

```text
success
skipped_existing
```

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

Records not eligible because of `download_status` should be counted as ignored records, not as errors.

### 7.2 Invalid metadata rows

If an eligible row is missing `corpus_id`, it must:

- not be processed;
- be recorded in `invalid_records` in the manifest;
- be marked as `failed_metadata`;
- be logged;
- cause exit code `1` after the run, unless no processing is attempted and the implementation treats it as a configuration error.

Invalid JSON lines are configuration errors and must cause exit code `2`.

---

## 8. Audio Extraction Profiles

The programme must support the following profiles:

| Profile       | Output extension | Channels | Sample rate | Codec / sample format | Intended use                             |
|---------------|------------------|---------:|------------:|-----------------------|------------------------------------------|
| `gemini_flac` | `.flac`          |        2 |       44100 | FLAC                  | Default profile for Gemini testing       |
| `gemini_wav`  | `.wav`           |        2 |       44100 | PCM signed 16-bit     | Uncompressed high-quality Gemini testing |
| `whisper_wav` | `.wav`           |        1 |       16000 | PCM signed 16-bit     | Whisper/WhisperX compatibility           |

### 8.1 Default profile

The default profile must be:

```text
gemini_flac
```

Rationale:

- preserves richer acoustic information than 16 kHz mono;
- preserves stereo information if present;
- uses lossless compression;
- produces smaller files than uncompressed WAV;
- is better suited for a fair Gemini 1.5 Pro speaker-turn transcription test than the Whisper-oriented profile.

### 8.2 `gemini_flac` profile

Command pattern:

```bash
ffmpeg -y \
  -i "<input_video>" \
  -vn \
  -ac 2 \
  -ar 44100 \
  -c:a flac \
  "<output_audio>.flac"
```

Conceptual subprocess command:

```python
[
    "ffmpeg",
    "-y",
    "-i",
    str(input_video),
    "-vn",
    "-ac",
    "2",
    "-ar",
    "44100",
    "-c:a",
    "flac",
    str(output_audio),
]
```

### 8.3 `gemini_wav` profile

Command pattern:

```bash
ffmpeg -y \
  -i "<input_video>" \
  -vn \
  -ac 2 \
  -ar 44100 \
  -c:a pcm_s16le \
  "<output_audio>.wav"
```

Conceptual subprocess command:

```python
[
    "ffmpeg",
    "-y",
    "-i",
    str(input_video),
    "-vn",
    "-ac",
    "2",
    "-ar",
    "44100",
    "-c:a",
    "pcm_s16le",
    str(output_audio),
]
```

### 8.4 `whisper_wav` profile

Command pattern:

```bash
ffmpeg -y \
  -i "<input_video>" \
  -vn \
  -ac 1 \
  -ar 16000 \
  -sample_fmt s16 \
  "<output_audio>.wav"
```

Conceptual subprocess command:

```python
[
    "ffmpeg",
    "-y",
    "-i",
    str(input_video),
    "-vn",
    "-ac",
    "1",
    "-ar",
    "16000",
    "-sample_fmt",
    "s16",
    str(output_audio),
]
```

---

## 9. Audio Extraction Behaviour

### 9.1 Full-length extraction only

The programme must extract the **entire audio track** from each source video.

It must not split, segment, trim, or chunk audio.

### 9.2 Output filename

The output filename must be based on `corpus_id`.

For example:

```text
corpus_id = jubilee_surrounded_001
```

With the `gemini_flac` profile, the output file must be:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/jubilee_surrounded_001.flac
```

With the `gemini_wav` profile, the output file must be:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_wav/jubilee_surrounded_001.wav
```

With the `whisper_wav` profile, the output file must be:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/whisper_wav/jubilee_surrounded_001.wav
```

### 9.3 Existing files

If the output audio file already exists and `--reprocess` is not enabled:

- do not call `ffmpeg`;
- mark the item as `skipped_existing`;
- log the skip;
- include the item in the manifest;
- include the item in the audio index.

If `--reprocess` is enabled:

- call `ffmpeg`;
- allow output to be overwritten because the command includes `-y`.

### 9.4 Missing source videos

If the expected source video file does not exist, the programme must:

- not call `ffmpeg`;
- mark the item as `missing_input`;
- record the expected input path in the manifest;
- log the missing input;
- continue processing other records;
- exit with code `1` at the end of the run.

### 9.5 `ffmpeg` failures

If `ffmpeg` returns a non-zero exit code, the programme must:

- capture the failure;
- mark the item as `failed`;
- save a short error summary in the manifest;
- log the failure;
- continue with the next item.

The programme must not stop the entire batch because one extraction fails.

### 9.6 Retries

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

## 10. Audio Index Design

The programme must write a curated audio index file:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```

Each line should contain one JSON object combining:

1. selected input metadata from `jubilee_debates_index.ndjson`;
2. local source video path;
3. local extracted audio path;
4. audio extraction profile metadata;
5. extraction run metadata;
6. item status.

### 10.1 Recommended audio index fields

Each audio index record should contain:

| Field                     | Source      | Description                          |
|---------------------------|-------------|--------------------------------------|
| `corpus_id`               | input       | Internal stable corpus ID            |
| `debate_format`           | input       | e.g. `Surrounded`                    |
| `sample_group`            | input       | e.g. `carol_initial_sample`          |
| `sample_order`            | input       | Sample order                         |
| `title_selected`          | input       | Title from Carol’s sample            |
| `title_extracted`         | input       | Title extracted by `yt-dlp`          |
| `youtube_id`              | input       | YouTube ID                           |
| `youtube_url`             | input       | Original YouTube URL                 |
| `webpage_url`             | input       | Canonical URL                        |
| `duration_seconds`        | input       | Video duration in seconds            |
| `duration_string`         | input       | Human-readable duration              |
| `chapters`                | input       | Chapter metadata                     |
| `source_video_file`       | local/input | Local video file used for extraction |
| `audio_file`              | local       | Extracted audio file                 |
| `audio_profile`           | programme   | e.g. `gemini_flac`                   |
| `audio_format`            | programme   | e.g. `flac`, `wav`                   |
| `audio_codec`             | programme   | e.g. `flac`, `pcm_s16le`             |
| `audio_channels`          | programme   | e.g. `2`, `1`                        |
| `audio_sample_rate`       | programme   | e.g. `44100`, `16000`                |
| `audio_sample_format`     | programme   | e.g. `s16` or `null`                 |
| `audio_file_size_bytes`   | local       | Size of output audio file            |
| `audio_extraction_status` | programme   | `success`, `failed`, etc.            |
| `audio_extraction_run_id` | programme   | Run ID                               |
| `audio_extracted_at_utc`  | programme   | Extraction timestamp                 |
| `ffmpeg_version`          | programme   | `ffmpeg` version                     |
| `download_run_id`         | input       | Previous stage run ID                |
| `downloaded_at_utc`       | input       | Previous stage timestamp             |
| `video_download_status`   | input       | Previous stage status                |
| `metadata_status`         | input       | Previous stage metadata status       |
| `raw_metadata_file`       | input       | Raw `.info.json` file                |
| `description_file`        | input       | Description file                     |
| `subtitles_files`         | input       | Subtitle files                       |
| `selected_by`             | input       | e.g. `Carol`                         |
| `selection_source`        | input       | e.g. `email`                         |
| `notes`                   | input       | Optional notes                       |

### 10.2 Example audio index record

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
  "chapters": [],
  "source_video_file": "cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4",
  "audio_file": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/jubilee_surrounded_001.flac",
  "audio_profile": "gemini_flac",
  "audio_format": "flac",
  "audio_codec": "flac",
  "audio_channels": 2,
  "audio_sample_rate": 44100,
  "audio_sample_format": null,
  "audio_file_size_bytes": null,
  "audio_extraction_status": "success",
  "audio_extraction_run_id": "20260730T210000Z",
  "audio_extracted_at_utc": "2026-07-30T21:00:00Z",
  "ffmpeg_version": "unknown",
  "download_run_id": "20260730T194409Z",
  "downloaded_at_utc": "2026-07-30T19:56:01Z",
  "video_download_status": "success",
  "metadata_status": "success",
  "raw_metadata_file": "cl_st1_ph0_carol/corpus/01_jubilee_debates/metadata_raw/jubilee_surrounded_001.info.json",
  "description_file": "cl_st1_ph0_carol/corpus/01_jubilee_debates/descriptions/jubilee_surrounded_001.description",
  "subtitles_files": [],
  "selected_by": "Carol",
  "selection_source": "email",
  "notes": null
}
```

---

## 11. Command-line Interface

### 11.1 Default usage

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

- input index:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```

- source video directory:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/
```

- audio output directory:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/
```

- audio profile:

```text
gemini_flac
```

- test mode enabled;
- test limit: `5`;
- sequential processing;
- skip existing audio files;
- no start corpus ID filter.

Because the current sample contains five debates, the default test run processes the full current sample unless audio files already exist and are skipped.

---

## 12. Optional Arguments

### 12.1 Input index file

```bash
--index PATH
```

Default argument value:

```text
corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```

Description:

Path to the NDJSON curated debate index.

Relative paths are resolved relative to the programme directory.

---

### 12.2 Input video directory

```bash
--input-dir PATH
```

Default argument value:

```text
corpus/01_jubilee_debates/videos/
```

Description:

Directory containing source video files.

Used as a fallback when the `video_file` field is absent or unusable.

Relative paths are resolved relative to the programme directory.

---

### 12.3 Output directory

```bash
--output-dir PATH
```

Default argument value:

```text
corpus/02_jubilee_debates_audio/
```

Description:

Base directory where extracted audio files, logs, manifests, and audio index files are written.

Relative paths are resolved relative to the programme directory.

---

### 12.4 Audio profile

```bash
--profile PROFILE
```

Default:

```text
gemini_flac
```

Allowed values:

```text
gemini_flac
gemini_wav
whisper_wav
```

Description:

Selects the audio extraction profile.

---

### 12.5 Test mode

```bash
--test-mode
--no-test-mode
```

Default:

```text
--test-mode
```

When enabled, only the first `--test-limit` planned records are processed.

---

### 12.6 Test limit

```bash
--test-limit N
```

Default:

```text
5
```

Must be a positive integer.

---

### 12.7 Reprocess existing outputs

```bash
--reprocess
```

Default:

```text
False
```

When omitted, existing audio files are skipped.

When provided, the programme re-runs `ffmpeg` and overwrites or refreshes outputs.

---

### 12.8 Start corpus ID

```bash
--start-corpus-id CORPUS_ID
```

Default:

```text
None
```

Example:

```bash
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

Behaviour:

- preserve input order;
- ignore eligible records before the specified `corpus_id`;
- include the specified record;
- include all following eligible records;
- fail fast if the `corpus_id` is not found among eligible records.

---

### 12.9 Log file

```bash
--log-file PATH
```

Default argument value:

```text
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log
```

Relative paths are resolved relative to the programme directory.

---

### 12.10 Manifest file

```bash
--manifest-file PATH
```

Default argument value:

```text
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest.json
```

Relative paths are resolved relative to the programme directory.

---

### 12.11 Audio index file

```bash
--audio-index-file PATH
```

Default argument value:

```text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```

Relative paths are resolved relative to the programme directory.

---

### 12.12 Workers

```bash
--workers N
```

Default:

```text
1
```

For the first implementation, only `--workers 1` is supported.

---

### 12.13 Timeout

```bash
--timeout SECONDS
```

Default:

```text
7200
```

Debate videos are long, so a two-hour per-item timeout is appropriate for the initial implementation.

---

### 12.14 Maximum retries

```bash
--max-retries N
```

Default:

```text
1
```

Must be zero or a positive integer.

---

### 12.15 Retry delay

```bash
--retry-delay SECONDS
```

Default:

```text
5
```

Must be zero or a positive integer.

---

## 13. Example Commands

### Default run from inside `cl_st1_ph0_carol/`

```bash
python extract_jubilee_debates_audio.py
```

### Default run from project root

```bash
python cl_st1_ph0_carol/extract_jubilee_debates_audio.py
```

### Full run

```bash
python extract_jubilee_debates_audio.py --no-test-mode
```

### Full run with explicit default Gemini FLAC profile

```bash
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --profile gemini_flac
```

### Extract uncompressed Gemini WAV files

```bash
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --profile gemini_wav
```

### Extract Whisper-compatible WAV files

```bash
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --profile whisper_wav
```

### Resume from a specific corpus item

```bash
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

### Reprocess existing audio files

```bash
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --reprocess
```

### Full run with explicit paths

```bash
python extract_jubilee_debates_audio.py \
  --index corpus/01_jubilee_debates/jubilee_debates_index.ndjson \
  --input-dir corpus/01_jubilee_debates/videos \
  --output-dir corpus/02_jubilee_debates_audio \
  --profile gemini_flac \
  --no-test-mode
```

---

## 14. Validation Rules

The programme must fail fast with a configuration error if:

- the input index file does not exist;
- the input index path is not a file;
- the input index file is unreadable;
- the input index contains invalid JSON lines;
- no eligible records are found;
- `--profile` is not one of the supported profiles;
- the input video directory does not exist;
- the input video directory is not a directory;
- the output directory cannot be created;
- `--test-limit` is less than or equal to zero;
- `--workers` is less than or equal to zero;
- `--workers` is not `1` in the first implementation;
- `--timeout` is less than or equal to zero;
- `--max-retries` is negative;
- `--retry-delay` is negative;
- `--start-corpus-id` is provided but empty;
- `--start-corpus-id` is provided but not found among eligible records;
- `ffmpeg` is not available on the system path.

The programme should check `ffmpeg` availability with:

```bash
ffmpeg -version
```

A validation error should:

- be printed clearly to the console or log;
- be written to the log if logging has already been configured;
- cause the programme to exit with code `2`.

---

## 15. Environment and Dependencies

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

## 16. Core Processing Flow

The programme should follow this workflow:

1. **Startup**
    - Parse command-line arguments.
    - Resolve relative paths against the programme directory.
    - Generate UTC `run_id`.
    - Ensure the output directory exists.
    - Ensure the selected profile output subdirectory exists.
    - Configure logging.
    - Validate simple argument values.
    - Check that `ffmpeg` is available.

2. **Index loading**
    - Open the NDJSON input index.
    - Read records line by line.
    - Parse each JSON object.
    - Count total records.
    - Select only records whose `download_status` is eligible.
    - Validate required fields for selected records:
        - `corpus_id`.
    - Preserve input order.
    - Record invalid eligible rows in the manifest.

3. **Planning**
    - If `--start-corpus-id` is provided:
        - locate the specified `corpus_id` in the eligible record list;
        - discard eligible records before it;
        - include the specified record and all following eligible records;
        - fail fast if the specified `corpus_id` is not found.
    - For each selected eligible record:
        - compute source video path;
        - compute output audio path according to the selected profile;
        - check whether the source video exists;
        - decide whether to skip or extract audio.
    - If the source video is missing:
        - mark the item as `missing_input`;
        - log the missing input;
        - do not run `ffmpeg`.
    - If the output audio file exists and `--reprocess` is not enabled:
        - mark the item as `skipped_existing`.
    - If the output file does not exist or `--reprocess` is enabled:
        - plan the item for extraction.
    - If test mode is enabled:
        - limit the planned extraction list to `--test-limit`.

4. **Execution**
    - For each planned item:
        - build the `ffmpeg` command according to the selected profile;
        - run `ffmpeg`;
        - capture stdout, stderr, return code, timing, and exceptions;
        - retry according to `--max-retries`;
        - mark the item as `success` or `failed`;
        - record output file size when available.

5. **Audio index generation**
    - Combine input metadata with audio extraction metadata.
    - Write `jubilee_debates_audio_index.ndjson`.

6. **Manifest writing**
    - Write the latest manifest.
    - Write the timestamped manifest.

7. **Exit**
    - Exit `0` if all attempted items succeeded or were skipped and there are no missing inputs or invalid eligible metadata rows.
    - Exit `1` if one or more attempted extractions failed, one or more source videos were missing, or invalid eligible metadata records exist.
    - Exit `2` for configuration errors.
    - Exit `130` for keyboard interruption.

---

## 17. Separation of Concerns

The implementation should be organised around the following responsibilities.

### CLI parsing

```python
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments and resolve paths."""
```

### Path resolution

```python
def resolve_script_relative_path(path: Path) -> Path:
    """Resolve relative paths against the programme directory."""
```

### Logging

```python
def setup_logging(log_file: Path) -> logging.Logger:
    """Configure append-only logging."""
```

### Output directories

```python
def ensure_output_dirs(output_dir: Path, profile: str) -> dict[str, Path]:
    """Create the output directory structure for the selected profile."""
```

### Validation

```python
def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and paths."""
```

### `ffmpeg` availability

```python
def check_ffmpeg() -> dict:
    """Check whether ffmpeg is available and return version metadata."""
```

### Index loading

```python
def load_debate_index(
    index_path: Path,
) -> tuple[list[dict], list[dict], int, int]:
    """Load and validate eligible debate records from the NDJSON audio source index."""
```

Suggested return values:

```text
eligible_records, invalid_records, total_records, ignored_records
```

### Planning

```python
def plan_audio_extractions(
    records: list[dict],
    input_dir: Path,
    output_dir: Path,
    profile: str,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_corpus_id: str | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Create planned, skipped-existing, and missing-input audio extraction records."""
```

Suggested return values:

```text
planned, skipped_existing, missing_input
```

### Profile configuration

```python
def get_audio_profile_config(profile: str) -> dict:
    """Return ffmpeg and output configuration for the selected audio profile."""
```

### Command building

```python
def build_ffmpeg_command(
    input_path: Path,
    output_path: Path,
    profile_config: dict,
) -> list[str]:
    """Build the ffmpeg command for one audio extraction."""
```

### Extraction

```python
def extract_one_audio(
    corpus_id: str,
    input_path: Path,
    output_path: Path,
    profile_config: dict,
    timeout: int,
    max_retries: int,
    retry_delay: int,
    logger: logging.Logger,
) -> dict:
    """Extract one audio file with ffmpeg and return a structured result."""
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
    run_id: str,
) -> tuple[Path, Path]:
    """Write latest and timestamped manifest files."""
```

### Main orchestration

```python
def main() -> int:
    """Run the complete Jubilee debate audio extraction workflow."""
```

---

## 18. Required Item Statuses

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

## 19. Manifest Design

The manifest must use this general structure:

```json
{
  "run_metadata": {
    "run_id": "20260730T210000Z",
    "tool_name": "extract_jubilee_debates_audio.py",
    "tool_version": "v1",
    "start_time": "2026-07-30T21:00:00Z",
    "end_time": "2026-07-30T21:30:00Z",
    "test_mode": true,
    "test_limit": 5,
    "reprocess": false,
    "workers": 1,
    "index_path": "cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson",
    "input_dir": "cl_st1_ph0_carol/corpus/01_jubilee_debates/videos",
    "output_dir": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio",
    "audio_index_file": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson",
    "log_file": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log",
    "manifest_file": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest.json",
    "config": {
      "profile": "gemini_flac",
      "output_format": "flac",
      "audio_channels": 2,
      "audio_sample_rate": 44100,
      "audio_codec": "flac",
      "audio_sample_format": null,
      "timeout_seconds": 7200,
      "max_retries": 1,
      "retry_delay_seconds": 5,
      "start_corpus_id": null
    },
    "ffmpeg": {
      "available": true,
      "version": "ffmpeg version ..."
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
      "input_path": "cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4",
      "output_path": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/jubilee_surrounded_001.flac",
      "profile": "gemini_flac",
      "status": "success",
      "error": null,
      "return_code": 0,
      "retries": 0,
      "duration_seconds": 240.5,
      "start_time": "2026-07-30T21:01:00Z",
      "end_time": "2026-07-30T21:05:00Z",
      "output_file_size_bytes": 123456789,
      "metadata": {
        "duration_seconds": 5427,
        "duration_string": "1:30:27",
        "command": [
          "ffmpeg",
          "-y",
          "-i",
          "cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4",
          "-vn",
          "-ac",
          "2",
          "-ar",
          "44100",
          "-c:a",
          "flac",
          "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/jubilee_surrounded_001.flac"
        ],
        "attempts": []
      }
    }
  ],
  "invalid_records": [],
  "ignored_records": []
}
```

The manifest may include absolute paths depending on how paths were resolved internally. This is acceptable, provided the paths identify the actual files used during the run.

---

## 20. Logging Specification

The programme must write an append-only UTF-8 log file:

```text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log
```

Each line should follow:

```text
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```

Required log events:

- startup;
- run ID;
- parsed configuration;
- resolved input index path;
- resolved input video directory;
- resolved output directory;
- selected audio profile;
- audio profile settings:
    - output format;
    - channel count;
    - sample rate;
    - codec;
    - sample format, if applicable;
- test mode status;
- test limit;
- reprocess status;
- start corpus ID, if provided;
- `ffmpeg` availability and version;
- number of input records loaded;
- number of eligible records;
- number of ignored records;
- number of invalid records;
- number of planned extractions;
- number of skipped existing items;
- number of missing input files;
- each skipped item;
- each missing input item;
- each extraction attempt;
- each retry;
- each successful extraction;
- each failed extraction;
- audio index writing;
- manifest writing;
- final summary;
- validation errors;
- keyboard interruption.

Example log lines:

```text
[2026-07-30 21:00:00] INFO  Starting extract_jubilee_debates_audio.py run_id=20260730T210000Z
[2026-07-30 21:00:00] INFO  Input index: cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
[2026-07-30 21:00:00] INFO  Input video directory: cl_st1_ph0_carol/corpus/01_jubilee_debates/videos
[2026-07-30 21:00:00] INFO  Output directory: cl_st1_ph0_carol/corpus/02_jubilee_debates_audio
[2026-07-30 21:00:00] INFO  Audio profile: gemini_flac; format=flac; channels=2; sample_rate=44100; codec=flac
[2026-07-30 21:00:01] INFO  ffmpeg version: ffmpeg version ...
[2026-07-30 21:00:02] INFO  Loaded records: input=5 eligible=5 ignored=0 invalid=0
[2026-07-30 21:01:00] INFO  SUCCESS jubilee_surrounded_001 -> corpus/02_jubilee_debates_audio/gemini_flac/jubilee_surrounded_001.flac
[2026-07-30 21:30:00] INFO  Wrote latest manifest: corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest.json
[2026-07-30 21:30:00] INFO  Finished run: succeeded=5 failed=0 skipped_existing=0 missing_input=0
```

---

## 21. Error Handling and Resiliency

### 21.1 Configuration errors

Configuration errors must stop the programme before extraction begins.

Examples:

- input index file missing;
- input index path is not a file;
- invalid JSON line in the input index;
- unsupported audio profile;
- input directory missing;
- output directory cannot be created;
- invalid command-line arguments;
- start corpus ID not found when `--start-corpus-id` is provided;
- `ffmpeg` is not installed or not found.

The programme must exit with code `2`.

### 21.2 Per-item errors

Per-item errors must not stop the full run.

Examples:

- source video file missing;
- unreadable video file;
- unsupported video file;
- video file with no usable audio stream;
- `ffmpeg` timeout;
- `ffmpeg` non-zero return code;
- output file cannot be written.

For each per-item error:

- mark the item as one of:
    - `missing_input`;
    - `failed_metadata`;
    - `failed`;
- capture a short error message;
- log the error;
- continue to the next item.

The programme must exit with code `1` if one or more per-item errors occur.

### 21.3 Invalid metadata records

Rows with missing required fields should be captured in `invalid_records`.

Preferred behaviour:

- continue processing valid records;
- write invalid rows to the manifest;
- exit with code `1` after the run.

Invalid JSON lines are treated as configuration errors and cause exit code `2`.

### 21.4 Keyboard interruption

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

## 22. Exit Codes

| Exit code | Meaning                                                                                                           |
|----------:|-------------------------------------------------------------------------------------------------------------------|
|       `0` | Completed with no failed extractions, no missing inputs, and no invalid eligible metadata rows                    |
|       `1` | Completed, but one or more extractions failed, source videos were missing, or eligible metadata rows were invalid |
|       `2` | Configuration or validation error                                                                                 |
|     `130` | Interrupted by user                                                                                               |

Skipped existing files are not failures.

Ignored records whose video download did not succeed are not failures.

---

## 23. Suggested Constants

The implementation should define constants near the top of the file.

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

DEFAULT_PROFILE = "gemini_flac"
SUPPORTED_PROFILES = ("gemini_flac", "gemini_wav", "whisper_wav")

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 7200
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

INPUT_VIDEO_EXTENSION = ".mp4"

PROFILE_CONFIGS = {
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
```

---

## 24. Docstrings and In-code Documentation

The implementation must include clear docstrings.

### 24.1 Module-level docstring

At the top of `extract_jubilee_debates_audio.py`, include a module-level docstring explaining:

- purpose of the programme;
- expected input index;
- source video directory;
- audio output directory;
- use of `ffmpeg`;
- supported audio profiles;
- default `gemini_flac` profile;
- default test mode;
- safe re-run behaviour;
- start-corpus-ID support;
- full-length extraction only;
- segmentation deferred to a later pipeline stage;
- example commands.

Suggested module docstring:

```python
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
```

### 24.2 Function docstrings

All major functions must include docstrings describing:

- purpose;
- parameters;
- return values;
- whether the function performs I/O;
- error behaviour.

At minimum, docstrings are required for:

- `parse_args`
- `resolve_script_relative_path`
- `setup_logging`
- `validate_args`
- `check_ffmpeg`
- `load_debate_index`
- `plan_audio_extractions`
- `get_audio_profile_config`
- `build_ffmpeg_command`
- `extract_one_audio`
- `write_audio_index`
- `write_manifests`
- `main`

---

## 25. Development Notes

### 25.1 Initial implementation scope

The first implementation should prioritise:

- correct sequential execution;
- reliable input index reading;
- robust eligibility filtering;
- correct full-length audio extraction;
- correct audio profile implementation;
- reliable logging;
- robust manifest output;
- robust audio index output;
- safe resumability;
- optional start-corpus-ID support;
- clear error handling;
- script-relative path resolution.

Parallel extraction can be prepared architecturally but does not need to be implemented in the first version.

### 25.2 Profile selection rationale

The `gemini_flac` profile is the default because the target task is Gemini 1.5 Pro transcription with speaker-turn differentiation. Compared with the Whisper-style profile, it preserves more acoustic information:

- stereo rather than mono;
- 44.1 kHz rather than 16 kHz;
- lossless compression rather than downsampling;
- smaller file size than uncompressed WAV.

The `whisper_wav` profile remains available to support later comparison with Whisper, WhisperX, or related diarisation pipelines.

### 25.3 Segmentation design note

Segmentation should be implemented separately after full-audio extraction is stable.

A later segmentation programme may support:

- fixed-duration segmentation;
- chapter-based segmentation;
- overlap between segments;
- maximum file size targets;
- Gemini upload-size constraints;
- segment manifests;
- parent-child links between full-audio and segment files;
- reconstruction metadata for full-transcript assembly.

---

## 26. Acceptance Criteria

The programme is considered complete when:

1. Running from inside `cl_st1_ph0_carol/` works:

   ```bash
   python extract_jubilee_debates_audio.py
   ```

2. Running from the project root works:

   ```bash
   python cl_st1_ph0_carol/extract_jubilee_debates_audio.py
   ```

3. Default relative paths are resolved relative to the programme directory, not the current working directory.

4. It reads:

   ```text
   cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
   ```

5. It processes only records whose `download_status` indicates successful video availability.

6. It uses source video files from:

   ```text
   cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/
   ```

7. It creates the output directory if needed:

   ```text
   cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/
   ```

8. It supports the `gemini_flac` profile.

9. It supports the `gemini_wav` profile.

10. It supports the `whisper_wav` profile.

11. The default profile is `gemini_flac`.

12. With `gemini_flac`, each audio file is saved as:

    ```text
    cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/<corpus_id>.flac
    ```

13. With `gemini_wav`, each audio file is saved as:

    ```text
    cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_wav/<corpus_id>.wav
    ```

14. With `whisper_wav`, each audio file is saved as:

    ```text
    cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/whisper_wav/<corpus_id>.wav
    ```

15. The `gemini_flac` command is equivalent to:

    ```bash
    ffmpeg -y -i "<input>.mp4" -vn -ac 2 -ar 44100 -c:a flac "<output>.flac"
    ```

16. The `gemini_wav` command is equivalent to:

    ```bash
    ffmpeg -y -i "<input>.mp4" -vn -ac 2 -ar 44100 -c:a pcm_s16le "<output>.wav"
    ```

17. The `whisper_wav` command is equivalent to:

    ```bash
    ffmpeg -y -i "<input>.mp4" -vn -ac 1 -ar 16000 -sample_fmt s16 "<output>.wav"
    ```

18. Existing audio files are skipped unless `--reprocess` is used.

19. Failed audio extractions do not stop the full batch.

20. Missing source video files are marked as `missing_input`.

21. Invalid eligible metadata rows are marked as `failed_metadata`.

22. The programme supports starting from a specific corpus ID with:

    ```bash
    --start-corpus-id CORPUS_ID
    ```

23. If `--start-corpus-id CORPUS_ID` is not found among eligible rows, the programme exits with a configuration error.

24. A log file is written at:

    ```text
    cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log
    ```

25. A latest manifest is written at:

    ```text
    cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest.json
    ```

26. A timestamped per-run manifest is also written.

27. An audio index is written at:

    ```text
    cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
    ```

28. The manifest records:
    - run metadata;
    - configuration;
    - audio profile;
    - `ffmpeg` version;
    - start corpus ID, if any;
    - per-item status;
    - errors;
    - timings;
    - summary counts;
    - generated `ffmpeg` command.

29. The audio index records:
    - source metadata;
    - source video path;
    - extracted audio path;
    - audio profile metadata;
    - extraction status;
    - extraction run ID;
    - extraction timestamp.

30. The programme exits with:
    - `0` if all attempted extractions succeed or are skipped and there are no missing inputs or invalid eligible metadata rows;
    - `1` if any attempted extraction fails, any eligible input video is missing, or any eligible metadata row is invalid;
    - `2` for configuration errors;
    - `130` for keyboard interruption.

31. The programme does **not** segment audio files.

---

## 27. Short README Section

The following section can be added to project documentation.

### Extract Jubilee debate audio

The `extract_jubilee_debates_audio.py` programme extracts full-length audio files from the Jubilee debate videos downloaded by `download_jubilee_debates.py`.

It reads the curated debate index:

```text
corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```

and uses source videos from:

```text
corpus/01_jubilee_debates/videos/
```

Extracted audio files are written to:

```text
corpus/02_jubilee_debates_audio/
```

Default test run:

```bash
python extract_jubilee_debates_audio.py
```

Full run:

```bash
python extract_jubilee_debates_audio.py --no-test-mode
```

The default audio profile is:

```text
gemini_flac
```

which produces stereo 44.1 kHz FLAC files for Gemini 1.5 Pro transcription and speaker-turn differentiation tests.

To extract Whisper-compatible audio instead:

```bash
python extract_jubilee_debates_audio.py \
  --profile whisper_wav \
  --no-test-mode
```

To resume from a specific debate:

```bash
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

The programme is safe to re-run: existing audio files are skipped by default. To force re-extraction:

```bash
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --reprocess
```

This programme extracts full-length audio only. Audio segmentation should be handled by a later pipeline stage.

The programme writes:

```text
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio.log
corpus/02_jubilee_debates_audio/extract_jubilee_debates_audio_manifest.json
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```

A timestamped per-run manifest is also created for each execution.

---

## 28. Design Decision Summary

| Decision                                | Rationale                                                                       |
|-----------------------------------------|---------------------------------------------------------------------------------|
| Extract full-length audio only          | Keeps this stage focused and stable                                             |
| Defer segmentation to a later programme | Segmentation has distinct concerns around Gemini upload limits and time offsets |
| Use `gemini_flac` by default            | Best balance of quality, file size, and Gemini-oriented testing                 |
| Preserve stereo for Gemini profiles     | May preserve useful acoustic/spatial cues for speaker-turn testing              |
| Preserve 44.1 kHz for Gemini profiles   | Avoids unnecessary downsampling before Gemini evaluation                        |
| Keep `whisper_wav` profile              | Enables comparison with Whisper/WhisperX pipelines                              |
| Use `corpus_id` for filenames           | Stable, clean, research-oriented naming                                         |
| Use script-relative path resolution     | Prevents accidental nested paths when running from different directories        |
| Write an audio index                    | Makes downstream segmentation and Gemini-testing stages easier                  |
| Write logs and manifests                | Supports reproducibility and auditability                                       |