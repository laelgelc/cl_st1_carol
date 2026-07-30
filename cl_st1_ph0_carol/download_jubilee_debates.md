# `download_jubilee_debates.py` — Programme Specification for Development

## 1. Programme Summary

`download_jubilee_debates.py` is a batch-processing programme that downloads selected Jubilee debate videos and associated metadata for **Corpus Linguistics — Study 1 — Carol, Phase 0**.

The programme reads an NDJSON input file containing the debate sample selected by Carol:

```text
cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson
```

Each NDJSON record represents one selected Jubilee debate and includes fields such as:

- `corpus_id`;
- `debate_format`;
- `title`;
- `youtube_url`;
- `youtube_id`;
- Carol’s reported view count at selection time.

The programme uses `yt-dlp` to download:

1. the video file;
2. the full raw metadata file produced by `yt-dlp`;
3. optionally, description files;
4. optionally, subtitles and automatic captions;
5. optionally, comments, if enabled.

In addition, the programme creates a curated corpus index file that extracts and normalises selected metadata useful for the study.

---

## 2. Default Paths

### Input file

```text
cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson
```

### Output directory

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/
```

### Default log file

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates.log
```

### Latest run manifest

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates_manifest.json
```

### Timestamped run manifest pattern

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates_manifest_<run_id>.json
```

### Curated corpus index

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```

---

## 3. Output Directory Structure

The programme should organise outputs as follows:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/
├── videos/
│   ├── jubilee_surrounded_001.mp4
│   ├── jubilee_surrounded_002.mp4
│   └── ...
├── metadata_raw/
│   ├── jubilee_surrounded_001.info.json
│   ├── jubilee_surrounded_002.info.json
│   └── ...
├── descriptions/
│   ├── jubilee_surrounded_001.description
│   ├── jubilee_surrounded_002.description
│   └── ...
├── subtitles/
│   ├── jubilee_surrounded_001.en.vtt
│   ├── jubilee_surrounded_001.en-orig.vtt
│   └── ...
├── comments/
│   ├── jubilee_surrounded_001.comments.json
│   └── ...
├── jubilee_debates_index.ndjson
├── download_jubilee_debates.log
├── download_jubilee_debates_manifest.json
└── download_jubilee_debates_manifest_<run_id>.json
```

For the first implementation, `videos/` and `metadata_raw/` should be mandatory. The other subdirectories may be created when their corresponding options are enabled.

---

## 4. Input Specification

The input file is NDJSON: one JSON object per line.

Default path:

```text
cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson
```

### 4.1 Required input fields

Each valid record must contain:

| Field           |   Type | Description                                               |
|-----------------|-------:|-----------------------------------------------------------|
| `corpus_id`     | string | Internal corpus identifier, e.g. `jubilee_surrounded_001` |
| `youtube_id`    | string | YouTube video ID, e.g. `WV29R1M25n8`                      |
| `youtube_url`   | string | YouTube watch URL                                         |
| `title`         | string | Title as supplied in the sample selection                 |
| `debate_format` | string | Debate format, e.g. `Surrounded`                          |

### 4.2 Recommended input fields

The programme should preserve these fields in the curated index if present:

| Field                           | Description                                          |
|---------------------------------|------------------------------------------------------|
| `source_platform`               | Usually `YouTube`                                    |
| `channel`                       | Expected to be `Jubilee`                             |
| `sample_group`                  | e.g. `carol_initial_sample`                          |
| `sample_order`                  | Position in Carol’s list                             |
| `views_reported_by_selector`    | View count as reported by Carol                      |
| `views_reported_numeric_approx` | Numeric approximation of Carol’s reported view count |
| `selected_by`                   | e.g. `Carol`                                         |
| `selection_source`              | e.g. `email`                                         |
| `status`                        | e.g. `selected`                                      |
| `notes`                         | Optional notes                                       |

### 4.3 Example input record

```json
{"corpus_id":"jubilee_surrounded_001","source_platform":"YouTube","channel":"Jubilee","debate_format":"Surrounded","sample_group":"carol_initial_sample","sample_order":1,"title":"1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)","youtube_url":"https://www.youtube.com/watch?v=WV29R1M25n8","youtube_id":"WV29R1M25n8","views_reported_by_selector":"~43 milhões","views_reported_numeric_approx":43000000,"selected_by":"Carol","selection_source":"email","status":"selected","notes":null}
```

---

## 5. Download Behaviour

### 5.1 Video download command

For each valid input record, the programme should download the video using a command equivalent to:

```bash
yt-dlp \
  -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" \
  "https://www.youtube.com/watch?v=WV29R1M25n8" \
  -o "cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4"
```

The output filename should be based on `corpus_id`, not on YouTube title, to ensure stable and filesystem-safe filenames.

Example:

```text
videos/jubilee_surrounded_001.mp4
```

### 5.2 Raw metadata download

The programme must save a raw `yt-dlp` metadata JSON file for each video.

The preferred approach is to invoke `yt-dlp` with `--write-info-json`.

Example command:

```bash
yt-dlp \
  --write-info-json \
  -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" \
  "https://www.youtube.com/watch?v=WV29R1M25n8" \
  -o "cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/jubilee_surrounded_001.%(ext)s"
```

However, because `yt-dlp` normally writes sidecar files next to the media output, the implementation should either:

1. configure output templates carefully; or
2. move/rename the produced `.info.json` file after download.

The final raw metadata path should be:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/metadata_raw/jubilee_surrounded_001.info.json
```

### 5.3 Metadata-only mode

The programme should support a metadata-only mode:

```bash
python download_jubilee_debates.py --metadata-only
```

In metadata-only mode:

- do not download video media;
- download or refresh `yt-dlp` metadata files;
- update the curated index;
- write manifests and logs.

This is useful before large downloads and for checking `yt-dlp` metadata availability.

The underlying `yt-dlp` command should be equivalent to:

```bash
yt-dlp \
  --skip-download \
  --write-info-json \
  "https://www.youtube.com/watch?v=WV29R1M25n8" \
  -o "cl_st1_ph0_carol/corpus/01_jubilee_debates/metadata_raw/jubilee_surrounded_001.%(ext)s"
```

---

## 6. Metadata Selection for Curated Index

The programme must write a curated index file:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```

Each line should contain one JSON object combining:

1. input metadata from Carol’s sample;
2. selected `yt-dlp` metadata;
3. local file paths;
4. extraction metadata.

### 6.1 Recommended curated index fields

Each curated index record should contain:

| Field                          | Source           | Description                                      |
|--------------------------------|------------------|--------------------------------------------------|
| `corpus_id`                    | input            | Internal stable corpus ID                        |
| `debate_format`                | input            | e.g. `Surrounded`                                |
| `sample_group`                 | input            | e.g. `carol_initial_sample`                      |
| `sample_order`                 | input            | Carol’s sample order                             |
| `title_selected`               | input            | Title from Carol’s message                       |
| `title_extracted`              | `yt-dlp`         | Title extracted at download time                 |
| `youtube_id`                   | input / `yt-dlp` | YouTube video ID                                 |
| `youtube_url`                  | input            | Original URL from input file                     |
| `webpage_url`                  | `yt-dlp`         | Canonical URL extracted by `yt-dlp`              |
| `source_platform`              | input            | Usually `YouTube`                                |
| `channel_selected`             | input            | Channel from input file                          |
| `channel_extracted`            | `yt-dlp`         | Channel from `yt-dlp`                            |
| `channel_id`                   | `yt-dlp`         | YouTube channel ID                               |
| `channel_url`                  | `yt-dlp`         | YouTube channel URL                              |
| `uploader`                     | `yt-dlp`         | Uploader name                                    |
| `uploader_id`                  | `yt-dlp`         | Uploader ID                                      |
| `upload_date`                  | `yt-dlp`         | Upload date, usually `YYYYMMDD`                  |
| `duration_seconds`             | `yt-dlp`         | Duration in seconds                              |
| `duration_string`              | `yt-dlp`         | Human-readable duration                          |
| `view_count_at_selection`      | input            | Carol’s approximate reported view count          |
| `view_count_at_download`       | `yt-dlp`         | Extracted view count at download time            |
| `like_count_at_download`       | `yt-dlp`         | Extracted like count, if available               |
| `comment_count_at_download`    | `yt-dlp`         | Extracted comment count, if available            |
| `categories`                   | `yt-dlp`         | YouTube categories                               |
| `tags`                         | `yt-dlp`         | YouTube tags                                     |
| `description`                  | `yt-dlp`         | Full video description or optional path only     |
| `thumbnail_url`                | `yt-dlp`         | Main thumbnail URL                               |
| `chapters`                     | `yt-dlp`         | Chapter metadata, if available                   |
| `subtitles_available`          | derived          | Whether manual subtitles are available           |
| `automatic_captions_available` | derived          | Whether automatic captions are available         |
| `availability`                 | `yt-dlp`         | Public/private/unlisted/member-only if available |
| `age_limit`                    | `yt-dlp`         | Age restriction data                             |
| `live_status`                  | `yt-dlp`         | Live status                                      |
| `video_file`                   | local            | Local `.mp4` path                                |
| `raw_metadata_file`            | local            | Local `.info.json` path                          |
| `description_file`             | local            | Optional local description path                  |
| `subtitles_files`              | local            | List of local subtitle files                     |
| `comments_file`                | local            | Optional local comments path                     |
| `download_status`              | programme        | `success`, `failed`, `skipped_existing`, etc.    |
| `metadata_status`              | programme        | `success`, `failed`, `skipped_existing`, etc.    |
| `download_run_id`              | programme        | Run ID                                           |
| `downloaded_at_utc`            | programme        | Timestamp                                        |
| `yt_dlp_version`               | programme        | `yt-dlp --version`                               |
| `selected_by`                  | input            | e.g. `Carol`                                     |
| `selection_source`             | input            | e.g. `email`                                     |
| `notes`                        | input            | Optional notes                                   |

### 6.2 Example curated index record

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "debate_format": "Surrounded",
  "sample_group": "carol_initial_sample",
  "sample_order": 1,
  "title_selected": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)",
  "title_extracted": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)",
  "youtube_id": "WV29R1M25n8",
  "youtube_url": "https://www.youtube.com/watch?v=WV29R1M25n8",
  "webpage_url": "https://www.youtube.com/watch?v=WV29R1M25n8",
  "source_platform": "YouTube",
  "channel_selected": "Jubilee",
  "channel_extracted": "Jubilee",
  "channel_id": null,
  "channel_url": null,
  "uploader": "Jubilee",
  "uploader_id": null,
  "upload_date": null,
  "duration_seconds": null,
  "duration_string": null,
  "view_count_at_selection": 43000000,
  "view_count_at_download": null,
  "like_count_at_download": null,
  "comment_count_at_download": null,
  "categories": [],
  "tags": [],
  "description": null,
  "thumbnail_url": null,
  "chapters": [],
  "subtitles_available": false,
  "automatic_captions_available": false,
  "availability": null,
  "age_limit": null,
  "live_status": null,
  "video_file": "cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4",
  "raw_metadata_file": "cl_st1_ph0_carol/corpus/01_jubilee_debates/metadata_raw/jubilee_surrounded_001.info.json",
  "description_file": null,
  "subtitles_files": [],
  "comments_file": null,
  "download_status": "success",
  "metadata_status": "success",
  "download_run_id": "20260730T100000Z",
  "downloaded_at_utc": "2026-07-30T10:00:00Z",
  "yt_dlp_version": "unknown",
  "selected_by": "Carol",
  "selection_source": "email",
  "notes": null
}
```

---

## 7. Command-line Interface

### 7.1 Default usage

```bash
python download_jubilee_debates.py
```

Default behaviour:

- input metadata path:

```text
cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson
```

- output directory:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/
```

- test mode enabled;
- test limit: `5`;
- sequential processing;
- skip existing videos and metadata;
- no cookies file;
- no start corpus ID filter.

Because the current sample contains exactly five debates, the default test run would process the entire current sample.

---

## 8. Optional Arguments

### 8.1 Input metadata file

```bash
--metadata PATH
```

Default:

```text
cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson
```

---

### 8.2 Output directory

```bash
--output-dir PATH
```

Default:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/
```

---

### 8.3 Test mode

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

### 8.4 Test limit

```bash
--test-limit N
```

Default:

```text
5
```

Must be a positive integer.

---

### 8.5 Reprocess existing outputs

```bash
--reprocess
```

Default:

```text
False
```

When omitted, existing video and metadata files are skipped when possible.

When provided, the programme should re-run `yt-dlp` and overwrite or refresh outputs.

---

### 8.6 Metadata-only mode

```bash
--metadata-only
```

Default:

```text
False
```

When enabled:

- download or refresh metadata;
- do not download video media;
- update the curated index and manifest.

---

### 8.7 Skip metadata refresh

```bash
--skip-metadata
```

Default:

```text
False
```

When enabled:

- do not request new `yt-dlp` metadata;
- rely on existing raw metadata files if available;
- still update the manifest and curated index where possible.

This option should not be used together with `--metadata-only`.

---

### 8.8 Cookies file

```bash
--cookies PATH
```

Default:

```text
None
```

Optional Netscape-format cookies file to pass to `yt-dlp`.

Example:

```bash
python download_jubilee_debates.py \
  --cookies env/youtube_cookies.txt
```

Security requirements:

- do not log the file contents;
- do not commit the file to Git;
- treat it like a password.

---

### 8.9 Start corpus ID

```bash
--start-corpus-id CORPUS_ID
```

Default:

```text
None
```

Example:

```bash
python download_jubilee_debates.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

Behaviour:

- preserve input order;
- ignore records before the specified `corpus_id`;
- include the specified record;
- include all following records;
- fail fast if the `corpus_id` is not found.

This is better than `--start-video-id` for this project because `corpus_id` is the stable internal corpus identifier.

---

### 8.10 Log file

```bash
--log-file PATH
```

Default:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates.log
```

---

### 8.11 Manifest file

```bash
--manifest-file PATH
```

Default:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates_manifest.json
```

---

### 8.12 Index file

```bash
--index-file PATH
```

Default:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```

---

### 8.13 Workers

```bash
--workers N
```

Default:

```text
1
```

For the first implementation, only `--workers 1` should be supported.

---

### 8.14 Timeout

```bash
--timeout SECONDS
```

Default suggestion:

```text
7200
```

Jubilee debates may be long, so a two-hour per-video timeout is safer than the one-hour default used in the reference specification.

---

### 8.15 Maximum retries

```bash
--max-retries N
```

Default:

```text
1
```

Must be zero or a positive integer.

---

### 8.16 Retry delay

```bash
--retry-delay SECONDS
```

Default:

```text
5
```

---

### 8.17 Subtitles

```bash
--write-subs
--write-auto-subs
--sub-langs LANGS
```

Recommended defaults:

```text
--write-auto-subs enabled
--write-subs enabled
--sub-langs en.*
```

Since the later phase involves transcription and speaker diarisation, preserving YouTube subtitles/captions may be useful as a reference, even if they are not sufficient for speaker-turn differentiation.

---

### 8.18 Description

```bash
--write-description
```

Default recommendation:

```text
True
```

The video description is useful contextual metadata and should be saved by default.

---

### 8.19 Comments

```bash
--write-comments
```

Default recommendation:

```text
False
```

Comments can be large and are not necessary for the initial speaker diarisation test. The programme may support them, but should not enable them by default.

---

## 9. Example Commands

### Default run

```bash
python download_jubilee_debates.py
```

### Full run

```bash
python download_jubilee_debates.py --no-test-mode
```

### Metadata-only run

```bash
python download_jubilee_debates.py --metadata-only
```

### Full run with cookies

```bash
python download_jubilee_debates.py \
  --no-test-mode \
  --cookies env/youtube_cookies.txt
```

### Resume from a specific corpus item

```bash
python download_jubilee_debates.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

### Resume with cookies

```bash
python download_jubilee_debates.py \
  --no-test-mode \
  --cookies env/youtube_cookies.txt \
  --start-corpus-id jubilee_surrounded_003
```

### Reprocess everything

```bash
python download_jubilee_debates.py \
  --no-test-mode \
  --reprocess
```

### Metadata-only refresh with cookies

```bash
python download_jubilee_debates.py \
  --metadata-only \
  --cookies env/youtube_cookies.txt \
  --reprocess
```

---

## 10. Validation Rules

The programme must fail fast with a configuration error if:

- the input metadata file does not exist;
- the input metadata file is unreadable;
- the input file contains invalid JSON lines;
- required fields are missing from all records;
- `--test-limit` is less than or equal to zero;
- `--workers` is less than or equal to zero;
- `--workers` is not `1` in the first implementation;
- `--timeout` is less than or equal to zero;
- `--max-retries` is negative;
- `--retry-delay` is negative;
- `--cookies` is provided but the file does not exist;
- `--cookies` is provided but the path is not a file;
- `--start-corpus-id` is provided but not found;
- `--metadata-only` and `--skip-metadata` are both provided;
- `yt-dlp` is not available on the system path.

The programme should check `yt-dlp` availability with:

```bash
yt-dlp --version
```

---

## 11. Core Processing Flow

The programme should follow this workflow:

1. **Startup**
   - Parse command-line arguments.
   - Generate UTC `run_id`.
   - Ensure output directories exist.
   - Configure logging.
   - Validate arguments.
   - Check `yt-dlp` version.

2. **Load input**
   - Read the NDJSON file line by line.
   - Parse each JSON object.
   - Validate required fields.
   - Preserve input order.
   - Record invalid rows.

3. **Deduplicate**
   - Use `corpus_id` as the primary unique key.
   - Optionally check duplicate `youtube_id`.
   - If duplicate `corpus_id` occurs:
     - keep first occurrence;
     - record later duplicates in the manifest.

4. **Planning**
   - Apply `--start-corpus-id`, if provided.
   - Apply existing-file skip logic.
   - Apply test limit, if test mode is enabled.
   - Determine per-item output paths:
     - video path;
     - raw metadata path;
     - description path;
     - subtitle directory;
     - comments path.

5. **Execution**
   - For each planned item:
     - run `yt-dlp`;
     - capture stdout, stderr, return code;
     - retry failures according to `--max-retries`;
     - move/normalise sidecar files if needed;
     - mark the item status.

6. **Index generation**
   - Read raw `.info.json` files where available.
   - Extract selected metadata fields.
   - Combine with input metadata.
   - Write `jubilee_debates_index.ndjson`.

7. **Manifest writing**
   - Write latest manifest.
   - Write timestamped manifest.

8. **Exit**
   - Exit `0` if all attempted items succeeded or were skipped.
   - Exit `1` if one or more attempted downloads failed or invalid metadata records exist.
   - Exit `2` for configuration errors.
   - Exit `130` for keyboard interruption.

---

## 12. Suggested Status Values

| Status             | Meaning                                               |
|--------------------|-------------------------------------------------------|
| `success`          | Download or metadata extraction succeeded             |
| `failed`           | Attempted but failed                                  |
| `skipped_existing` | Output already existed and `--reprocess` was not used |
| `planned`          | Planned but not yet attempted                         |
| `not_requested`    | Output type was not requested                         |
| `failed_metadata`  | Input record was invalid                              |
| `interrupted`      | Processing stopped due to keyboard interruption       |

---

## 13. Manifest Design

The manifest should use this general structure:

```json
{
  "run_metadata": {
    "run_id": "20260730T100000Z",
    "tool_name": "download_jubilee_debates.py",
    "tool_version": "v1",
    "start_time": "2026-07-30T10:00:00Z",
    "end_time": "2026-07-30T10:45:00Z",
    "test_mode": true,
    "test_limit": 5,
    "metadata_only": false,
    "reprocess": false,
    "workers": 1,
    "metadata_path": "cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson",
    "output_dir": "cl_st1_ph0_carol/corpus/01_jubilee_debates",
    "index_file": "cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson",
    "log_file": "cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates.log",
    "manifest_file": "cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates_manifest.json",
    "config": {
      "yt_dlp_format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
      "timeout_seconds": 7200,
      "max_retries": 1,
      "retry_delay_seconds": 5,
      "cookies_provided": false,
      "start_corpus_id": null,
      "write_description": true,
      "write_subs": true,
      "write_auto_subs": true,
      "write_comments": false,
      "sub_langs": "en.*"
    },
    "yt_dlp": {
      "available": true,
      "version": "2026.07.21"
    },
    "summary": {
      "input_records": 5,
      "valid_records": 5,
      "invalid_records": 0,
      "unique_corpus_items": 5,
      "planned_items": 5,
      "attempted_items": 5,
      "succeeded": 5,
      "failed": 0,
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
      "debate_format": "Surrounded",
      "video_file": "cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4",
      "raw_metadata_file": "cl_st1_ph0_carol/corpus/01_jubilee_debates/metadata_raw/jubilee_surrounded_001.info.json",
      "description_file": "cl_st1_ph0_carol/corpus/01_jubilee_debates/descriptions/jubilee_surrounded_001.description",
      "status": "success",
      "video_status": "success",
      "metadata_status": "success",
      "error": null,
      "return_code": 0,
      "retries": 0,
      "duration_seconds": 850.25,
      "start_time": "2026-07-30T10:01:00Z",
      "end_time": "2026-07-30T10:15:10Z"
    }
  ],
  "invalid_records": [],
  "duplicates": []
}
```

---

## 14. Logging Specification

The programme must write an append-only UTF-8 log file:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates.log
```

Each line should follow:

```text
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```

Required log events:

- startup;
- run ID;
- parsed configuration;
- metadata path;
- output directory;
- index path;
- test mode status;
- metadata-only status;
- cookies provided or not;
- `yt-dlp` version;
- number of records loaded;
- number of valid and invalid records;
- number of planned items;
- each skipped item;
- each download attempt;
- each retry;
- each successful item;
- each failed item;
- curated index writing;
- manifest writing;
- final summary;
- validation errors;
- keyboard interruption.

The programme must not log cookies file contents.

---

## 15. Suggested Constants

```python
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
    "cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates_manifest.json"
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
```

---

## 16. Suggested Function Architecture

```python
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""


def setup_logging(log_file: Path) -> logging.Logger:
    """Configure append-only logging."""


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and paths."""


def check_yt_dlp() -> dict:
    """Check whether yt-dlp is available and return version metadata."""


def load_samples(metadata_path: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """Load, validate, and deduplicate debate sample records."""


def plan_items(
    records: list[dict],
    output_dir: Path,
    args: argparse.Namespace,
) -> tuple[list[dict], list[dict]]:
    """Create planned and skipped processing items."""


def build_yt_dlp_command(
    item: dict,
    args: argparse.Namespace,
    output_paths: dict,
) -> list[str]:
    """Build the yt-dlp command for one corpus item."""


def run_yt_dlp_command(
    command: list[str],
    timeout: int,
    max_retries: int,
    retry_delay: int,
) -> dict:
    """Run yt-dlp with retries and return structured execution metadata."""


def normalise_sidecar_files(item: dict, output_paths: dict) -> dict:
    """Move or rename yt-dlp sidecar files into the expected project layout."""


def extract_curated_metadata(
    input_record: dict,
    raw_metadata_path: Path | None,
    local_paths: dict,
    run_metadata: dict,
) -> dict:
    """Create one curated corpus index record."""


def write_index(index_records: list[dict], index_file: Path) -> None:
    """Write the curated NDJSON index."""


def write_manifests(
    manifest: dict,
    manifest_file: Path,
    run_id: str,
) -> tuple[Path, Path]:
    """Write latest and timestamped manifest files."""


def main() -> int:
    """Run the complete Jubilee debate download workflow."""
```

---

## 17. Exit Codes

| Exit code | Meaning                                                               |
|----------:|-----------------------------------------------------------------------|
|       `0` | Completed with no failures                                            |
|       `1` | Completed, but one or more items failed or invalid metadata was found |
|       `2` | Configuration or validation error                                     |
|     `130` | Interrupted by user                                                   |

---

## 18. Acceptance Criteria

The programme is considered complete when:

1. Running the default command works:

   ```bash
   python download_jubilee_debates.py
   ```

2. It reads:

   ```text
   cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson
   ```

3. It creates:

   ```text
   cl_st1_ph0_carol/corpus/01_jubilee_debates/
   ```

4. It downloads videos into:

   ```text
   cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/
   ```

5. Video filenames are based on `corpus_id`.

6. It saves raw `yt-dlp` metadata into:

   ```text
   cl_st1_ph0_carol/corpus/01_jubilee_debates/metadata_raw/
   ```

7. It writes a curated index:

   ```text
   cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
   ```

8. The curated index preserves Carol’s sample metadata and adds selected `yt-dlp` metadata.

9. Existing outputs are skipped by default.

10. `--reprocess` forces reprocessing.

11. `--metadata-only` fetches metadata without downloading video files.

12. `--cookies PATH` is supported.

13. `--start-corpus-id CORPUS_ID` is supported.

14. Failed downloads do not stop the entire batch.

15. Logs are written to:

   ```text
   cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates.log
   ```

16. Latest and timestamped manifests are written.

17. The programme exits with the specified exit codes.

---

## 19. Design Decision Summary

The main project-specific design choices are:

| Decision                                                | Rationale                                                           |
|---------------------------------------------------------|---------------------------------------------------------------------|
| Use `corpus_id` for filenames                           | Stable, clean, research-oriented identifier                         |
| Keep raw `.info.json` files                             | Preserves full `yt-dlp` metadata for reproducibility                |
| Also generate curated NDJSON index                      | Easier for analysis and downstream scripts                          |
| Separate `videos/`, `metadata_raw/`, `subtitles/`, etc. | Keeps corpus directory organised                                    |
| Default `test-limit = 5`                                | Matches the current initial sample size                             |
| Support metadata-only mode                              | Useful before large downloads and for metadata inspection           |
| Save Carol’s reported view counts separately            | Distinguishes selection-time popularity from download-time metadata |
| Prefer `--start-corpus-id` over `--start-video-id`      | Corpus IDs are the internal stable identifiers                      |