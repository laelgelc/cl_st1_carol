# `download_jubilee_debates.py` — Programme Specification for Development

## 1. Programme Summary

`download_jubilee_debates.py` is a batch-processing programme that downloads selected Jubilee debate videos and associated metadata for **Corpus Linguistics — Study 1 — Carol, Phase 0**.

The programme is located at:
```text
cl_st1_ph0_carol/download_jubilee_debates.py
```
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
3. description files, by default;
4. subtitles and automatic captions, by default;
5. comments, optionally, if enabled.

In addition, the programme creates a curated corpus index file that extracts and normalises selected metadata useful for the study.

The curated index must be **portable across machines**. File paths written into the curated index should be project-relative whenever the files are inside the project phase directory. This avoids machine-specific paths such as:
```text
/home/<user>/PycharmProjects/cl_st1_carol/cl_st1_ph0_carol/...
```
and instead writes paths such as:
```text
corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4
```
This portability is important because downstream audio extraction, transcription, alignment, and diarisation stages may run on a different machine, such as an EC2 GPU server.

---

## 2. Path Resolution Policy

The programme must resolve its **default paths relative to the directory where `download_jubilee_debates.py` is located**, not relative to the current working directory.

This means that if the script is located at:
```text
cl_st1_ph0_carol/download_jubilee_debates.py
```
then the default metadata path:
```text
corpus/00_sources/jubilee_debates_samples.ndjson
```
must resolve to:
```text
cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson
```
and the default output directory:
```text
corpus/01_jubilee_debates/
```
must resolve to:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/
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

### 2.1 Internal path base

The implementation should define a script directory equivalent to:
```python
SCRIPT_DIR = Path(__file__).resolve().parent
```
Relative default paths should then be resolved against `SCRIPT_DIR`.

### 2.2 Absolute paths

If the user supplies an absolute path for an argument such as `--metadata`, `--output-dir`, `--log-file`, `--manifest-file`, `--index-file`, or `--cookies`, the programme must preserve that absolute path.

### 2.3 Relative command-line paths

For consistency with the default behaviour, relative command-line paths should also be resolved relative to the programme directory.

For example, if the user runs:
```bash
python download_jubilee_debates.py --cookies env/youtube_cookies.txt
```
from inside `cl_st1_ph0_carol/`, the cookies path should resolve to:
```text
cl_st1_ph0_carol/env/youtube_cookies.txt
```
### 2.4 Portable paths in curated index files

Although the programme resolves filesystem paths internally as absolute paths, the curated corpus index should not normally store machine-specific absolute paths.

For fields that refer to files inside the project phase directory, the programme must write paths relative to `SCRIPT_DIR`.

For example, if the programme internally resolves:
```text
/home/eyamrog/PycharmProjects/cl_st1_carol/cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4
```
then the curated index should store:
```text
corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4
```
This applies to curated index fields such as:

- `video_file`;
- `raw_metadata_file`;
- `description_file`;
- `subtitles_files`;
- `comments_file`.

Paths outside the project phase directory may be preserved as supplied, because converting genuinely external paths to project-relative paths would be misleading.

The manifest may contain resolved paths for debugging, but curated indices intended for downstream pipeline stages should prefer portable project-relative paths.

---

## 3. Default Paths

The following defaults are relative to the programme directory `cl_st1_ph0_carol/`.

### Input file

Default argument value:
```text
corpus/00_sources/jubilee_debates_samples.ndjson
```
Resolved project path:
```text
cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson
```
### Output directory

Default argument value:
```text
corpus/01_jubilee_debates/
```
Resolved project path:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/
```
### Default log file

Default argument value:
```text
corpus/01_jubilee_debates/download_jubilee_debates.log
```
Resolved project path:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates.log
```
### Latest run manifest

Default argument value:
```text
corpus/01_jubilee_debates/download_jubilee_debates_manifest.json
```
Resolved project path:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates_manifest.json
```
### Timestamped run manifest pattern

Resolved project path pattern:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates_manifest_<run_id>.json
```
### Curated corpus index

Default argument value:
```text
corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```
Resolved project path:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```
---

## 4. Output Directory Structure

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
The programme should create the following subdirectories if they do not already exist:
```text
videos/
metadata_raw/
descriptions/
subtitles/
comments/
```
For the first implementation, `videos/` and `metadata_raw/` are the primary output directories. The other subdirectories are created to support description, subtitle, and optional comment outputs.

---

## 5. Input Specification

The input file is NDJSON: one JSON object per line.

Default resolved path:
```text
cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson
```
### 5.1 Required input fields

Each valid record must contain:

| Field           |   Type | Description                                               |
|-----------------|-------:|-----------------------------------------------------------|
| `corpus_id`     | string | Internal corpus identifier, e.g. `jubilee_surrounded_001` |
| `youtube_id`    | string | YouTube video ID, e.g. `WV29R1M25n8`                      |
| `youtube_url`   | string | YouTube watch URL                                         |
| `title`         | string | Title as supplied in the sample selection                 |
| `debate_format` | string | Debate format, e.g. `Surrounded`                          |

### 5.2 Recommended input fields

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

### 5.3 Example input record
```json
{"corpus_id":"jubilee_surrounded_001","source_platform":"YouTube","channel":"Jubilee","debate_format":"Surrounded","sample_group":"carol_initial_sample","sample_order":1,"title":"1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)","youtube_url":"https://www.youtube.com/watch?v=WV29R1M25n8","youtube_id":"WV29R1M25n8","views_reported_by_selector":"~43 milhões","views_reported_numeric_approx":43000000,"selected_by":"Carol","selection_source":"email","status":"selected","notes":null}
```
### 5.4 Invalid input records

If a row is missing one or more required fields:

- the row must not be downloaded;
- the row should be recorded in `invalid_records` in the manifest;
- the row should be marked with status `failed_metadata` or equivalent;
- processing should continue for other records.

Invalid JSON lines are configuration errors and should cause the programme to exit with code `2`.

---

## 6. Download Behaviour

### 6.1 Video download command

For each valid input record, the programme should download the video using a command equivalent to:
```bash
yt-dlp \
  -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" \
  "https://www.youtube.com/watch?v=WV29R1M25n8" \
  -o "cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/jubilee_surrounded_001.%(ext)s"
```
The output filename should be based on `corpus_id`, not on YouTube title, to ensure stable and filesystem-safe filenames.

Expected final video path:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4
```
In the curated index, this should be written as:
```text
corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4
```
### 6.2 Raw metadata download

The programme must save a raw `yt-dlp` metadata JSON file for each video unless `--skip-metadata` is provided.

The programme should invoke `yt-dlp` with:
```bash
--write-info-json
```
When running a normal video download, the command should be equivalent to:
```bash
yt-dlp \
  --write-info-json \
  -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" \
  "https://www.youtube.com/watch?v=WV29R1M25n8" \
  -o "cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/jubilee_surrounded_001.%(ext)s"
```
Because `yt-dlp` normally writes sidecar files next to the media output, the implementation may:

1. configure output templates carefully; or
2. move/rename the produced `.info.json` file after download.

The final raw metadata path must be:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/metadata_raw/jubilee_surrounded_001.info.json
```
In the curated index, this should be written as:
```text
corpus/01_jubilee_debates/metadata_raw/jubilee_surrounded_001.info.json
```
### 6.3 Metadata-only mode

The programme must support a metadata-only mode:
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
Expected final raw metadata path:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/metadata_raw/jubilee_surrounded_001.info.json
```
### 6.4 Existing outputs

Existing outputs should be skipped by default.

If `--metadata-only` is enabled, an item may be skipped when its raw metadata file already exists and `--reprocess` is not enabled.

If normal video download mode is enabled, an item may be skipped when both the video file and raw metadata file already exist and `--reprocess` is not enabled.

If `--skip-metadata` is enabled, an item may be skipped when the video file exists and `--reprocess` is not enabled.

### 6.5 Reprocessing

If `--reprocess` is provided:
```bash
python download_jubilee_debates.py --reprocess
```
the programme should call `yt-dlp` again and allow outputs to be overwritten or refreshed.

---

## 7. Metadata Selection for Curated Index

The programme must write a curated index file:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```
Each line should contain one JSON object combining:

1. input metadata from Carol’s sample;
2. selected `yt-dlp` metadata;
3. local file paths;
4. download metadata.

### 7.1 Recommended curated index fields

Each curated index record should contain:

| Field                             | Source           | Description                                                  |
|-----------------------------------|------------------|--------------------------------------------------------------|
| `corpus_id`                       | input            | Internal stable corpus ID                                    |
| `debate_format`                   | input            | e.g. `Surrounded`                                            |
| `sample_group`                    | input            | e.g. `carol_initial_sample`                                  |
| `sample_order`                    | input            | Carol’s sample order                                         |
| `title_selected`                  | input            | Title from Carol’s message                                   |
| `title_extracted`                 | `yt-dlp`         | Title extracted at download time                             |
| `youtube_id`                      | input / `yt-dlp` | YouTube video ID                                             |
| `youtube_url`                     | input            | Original URL from input file                                 |
| `webpage_url`                     | `yt-dlp`         | Canonical URL extracted by `yt-dlp`                          |
| `source_platform`                 | input            | Usually `YouTube`                                            |
| `channel_selected`                | input            | Channel from input file                                      |
| `channel_extracted`               | `yt-dlp`         | Channel from `yt-dlp`                                        |
| `channel_id`                      | `yt-dlp`         | YouTube channel ID                                           |
| `channel_url`                     | `yt-dlp`         | YouTube channel URL                                          |
| `uploader`                        | `yt-dlp`         | Uploader name                                                |
| `uploader_id`                     | `yt-dlp`         | Uploader ID                                                  |
| `upload_date`                     | `yt-dlp`         | Upload date, usually `YYYYMMDD`                              |
| `duration_seconds`                | `yt-dlp`         | Duration in seconds                                          |
| `duration_string`                 | `yt-dlp`         | Human-readable duration                                      |
| `view_count_at_selection`         | input            | Carol’s approximate reported view count                      |
| `view_count_reported_by_selector` | input            | Original textual view count reported by Carol                |
| `view_count_at_download`          | `yt-dlp`         | Extracted view count at download time                        |
| `like_count_at_download`          | `yt-dlp`         | Extracted like count, if available                           |
| `comment_count_at_download`       | `yt-dlp`         | Extracted comment count, if available                        |
| `categories`                      | `yt-dlp`         | YouTube categories                                           |
| `tags`                            | `yt-dlp`         | YouTube tags                                                 |
| `description`                     | `yt-dlp`         | Full video description                                       |
| `thumbnail_url`                   | `yt-dlp`         | Main thumbnail URL                                           |
| `chapters`                        | `yt-dlp`         | Chapter metadata, if available                               |
| `subtitles_available`             | derived          | Whether manual subtitles are available                       |
| `automatic_captions_available`    | derived          | Whether automatic captions are available                     |
| `availability`                    | `yt-dlp`         | Public/private/unlisted/member-only if available             |
| `age_limit`                       | `yt-dlp`         | Age restriction data                                         |
| `live_status`                     | `yt-dlp`         | Live status                                                  |
| `video_file`                      | local            | Project-relative `.mp4` path, or `null` if unavailable       |
| `raw_metadata_file`               | local            | Project-relative `.info.json` path, or `null` if unavailable |
| `description_file`                | local            | Project-relative description path, or `null` if unavailable  |
| `subtitles_files`                 | local            | List of project-relative subtitle file paths                 |
| `comments_file`                   | local            | Project-relative comments path, or `null` if unavailable     |
| `download_status`                 | programme        | `success`, `failed`, `skipped_existing`, etc.                |
| `metadata_status`                 | programme        | `success`, `failed`, `skipped_existing`, etc.                |
| `download_run_id`                 | programme        | Run ID                                                       |
| `downloaded_at_utc`               | programme        | Timestamp                                                    |
| `yt_dlp_version`                  | programme        | `yt-dlp --version`                                           |
| `selected_by`                     | input            | e.g. `Carol`                                                 |
| `selection_source`                | input            | e.g. `email`                                                 |
| `notes`                           | input            | Optional notes                                               |

### 7.2 Example curated index record
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
  "source_platform": "YouTube",
  "channel_selected": "Jubilee",
  "channel_extracted": "Jubilee",
  "channel_id": "UCJjSDX-jUChzOEyok9XYRJQ",
  "channel_url": "https://www.youtube.com/channel/UCJjSDX-jUChzOEyok9XYRJQ",
  "uploader": "Jubilee",
  "uploader_id": "@jubilee",
  "upload_date": "20240908",
  "duration_seconds": 5427,
  "duration_string": "1:30:27",
  "view_count_at_selection": 43000000,
  "view_count_reported_by_selector": "~43 milhões",
  "view_count_at_download": 44041973,
  "like_count_at_download": 867639,
  "comment_count_at_download": 183000,
  "categories": ["Entertainment"],
  "tags": [],
  "description": "Full video description from yt-dlp...",
  "thumbnail_url": "https://i.ytimg.com/vi/WV29R1M25n8/maxresdefault.jpg",
  "chapters": [
    {
      "start_time": 0,
      "title": "Intro",
      "end_time": 45
    }
  ],
  "subtitles_available": false,
  "automatic_captions_available": true,
  "availability": "public",
  "age_limit": 0,
  "live_status": "not_live",
  "video_file": "corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4",
  "raw_metadata_file": "corpus/01_jubilee_debates/metadata_raw/jubilee_surrounded_001.info.json",
  "description_file": "corpus/01_jubilee_debates/descriptions/jubilee_surrounded_001.description",
  "subtitles_files": [
    "corpus/01_jubilee_debates/subtitles/jubilee_surrounded_001.en-orig.vtt",
    "corpus/01_jubilee_debates/subtitles/jubilee_surrounded_001.en.vtt"
  ],
  "comments_file": null,
  "download_status": "success",
  "metadata_status": "success",
  "download_run_id": "20260817T170458Z",
  "downloaded_at_utc": "2026-08-17T17:14:24Z",
  "yt_dlp_version": "2026.07.04",
  "selected_by": "Carol",
  "selection_source": "email",
  "notes": null
}
```
### 7.3 Failed download records in the curated index

The curated index may include records for failed downloads. This is intentional.

If `yt-dlp` successfully retrieves some metadata or sidecar files but fails to download the video media, the curated index should still preserve available metadata and set status fields accordingly.

For a failed video download, the index may contain:
```json
{
  "corpus_id": "jubilee_surrounded_002",
  "video_file": null,
  "raw_metadata_file": "corpus/01_jubilee_debates/metadata_raw/jubilee_surrounded_002.info.json",
  "description_file": "corpus/01_jubilee_debates/descriptions/jubilee_surrounded_002.description",
  "subtitles_files": [
    "corpus/01_jubilee_debates/subtitles/jubilee_surrounded_002.en-orig.vtt",
    "corpus/01_jubilee_debates/subtitles/jubilee_surrounded_002.en.vtt"
  ],
  "download_status": "failed",
  "metadata_status": "failed"
}
```
This indicates that the record remains part of the planned corpus, but the video media was not available from this run.

Downstream stages should process only records whose upstream status indicates the required input is available.

---

## 8. Command-line Interface

### 8.1 Default usage

The script may be run from inside `cl_st1_ph0_carol/`:
```bash
python download_jubilee_debates.py
```
or from the project root:
```bash
python cl_st1_ph0_carol/download_jubilee_debates.py
```
Both commands should resolve default paths correctly.

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
- no start corpus ID filter;
- write descriptions;
- write manual subtitles;
- write automatic captions;
- do not write comments.

Because the current sample contains exactly five debates, the default test run processes the entire current sample unless outputs are already present and skipped.

---

## 9. Optional Arguments

### 9.1 Input metadata file
```bash
--metadata PATH
```
Default argument value:
```text
corpus/00_sources/jubilee_debates_samples.ndjson
```
Default resolved path:
```text
cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson
```
Description:

Path to the NDJSON input metadata file.

Relative paths are resolved relative to the programme directory.

---

### 9.2 Output directory
```bash
--output-dir PATH
```
Default argument value:
```text
corpus/01_jubilee_debates/
```
Default resolved path:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/
```
Description:

Directory where downloaded files, sidecar files, logs, manifests, and the curated index are written.

Relative paths are resolved relative to the programme directory.

---

### 9.3 Test mode
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

### 9.4 Test limit
```bash
--test-limit N
```
Default:
```text
5
```
Must be a positive integer.

---

### 9.5 Reprocess existing outputs
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

### 9.6 Metadata-only mode
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

### 9.7 Skip metadata refresh
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

This option must not be used together with `--metadata-only`.

---

### 9.8 Cookies file
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
Relative cookies paths are resolved relative to the programme directory.

Security requirements:

- do not log the file contents;
- do not commit the file to Git;
- treat it like a password.

---

### 9.9 Start corpus ID
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

### 9.10 Log file
```bash
--log-file PATH
```
Default argument value:
```text
corpus/01_jubilee_debates/download_jubilee_debates.log
```
Default resolved path:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates.log
```
Relative paths are resolved relative to the programme directory.

---

### 9.11 Manifest file
```bash
--manifest-file PATH
```
Default argument value:
```text
corpus/01_jubilee_debates/download_jubilee_debates_manifest.json
```
Default resolved path:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates_manifest.json
```
Relative paths are resolved relative to the programme directory.

---

### 9.12 Index file
```bash
--index-file PATH
```
Default argument value:
```text
corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```
Default resolved path:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```
Relative paths are resolved relative to the programme directory.

---

### 9.13 Workers
```bash
--workers N
```
Default:
```text
1
```
For the first implementation, only `--workers 1` is supported.

---

### 9.14 Timeout
```bash
--timeout SECONDS
```
Default:
```text
7200
```
Jubilee debates may be long, so a two-hour per-video timeout is safer than a shorter default.

---

### 9.15 Maximum retries
```bash
--max-retries N
```
Default:
```text
1
```
Must be zero or a positive integer.

---

### 9.16 Retry delay
```bash
--retry-delay SECONDS
```
Default:
```text
5
```
Must be zero or a positive integer.

---

### 9.17 Description
```bash
--write-description
--no-write-description
```
Default:
```text
--write-description
```
The video description is useful contextual metadata and should be saved by default.

---

### 9.18 Subtitles
```bash
--write-subs
--no-write-subs
--write-auto-subs
--no-write-auto-subs
--sub-langs LANGS
```
Recommended defaults:
```text
--write-subs
--write-auto-subs
--sub-langs en.*
```
Since the later phase involves transcription and speaker diarisation, preserving YouTube subtitles/captions may be useful as a reference, even if they are not sufficient for speaker-turn differentiation.

---

### 9.19 Comments
```bash
--write-comments
```
Default:
```text
False
```
Comments can be large and are not necessary for the initial speaker diarisation test. The programme supports comments, but should not enable them by default.

---

## 10. Example Commands

### Default run from inside `cl_st1_ph0_carol/`
```bash
python download_jubilee_debates.py
```
### Metadata-only run from inside `cl_st1_ph0_carol/`
```bash
python download_jubilee_debates.py --metadata-only
```
### Default run from project root
```bash
python cl_st1_ph0_carol/download_jubilee_debates.py
```
### Metadata-only run from project root
```bash
python cl_st1_ph0_carol/download_jubilee_debates.py --metadata-only
```
### Full run
```bash
python download_jubilee_debates.py --no-test-mode
```
### Full run with cookies
```bash
python download_jubilee_debates.py \
  --no-test-mode \
  --cookies env/youtube_cookies.txt
```
### Retry failed downloads with cookies

Some YouTube downloads may fail with errors such as:
```text
HTTP Error 403: Forbidden
```
or a bot-confirmation/authentication message. In that case, retry with a browser-exported cookies file:
```bash
python download_jubilee_debates.py \
  --no-test-mode \
  --cookies env/youtube_cookies.txt \
  --start-corpus-id jubilee_surrounded_002
```
If only selected records failed, use `--start-corpus-id` to resume from the first failed item. If the failed items are not contiguous, rerun with `--reprocess` after ensuring the cookies file is valid, or temporarily adjust the input sample.

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
### Disable subtitles
```bash
python download_jubilee_debates.py \
  --no-write-subs \
  --no-write-auto-subs
```
### Download comments explicitly
```bash
python download_jubilee_debates.py \
  --write-comments
```
---

## 11. Validation Rules

The programme must fail fast with a configuration error if:

- the input metadata file does not exist;
- the input metadata path is not a file;
- the input metadata file is unreadable;
- the input file contains invalid JSON lines;
- no valid records are found in the metadata file;
- `--test-limit` is less than or equal to zero;
- `--workers` is less than or equal to zero;
- `--workers` is not `1` in the first implementation;
- `--timeout` is less than or equal to zero;
- `--max-retries` is negative;
- `--retry-delay` is negative;
- `--cookies` is provided but the cookies file does not exist;
- `--cookies` is provided but the cookies path is not a file;
- `--start-corpus-id` is provided but empty;
- `--start-corpus-id` is provided but not found;
- `--metadata-only` and `--skip-metadata` are both provided;
- `yt-dlp` is not available on the system path.

The programme should check `yt-dlp` availability with:
```bash
yt-dlp --version
```
A validation error should:

- be printed clearly to the console or log;
- be written to the log if logging has already been configured;
- cause the programme to exit with code `2`.

---

## 12. Core Processing Flow

The programme should follow this workflow:

1. **Startup**
   - Parse command-line arguments.
   - Resolve relative paths against the programme directory.
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
     - build the `yt-dlp` command;
     - include `--cookies PATH` if provided;
     - include `--write-info-json` unless `--skip-metadata` is provided;
     - include `--skip-download` if `--metadata-only` is provided;
     - include description/subtitle/comment options as configured;
     - run `yt-dlp`;
     - capture stdout, stderr, return code, timings, and errors;
     - retry failures according to `--max-retries`;
     - move/normalise sidecar files if needed;
     - mark the item status.

6. **Index generation**
   - Read raw `.info.json` files where available.
   - Extract selected metadata fields.
   - Combine with input metadata.
   - Write `jubilee_debates_index.ndjson`.
   - Write project-internal file paths as project-relative strings in the curated index.

7. **Manifest writing**
   - Write latest manifest.
   - Write timestamped manifest.

8. **Exit**
   - Exit `0` if all attempted items succeeded or were skipped.
   - Exit `1` if one or more attempted downloads failed or invalid metadata records exist.
   - Exit `2` for configuration errors.
   - Exit `130` for keyboard interruption.

---

## 13. Suggested Status Values

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

## 14. Manifest Design

The manifest should use this general structure:
```json
{
  "run_metadata": {
    "run_id": "20260817T170458Z",
    "tool_name": "download_jubilee_debates.py",
    "tool_version": "v1",
    "start_time": "2026-08-17T17:04:58Z",
    "end_time": "2026-08-17T17:14:24Z",
    "test_mode": false,
    "test_limit": 5,
    "metadata_only": false,
    "reprocess": false,
    "workers": 1,
    "metadata_path": "corpus/00_sources/jubilee_debates_samples.ndjson",
    "output_dir": "corpus/01_jubilee_debates",
    "index_file": "corpus/01_jubilee_debates/jubilee_debates_index.ndjson",
    "log_file": "corpus/01_jubilee_debates/download_jubilee_debates.log",
    "manifest_file": "corpus/01_jubilee_debates/download_jubilee_debates_manifest.json",
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
      "sub_langs": "en.*",
      "skip_metadata": false
    },
    "yt_dlp": {
      "available": true,
      "version": "2026.07.04"
    },
    "summary": {
      "input_records": 5,
      "valid_records": 5,
      "invalid_records": 0,
      "unique_corpus_items": 5,
      "planned_items": 5,
      "attempted_items": 5,
      "succeeded": 3,
      "failed": 2,
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
      "video_file": "corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4",
      "raw_metadata_file": "corpus/01_jubilee_debates/metadata_raw/jubilee_surrounded_001.info.json",
      "description_file": "corpus/01_jubilee_debates/descriptions/jubilee_surrounded_001.description",
      "status": "success",
      "video_status": "success",
      "metadata_status": "success",
      "error": null,
      "return_code": 0,
      "retries": 1,
      "duration_seconds": 73.25,
      "start_time": "2026-08-17T17:04:58Z",
      "end_time": "2026-08-17T17:06:11Z",
      "metadata": {
        "command": [
          "yt-dlp",
          "--no-overwrites",
          "--write-info-json",
          "-f",
          "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
          "--write-description",
          "--write-subs",
          "--write-auto-subs",
          "--sub-langs",
          "en.*",
          "https://www.youtube.com/watch?v=WV29R1M25n8",
          "-o",
          "corpus/01_jubilee_debates/videos/jubilee_surrounded_001.%(ext)s"
        ],
        "attempts": []
      }
    }
  ],
  "invalid_records": [],
  "duplicates": []
}
```
Manifest path fields should also prefer project-relative paths when they refer to files under the project phase directory. This improves portability and keeps manifests consistent with curated indices.

---

## 15. Logging Specification

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
- resolved metadata path;
- resolved output directory;
- resolved index path;
- test mode status;
- metadata-only status;
- skip-metadata status;
- reprocess status;
- cookies provided or not;
- start corpus ID, if provided;
- `yt-dlp` version;
- number of records loaded;
- number of valid and invalid records;
- number of duplicate records;
- number of planned items;
- number of skipped existing items;
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

## 16. Error Handling and Resiliency

### 16.1 Configuration errors

Configuration errors must stop the programme before downloads begin.

Examples:

- metadata file missing;
- metadata path is not a file;
- invalid command-line arguments;
- cookies file missing when `--cookies` is provided;
- start corpus ID not found when `--start-corpus-id` is provided;
- `yt-dlp` is not installed or not found.

The programme must exit with code `2`.

### 16.2 Per-item errors

Per-item errors must not stop the full run.

Examples:

- video unavailable;
- video private;
- video deleted;
- region restriction;
- malformed URL;
- network error;
- timeout;
- `yt-dlp` non-zero return code;
- YouTube bot-confirmation message.

For each per-item error:

- mark the item as `failed`;
- capture a short error message;
- log the error;
- continue to the next item.

The programme must exit with code `1` if one or more attempted items fail.

A common YouTube/`yt-dlp` failure is:
```text
HTTP Error 403: Forbidden
```
This can be caused by:

- YouTube bot or anti-automation checks;
- missing browser cookies;
- expired browser cookies;
- temporary rate limiting;
- IP reputation or regional access differences;
- a video whose media streams require authenticated access;
- `yt-dlp` needing an update for YouTube extractor changes.

Recommended response:

1. retry later;
2. update `yt-dlp`;
3. retry with `--cookies env/youtube_cookies.txt`;
4. if metadata exists but video media failed, decide whether existing local video/audio files are sufficient for downstream processing.

### 16.3 Invalid metadata records

Rows with missing required fields should be captured in `invalid_records`.

Preferred behaviour:

- continue processing valid records;
- write invalid rows to the manifest;
- exit with code `1` after the run.

Invalid JSON lines are treated as configuration errors and cause exit code `2`.

### 16.4 Keyboard interruption

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

## 17. Suggested Constants

The implementation should define constants near the top of the file.
```python
TOOL_NAME = "download_jubilee_debates.py"
TOOL_VERSION = "v1"

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_METADATA_PATH = "corpus/00_sources/jubilee_debates_samples.ndjson"
DEFAULT_OUTPUT_DIR = "corpus/01_jubilee_debates"

DEFAULT_VIDEOS_DIR_NAME = "videos"
DEFAULT_RAW_METADATA_DIR_NAME = "metadata_raw"
DEFAULT_DESCRIPTIONS_DIR_NAME = "descriptions"
DEFAULT_SUBTITLES_DIR_NAME = "subtitles"
DEFAULT_COMMENTS_DIR_NAME = "comments"

DEFAULT_LOG_FILE = "corpus/01_jubilee_debates/download_jubilee_debates.log"
DEFAULT_MANIFEST_FILE = (
    "corpus/01_jubilee_debates/download_jubilee_debates_manifest.json"
)
DEFAULT_INDEX_FILE = "corpus/01_jubilee_debates/jubilee_debates_index.ndjson"

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

REQUIRED_FIELDS = (
    "corpus_id",
    "youtube_id",
    "youtube_url",
    "title",
    "debate_format",
)
```
---

## 18. Suggested Function Architecture
```python
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments and resolve paths."""


def resolve_script_relative_path(path: Path) -> Path:
    """Resolve relative paths against the programme directory."""


def path_for_index(path_value: Any) -> str | None:
    """Convert project-internal paths to portable project-relative strings for curated indices."""


def setup_logging(log_file: Path) -> logging.Logger:
    """Configure append-only logging."""


def ensure_output_dirs(output_dir: Path) -> dict[str, Path]:
    """Create the output directory structure."""


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and paths."""


def check_yt_dlp() -> dict:
    """Check whether yt-dlp is available and return version metadata."""


def load_samples(
    metadata_path: Path,
) -> tuple[list[dict], list[dict], list[dict], int]:
    """Load, validate, and deduplicate debate sample records."""


def output_paths_for_record(record: dict, output_dir: Path) -> dict:
    """Compute expected output paths for one record."""


def item_outputs_satisfied(
    paths: dict,
    args: argparse.Namespace,
) -> tuple[bool, str]:
    """Determine whether requested outputs already exist."""


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
    logger: logging.Logger,
    corpus_id: str,
) -> dict:
    """Run yt-dlp with retries and return structured execution metadata."""


def normalise_sidecar_files(
    item: dict,
    output_paths: dict,
    args: argparse.Namespace,
) -> dict:
    """Move or rename yt-dlp sidecar files into the expected project layout."""


def load_raw_metadata(raw_metadata_path: Path | None) -> dict:
    """Load a raw yt-dlp info JSON file if available."""


def extract_curated_metadata(
    input_record: dict,
    raw_metadata_path: Path | None,
    local_paths: dict,
    run_metadata: dict,
    item_result: dict,
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


def make_initial_run_metadata(
    args: argparse.Namespace,
    run_id: str,
    start_time: str,
    yt_dlp_info: dict | None = None,
) -> dict:
    """Construct the initial run metadata dictionary."""


def item_result_from_skipped(
    item: dict,
    run_metadata: dict,
) -> dict:
    """Create a manifest item result for an existing skipped item."""


def process_item(
    item: dict,
    args: argparse.Namespace,
    logger: logging.Logger,
) -> tuple[dict, dict]:
    """Process one planned item with yt-dlp."""


def main() -> int:
    """Run the complete Jubilee debate download workflow."""
```
---

## 19. Exit Codes

| Exit code | Meaning                                                               |
|----------:|-----------------------------------------------------------------------|
|       `0` | Completed with no failures                                            |
|       `1` | Completed, but one or more items failed or invalid metadata was found |
|       `2` | Configuration or validation error                                     |
|     `130` | Interrupted by user                                                   |

---

## 20. Acceptance Criteria

The programme is considered complete when:

1. Running from inside `cl_st1_ph0_carol/` works:

   ```bash
   python download_jubilee_debates.py
   ```

2. Running from the project root works:

   ```bash
   python cl_st1_ph0_carol/download_jubilee_debates.py
   ```

3. Default relative paths are resolved relative to the programme directory, not the current working directory.

4. It reads:

   ```text
   cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson
   ```

5. It creates:

   ```text
   cl_st1_ph0_carol/corpus/01_jubilee_debates/
   ```

6. It downloads videos into:

   ```text
   cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/
   ```

7. Video filenames are based on `corpus_id`.

8. It saves raw `yt-dlp` metadata into:

   ```text
   cl_st1_ph0_carol/corpus/01_jubilee_debates/metadata_raw/
   ```

9. It writes descriptions into:

   ```text
   cl_st1_ph0_carol/corpus/01_jubilee_debates/descriptions/
   ```

   when descriptions are enabled.

10. It writes subtitles into:

    ```text
    cl_st1_ph0_carol/corpus/01_jubilee_debates/subtitles/
    ```

    when subtitles or automatic captions are enabled.

11. It writes comments into:

    ```text
    cl_st1_ph0_carol/corpus/01_jubilee_debates/comments/
    ```

    when comments are explicitly enabled.

12. It writes a curated index:

    ```text
    cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
    ```

13. The curated index preserves Carol’s sample metadata and adds selected `yt-dlp` metadata.

14. The curated index writes project-internal file paths as project-relative paths, for example:

    ```text
    corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4
    ```

    rather than:

    ```text
    /home/<user>/PycharmProjects/cl_st1_carol/cl_st1_ph0_carol/corpus/01_jubilee_debates/videos/jubilee_surrounded_001.mp4
    ```

15. The curated index should not contain machine-specific absolute paths for files located inside the project phase directory.

16. Failed downloads are represented in the curated index with `download_status = failed`, and should preserve any metadata files that were successfully written.

17. Existing outputs are skipped by default.

18. `--reprocess` forces reprocessing.

19. `--metadata-only` fetches metadata without downloading video files.

20. `--skip-metadata` avoids refreshing raw metadata and relies on existing metadata where available.

21. `--metadata-only` and `--skip-metadata` cannot be used together.

22. `--cookies PATH` is supported.

23. `--start-corpus-id CORPUS_ID` is supported.

24. Failed downloads do not stop the entire batch.

25. Logs are written to:

    ```text
    cl_st1_ph0_carol/corpus/01_jubilee_debates/download_jubilee_debates.log
    ```

26. Latest and timestamped manifests are written.

27. The programme exits with the specified exit codes.

---

## 21. Design Decision Summary

The main project-specific design choices are:

| Decision                                                                            | Rationale                                                                        |
|-------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| Resolve paths relative to the script directory                                      | Prevents accidental nested paths when running from different working directories |
| Use `corpus_id` for filenames                                                       | Stable, clean, research-oriented identifier                                      |
| Keep raw `.info.json` files                                                         | Preserves full `yt-dlp` metadata for reproducibility                             |
| Also generate curated NDJSON index                                                  | Easier for analysis and downstream scripts                                       |
| Separate `videos/`, `metadata_raw/`, `descriptions/`, `subtitles/`, and `comments/` | Keeps corpus directory organised                                                 |
| Default `test-limit = 5`                                                            | Matches the current initial sample size                                          |
| Support metadata-only mode                                                          | Useful before large downloads and for metadata inspection                        |
| Save Carol’s reported view counts separately                                        | Distinguishes selection-time popularity from download-time metadata              |
| Prefer `--start-corpus-id` over `--start-video-id`                                  | Corpus IDs are the internal stable identifiers                                   |
| Write descriptions and subtitles by default                                         | Useful contextual material for later transcription and diarisation work          |
| Do not write comments by default                                                    | Comments can be large and are not required for the initial diarisation test      |
| Write project-relative paths in curated indices                                     | Makes corpus metadata portable between local machines and EC2                    |
| Preserve failed download records in the index                                       | Keeps the corpus plan auditable while accurately recording unavailable media     |
| Allow cookies for YouTube `403 Forbidden` / bot checks                              | Some videos require browser-authenticated requests or fresh cookies              |