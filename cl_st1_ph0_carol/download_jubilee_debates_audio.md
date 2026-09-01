# `download_jubilee_debates_audio.py` — Programme Specification for Development

## 1. Programme Summary

`download_jubilee_debates_audio.py` is a batch-processing programme that directly downloads Whisper-ready audio and associated metadata for selected Jubilee debates for **Corpus Linguistics — Study 1 — Carol, Phase 0**.

The programme is located at:
```text
cl_st1_ph0_carol/download_jubilee_debates_audio.py
```

The programme reads an NDJSON input file containing the debate sample selected by Carol:
```text
cl_st1_ph0_carol/corpus/00_sources/jubilee_debates_samples.ndjson
```

To solve strict storage constraints on the processing server, this programme uses `yt-dlp` to directly download the audio stream and process it natively with `ffmpeg` in memory/stream, bypassing the need to save and delete heavy `.mp4` video files.

The outputs are:
1. Full-length audio files formatted natively for Whisper/WhisperX and pyannote.audio (WAV, mono, 16 kHz, signed 16-bit PCM).
2. The full raw metadata file produced by `yt-dlp`.
3. Description files, by default.
4. Subtitles and automatic captions, by default.
5. A curated corpus index file (`jubilee_debates_audio_index.ndjson`) that extracts and normalises metadata for downstream stages.

The curated index must be **portable across machines**, writing project-relative paths whenever files are inside the project directory (e.g. `corpus/01_jubilee_debates_audio/audio/jubilee_surrounded_001.wav`).

---

## 2. Path Resolution Policy

The programme must resolve its **default paths relative to the directory where `download_jubilee_debates_audio.py` is located**.

### Internal path base
```python
SCRIPT_DIR = Path(__file__).resolve().parent
```

### Portable paths in curated index files
The curated corpus index should not store machine-specific absolute paths.
For fields that refer to files inside the project phase directory, write paths relative to `SCRIPT_DIR` (e.g. `corpus/01_jubilee_debates_audio/audio/jubilee_surrounded_001.wav`).

---

## 3. Output Directory Structure

Because we are skipping the video download stage, this programme becomes Stage 01. The outputs are organised as follows:

```text
cl_st1_ph0_carol/corpus/01_jubilee_debates_audio/
├── audio/
│   ├── jubilee_surrounded_001.wav
│   ├── jubilee_surrounded_002.wav
│   └── ...
├── metadata_raw/
│   ├── jubilee_surrounded_001.info.json
│   └── ...
├── descriptions/
│   ├── jubilee_surrounded_001.description
│   └── ...
├── subtitles/
│   ├── jubilee_surrounded_001.en.vtt
│   └── ...
├── jubilee_debates_audio_index.ndjson
├── download_jubilee_debates_audio.log
├── download_jubilee_debates_audio_manifest.json
└── download_jubilee_debates_audio_manifest_<run_id>.json
```

---

## 4. Download Behaviour & yt-dlp Audio Command

For each valid input record, the programme should download the audio using `yt-dlp` configured to extract audio directly.

The `yt-dlp` command should be equivalent to:
```bash
yt-dlp \
  -f "bestaudio/best" \
  --extract-audio \
  --audio-format wav \
  --postprocessor-args "-ac 1 -ar 16000 -sample_fmt s16" \
  --write-info-json \
  --write-description \
  --write-subs \
  --write-auto-subs \
  --sub-langs "en.*" \
  "https://www.youtube.com/watch?v=WV29R1M25n8" \
  -o "cl_st1_ph0_carol/corpus/01_jubilee_debates_audio/audio/jubilee_surrounded_001.%(ext)s"
```

*Note: yt-dlp uses `ffmpeg` implicitly via `--extract-audio`. The `--postprocessor-args` ensure it converts directly into the Whisper/pyannote compatible format (16kHz, mono, s16le PCM) without needing a secondary script.*

---

## 5. Metadata Selection for Curated Index

The curated index file:
```text
cl_st1_ph0_carol/corpus/01_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```
must combine input metadata, selected `yt-dlp` metadata, and the local file paths.

### Example curated index record
```json
{
  "corpus_id": "jubilee_surrounded_001",
  "debate_format": "Surrounded",
  "title_selected": "1 Conservative vs 25 Liberal College Students",
  "youtube_id": "WV29R1M25n8",
  "duration_seconds": 5427,
  "audio_file": "corpus/01_jubilee_debates_audio/audio/jubilee_surrounded_001.wav",
  "audio_format": "wav",
  "audio_codec": "pcm_s16le",
  "audio_channels": 1,
  "audio_sample_rate": 16000,
  "audio_file_size_bytes": 173651160,
  "raw_metadata_file": "corpus/01_jubilee_debates_audio/metadata_raw/jubilee_surrounded_001.info.json",
  "description_file": "corpus/01_jubilee_debates_audio/descriptions/jubilee_surrounded_001.description",
  "subtitles_files": [
    "corpus/01_jubilee_debates_audio/subtitles/jubilee_surrounded_001.en.vtt"
  ],
  "download_status": "success",
  "metadata_status": "success",
  "download_run_id": "20260817T170458Z",
  "download_duration_seconds": 124.5,
  "yt_dlp_version": "2026.07.04"
}
```

*Crucially, `duration_seconds` must reflect the original media duration from yt-dlp metadata, and `download_duration_seconds` reflects the runtime of the `yt-dlp` download command.*

---

## 6. Command-line Interface

### Default usage
```bash
python download_jubilee_debates_audio.py
```
This runs in `--test-mode` with a default limit of `5` debates, skipping existing files.

### Full run
```bash
python download_jubilee_debates_audio.py --no-test-mode
```

### Resume from a specific corpus ID
```bash
python download_jubilee_debates_audio.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

### Run with YouTube Cookies (for restricted videos)
```bash
python download_jubilee_debates_audio.py \
  --no-test-mode \
  --cookies env/youtube_cookies.txt
```

---

## 7. Exit Codes

| Exit code | Meaning                                                               |
|----------:|-----------------------------------------------------------------------|
|       `0` | Completed with no failures                                            |
|       `1` | Completed, but one or more items failed or invalid metadata was found |
|       `2` | Configuration or validation error                                     |
|     `130` | Interrupted by user                                                   |

---

## 8. Suggested Constants

```python
TOOL_NAME = "download_jubilee_debates_audio.py"
TOOL_VERSION = "v1"

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_METADATA_PATH = "corpus/00_sources/jubilee_debates_samples.ndjson"
DEFAULT_OUTPUT_DIR = "corpus/01_jubilee_debates_audio"

DEFAULT_AUDIO_DIR_NAME = "audio"
DEFAULT_RAW_METADATA_DIR_NAME = "metadata_raw"
DEFAULT_DESCRIPTIONS_DIR_NAME = "descriptions"
DEFAULT_SUBTITLES_DIR_NAME = "subtitles"
DEFAULT_COMMENTS_DIR_NAME = "comments"

DEFAULT_LOG_FILE = "corpus/01_jubilee_debates_audio/download_jubilee_debates_audio.log"
DEFAULT_MANIFEST_FILE = "corpus/01_jubilee_debates_audio/download_jubilee_debates_audio_manifest.json"
DEFAULT_INDEX_FILE = "corpus/01_jubilee_debates_audio/jubilee_debates_audio_index.ndjson"

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 7200
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

YT_DLP_AUDIO_FORMAT = "bestaudio/best"
YT_DLP_POSTPROCESSOR_ARGS = "-ac 1 -ar 16000 -sample_fmt s16"

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

## 9. Next Steps

With this spec, the entire video download process and secondary audio extraction script (`extract_jubilee_debates_audio.py`) are unified into a single pipeline step. `yt-dlp` automatically wraps `ffmpeg` to handle the heavy lifting natively.