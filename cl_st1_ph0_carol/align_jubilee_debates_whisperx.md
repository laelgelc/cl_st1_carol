# `align_jubilee_debates_whisperx.py` — Programme Specification for Development

## 1. High-level Functionality Specification

### Programme Summary

`align_jubilee_debates_whisperx.py` is a batch-processing programme that performs WhisperX forced alignment for previously transcribed full-length Jubilee debate audio files.

The programme is part of:

```plain text
Corpus Linguistics — Study 1 — Carol, Phase 0 — Speaker Diarisation Test
```


It is the second GPU-oriented speech-processing stage after transcription.

The preceding stage is:

```plain text
transcribe_jubilee_debates_whisperx.py
```


The following stages are:

| Stage | Programme |
|---:|---|
| 3 | `diarise_jubilee_debates_pyannote.py` |
| 4 | `assign_speakers_jubilee_debates.py` |
| 5 | `qc_jubilee_debates_speaker_diarisation.py` |

The programme reads the curated transcript index produced by the transcription stage:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
```


Each record in this index represents one eligible Jubilee debate transcript. The programme must process records where the transcription is available, indicated by:

```plain text
transcription_status = success
```


or:

```plain text
transcription_status = skipped_existing
```


For each eligible record, the programme uses:

- `corpus_id` to identify the debate;
- `audio_file` to locate the source WAV file when present and usable;
- `<audio-dir>/<corpus_id>.wav` as a fallback audio path;
- `transcript_json_file` to locate the segment-level transcript JSON when present and usable;
- `<transcript-dir>/<corpus_id>.json` as a fallback transcript JSON path;
- `corpus_id` again to name alignment outputs.

The source audio files are expected in:

```plain text
corpus/02_jubilee_debates_audio/
```


The source transcript JSON files are expected in:

```plain text
corpus/03_jubilee_debates_transcripts/
```


Alignment outputs must be written to:

```plain text
corpus/04_jubilee_debates_alignment/
```


For each successfully aligned debate, the programme must write:

```plain text
corpus/04_jubilee_debates_alignment/<corpus_id>.aligned.json
```


It should also write a compact word-level NDJSON file when possible:

```plain text
corpus/04_jubilee_debates_alignment/<corpus_id>.words.ndjson
```


The `.aligned.json` file contains:

- copied source metadata;
- original transcript segment information;
- aligned segment information;
- word-level or near-word-level timestamps;
- alignment model metadata;
- run metadata;
- item status.

The `.words.ndjson` file contains one aligned word/token per line for easier downstream speaker assignment and QC.

The intended alignment engine is:

```plain text
WhisperX forced alignment
```


This programme performs **alignment only**. It must not perform:

- initial Whisper transcription;
- speaker diarisation;
- assignment of speakers to words;
- speaker identity resolution;
- quality-control report generation.

---

## 2. Key Behaviours

The programme must implement the following behaviours:

- Read Jubilee debate transcript metadata from an NDJSON transcript index.
- Process only records where `transcription_status` indicates usable transcript outputs.
- Extract required fields:
  - `corpus_id`.
- Locate source audio using:
  - `audio_file`, when present and usable;
  - otherwise `<audio_dir>/<corpus_id>.wav`.
- Locate source transcript JSON using:
  - `transcript_json_file`, when present and usable;
  - otherwise `<transcript_dir>/<corpus_id>.json`.
- Load the transcript JSON and extract:
  - transcript language;
  - transcript text;
  - segment-level timestamps;
  - segment text.
- Use WhisperX forced alignment to align transcript segments to the source audio.
- Write aligned JSON output as:

```plain text
<output_dir>/<corpus_id>.aligned.json
```


- Write word-level NDJSON output as:

```plain text
<output_dir>/<corpus_id>.words.ndjson
```


- Create the output directory if it does not already exist.
- Load the alignment model once per run where practical.
- Use GPU acceleration by default where available.
- Use English alignment by default:

```plain text
language = en
```


- Use test mode by default, limiting processing to 1 eligible debate.
- Skip already-aligned debates by default, supporting safe re-runs.
- Allow reprocessing with an explicit command-line option.
- Support starting from a specific `corpus_id`.
- Continue processing remaining debates if one alignment fails.
- Record progress and errors in an append-only log file.
- Produce a JSON manifest with run-level metadata and item-level results.
- Write both:
  - a timestamped per-run manifest;
  - a latest manifest overwritten on each run.
- Write a curated alignment index for downstream speaker assignment.
- Exit with status code `0` only when all attempted alignments succeed or are skipped, and there are no missing inputs or invalid eligible metadata rows.
- Exit with a non-zero status code if one or more attempted alignments fail, if source audio or transcript JSON is missing, if eligible metadata is invalid, or if there is a configuration/validation error.

---

## 3. Path Resolution Policy

The programme must resolve its default paths relative to the directory where `align_jubilee_debates_whisperx.py` is located, not relative to the current working directory.

If the script is located at:

```plain text
cl_st1_ph0_carol/align_jubilee_debates_whisperx.py
```


then the default transcript index path:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
```


must resolve to:

```plain text
cl_st1_ph0_carol/corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
```


This ensures that the programme works when executed from:

```plain text
cl_st1_carol/
```


or:

```plain text
cl_st1_carol/cl_st1_ph0_carol/
```


or from another current working directory.

### Internal path base

The implementation should define:

```python
SCRIPT_DIR = Path(__file__).resolve().parent
```


Relative default paths and relative command-line paths should be resolved against `SCRIPT_DIR`.

### Absolute paths

If the user supplies an absolute path for arguments such as:

- `--transcript-index`
- `--audio-dir`
- `--transcript-dir`
- `--output-dir`
- `--log-file`
- `--manifest-file`
- `--alignment-index-file`

the programme must preserve that absolute path.

---

## 4. Input / Output Specification

## 4.1 Input

### Input transcript index file

Default path:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
```


The file is expected to be in **NDJSON** format: one JSON object per line.

This file is produced by the preceding transcription stage.

### Required fields

Each valid eligible transcript-index record must contain:

| Field | Type | Description |
|---|---:|---|
| `corpus_id` | string | Stable internal debate identifier, e.g. `jubilee_surrounded_001` |
| `transcription_status` | string | Status from the transcription stage |

The source audio path is resolved using:

| Field | Requirement | Description |
|---|---|---|
| `audio_file` | optional | Preferred local WAV path when present and usable |

If `audio_file` is absent, blank, or unusable, the programme must fall back to:

```plain text
<audio_dir>/<corpus_id>.wav
```


The transcript JSON path is resolved using:

| Field | Requirement | Description |
|---|---|---|
| `transcript_json_file` | optional | Preferred local transcript JSON path when present and usable |

If `transcript_json_file` is absent, blank, or unusable, the programme must fall back to:

```plain text
<transcript_dir>/<corpus_id>.json
```


### Eligible transcription statuses

The programme must process only records where:

```plain text
transcription_status = success
```


or:

```plain text
transcription_status = skipped_existing
```


Records with other statuses must be ignored, not treated as errors.

Ineligible statuses include:

```plain text
failed
missing_input
failed_metadata
ignored_audio_unavailable
interrupted
null
""
missing value
```


### Transcript JSON requirements

The transcript JSON file must contain enough information for alignment.

Required fields or equivalent structure:

| Field | Description |
|---|---|
| `corpus_id` | Debate ID |
| `transcription.text` | Full transcript text |
| `transcription.segments` | Segment list with text and timestamps |
| `model.language` or `transcription.detected_language` | Language information if available |

Each segment should include at least:

```json
{
  "id": 1,
  "start": 0.0,
  "end": 4.28,
  "text": "Example transcript segment."
}
```


If transcript JSON is malformed or lacks usable segments, the item must be marked as `failed_metadata` or `failed`, depending on when the problem is detected:

- missing `corpus_id` in an eligible transcript-index row: `failed_metadata`;
- transcript JSON cannot be parsed or lacks usable transcript data: `failed`.

### Metadata fields to preserve

The programme should preserve these fields in alignment outputs and indices when present:

| Field | Description |
|---|---|
| `corpus_id` | Internal stable corpus ID |
| `debate_format` | Debate format |
| `sample_group` | Sample group |
| `sample_order` | Sample order |
| `title` | Selected title, if present |
| `title_selected` | Selected title |
| `title_extracted` | Extracted title |
| `youtube_id` | YouTube video ID |
| `youtube_url` | Original YouTube URL |
| `webpage_url` | Canonical URL |
| `duration_seconds` | Source duration |
| `duration_string` | Human-readable duration |
| `chapters` | Chapter metadata |
| `audio_file` | Source WAV path |
| `transcript_text_file` | Transcript text path |
| `transcript_json_file` | Transcript JSON path |
| `transcription_status` | Previous stage status |
| `transcription_run_id` | Previous stage run ID |
| `transcribed_at_utc` | Previous stage timestamp |
| `transcript_characters` | Transcript character count |
| `segment_count` | Segment count |
| `detected_language` | Detected language |
| `language_probability` | Language probability |
| `model_name` | Transcription model name |
| `backend` | Transcription backend |
| `device` | Transcription device |
| `compute_type` | Transcription compute type |
| `batch_size` | Transcription batch size |
| `audio_extraction_status` | Audio extraction stage status |
| `audio_extraction_run_id` | Audio extraction stage run ID |
| `selected_by` | Selector |
| `selection_source` | Selection source |
| `notes` | Notes |

---

## 4.2 Input audio files

### Audio input directory

Default path:

```plain text
corpus/02_jubilee_debates_audio/
```


Each fallback source audio file is expected as:

```plain text
<audio_dir>/<corpus_id>.wav
```


Examples:

```plain text
corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav
corpus/02_jubilee_debates_audio/jubilee_surrounded_002.wav
```


The audio extraction stage should have produced WAV files with:

| Property | Expected value |
|---|---:|
| Container | WAV |
| Channels | mono |
| Sample rate | 16000 Hz |
| Sample format | signed 16-bit PCM |

The alignment programme may rely on the audio extraction programme for audio compatibility.

---

## 4.3 Input transcript files

### Transcript input directory

Default path:

```plain text
corpus/03_jubilee_debates_transcripts/
```


Each fallback transcript JSON file is expected as:

```plain text
<transcript_dir>/<corpus_id>.json
```


Examples:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.json
corpus/03_jubilee_debates_transcripts/jubilee_surrounded_002.json
```


The transcript JSON files should have been produced by:

```plain text
transcribe_jubilee_debates_whisperx.py
```


---

## 4.4 Output

### Alignment output directory

Default path:

```plain text
corpus/04_jubilee_debates_alignment/
```


The programme must create this directory if it does not already exist.

### Per-debate aligned JSON

Each successful alignment must write:

```plain text
<output_dir>/<corpus_id>.aligned.json
```


Example:

```plain text
corpus/04_jubilee_debates_alignment/jubilee_surrounded_001.aligned.json
```


### Per-debate word NDJSON

Each successful alignment should write:

```plain text
<output_dir>/<corpus_id>.words.ndjson
```


Example:

```plain text
corpus/04_jubilee_debates_alignment/jubilee_surrounded_001.words.ndjson
```


This file should contain one aligned word/token per line when word-level data is available.

### Log file

Default path:

```plain text
corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx.log
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

```plain text
corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx_manifest.json
```


#### Per-run manifest

A timestamped copy must also be written using the run ID.

Filename pattern:

```plain text
align_jubilee_debates_whisperx_manifest_<run_id>.json
```


Example:

```plain text
corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx_manifest_20260730T230000Z.json
```


### Alignment index file

Default path:

```plain text
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
```


This curated alignment index is used by downstream speaker assignment and QC stages.

---

# 5. Command-line Interface

## 5.1 Default usage

The programme may be run from inside `cl_st1_ph0_carol/`:

```shell script
python align_jubilee_debates_whisperx.py
```


or from the project root:

```shell script
python cl_st1_ph0_carol/align_jubilee_debates_whisperx.py
```


Both commands should resolve default paths correctly.

Default behaviour:

- transcript index:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
```


- audio directory:

```plain text
corpus/02_jubilee_debates_audio/
```


- transcript directory:

```plain text
corpus/03_jubilee_debates_transcripts/
```


- output directory:

```plain text
corpus/04_jubilee_debates_alignment/
```


- backend:

```plain text
whisperx
```


- alignment language:

```plain text
en
```


- device:

```plain text
cuda
```


- batch size:

```plain text
8
```


- return character alignments:

```plain text
false
```


- test mode:

```plain text
enabled
```


- test limit:

```plain text
1
```


- reprocess:

```plain text
disabled
```


- existing `.aligned.json` and `.words.ndjson` files are skipped;
- one worker / sequential processing.

### Note on default test limit

This project processes long-form debate audio. The default test limit should remain:

```plain text
1
```


---

## 5.2 Required arguments

There are no required command-line arguments if all defaults are used.

---

## 5.3 Optional arguments

### Transcript index

```shell script
--transcript-index PATH
```


Default:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
```


Description:

Path to the curated NDJSON transcript index from the transcription stage.

---

### Audio directory

```shell script
--audio-dir PATH
```


Default:

```plain text
corpus/02_jubilee_debates_audio/
```


Description:

Fallback directory containing source WAV files.

---

### Transcript directory

```shell script
--transcript-dir PATH
```


Default:

```plain text
corpus/03_jubilee_debates_transcripts/
```


Description:

Fallback directory containing transcript JSON files.

---

### Output directory

```shell script
--output-dir PATH
```


Default:

```plain text
corpus/04_jubilee_debates_alignment/
```


Description:

Directory where alignment outputs, logs, manifests, and alignment index are written.

---

### Backend

```shell script
--backend BACKEND
```


Default:

```plain text
whisperx
```


Allowed values:

```plain text
whisperx
```


Description:

Backend label recorded in outputs. The first implementation should use WhisperX forced alignment.

---

### Device

```shell script
--device DEVICE
```


Default:

```plain text
cuda
```


Allowed values:

```plain text
cuda
cpu
auto
```


For EC2 GPU processing, use:

```plain text
cuda
```


If `--device cuda` is requested and CUDA is unavailable, fail fast with configuration error.

---

### Language

```shell script
--language LANGUAGE_CODE
```


Default:

```plain text
en
```


Description:

Language code used to load the WhisperX alignment model.

If set to:

```plain text
auto
```


the programme should infer language from the transcript JSON or transcript index. If no language can be inferred, fall back to:

```plain text
en
```


and log a warning.

---

### Batch size

```shell script
--batch-size N
```


Default:

```plain text
8
```


Must be a positive integer.

If CUDA out-of-memory occurs, reduce to:

```plain text
4
```


or:

```plain text
2
```


---

### Return character alignments

```shell script
--return-char-alignments
--no-return-char-alignments
```


Default:

```plain text
--no-return-char-alignments
```


Description:

Whether WhisperX should return character-level alignments in addition to word-level alignment.

For initial corpus processing, word-level alignment is sufficient and more compact.

---

### Interpolate method

```shell script
--interpolate-method METHOD
```


Default:

```plain text
nearest
```


Suggested allowed values:

```plain text
nearest
linear
ignore
```


Description:

Interpolation method for words whose timestamps cannot be directly aligned, if supported by the WhisperX API.

---

### Test mode

```shell script
--test-mode
--no-test-mode
```


Default:

```plain text
--test-mode
```


---

### Test limit

```shell script
--test-limit N
```


Default:

```plain text
1
```


Must be a positive integer.

---

### Reprocess existing alignments

```shell script
--reprocess
```


Default:

```plain text
False
```


When omitted, debates with both alignment outputs present are skipped.

When provided, alignment is run again and existing outputs are overwritten.

---

### Start corpus ID

```shell script
--start-corpus-id CORPUS_ID
```


Default:

```plain text
None
```


Start planning from a specific `corpus_id`.

Example:

```shell script
python align_jubilee_debates_whisperx.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```


---

### Log file

```shell script
--log-file PATH
```


Default:

```plain text
corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx.log
```


---

### Manifest file

```shell script
--manifest-file PATH
```


Default:

```plain text
corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx_manifest.json
```


---

### Alignment index file

```shell script
--alignment-index-file PATH
```


Default:

```plain text
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
```


---

### Workers

```shell script
--workers N
```


Default:

```plain text
1
```


Only `--workers 1` is supported in the first implementation.

---

### Timeout

```shell script
--timeout SECONDS
```


Default suggestion:

```plain text
14400
```


A four-hour per-item timeout is appropriate for long debate alignment. Strict timeout enforcement may require subprocess isolation; the first implementation may record the value without hard enforcement.

---

### Maximum retries

```shell script
--max-retries N
```


Default:

```plain text
1
```


---

### Retry delay

```shell script
--retry-delay SECONDS
```


Default:

```plain text
5
```


---

## 5.4 Example commands

### Default one-debate alignment test

```shell script
python align_jubilee_debates_whisperx.py
```


### Test from a specific corpus ID

```shell script
python align_jubilee_debates_whisperx.py \
  --test-limit 1 \
  --start-corpus-id jubilee_surrounded_003
```


### Full alignment run

```shell script
python align_jubilee_debates_whisperx.py --no-test-mode
```


### Full alignment run with smaller batch size

```shell script
python align_jubilee_debates_whisperx.py \
  --no-test-mode \
  --batch-size 4
```


### Re-align all debates

```shell script
python align_jubilee_debates_whisperx.py \
  --no-test-mode \
  --reprocess
```


### EC2 run inside `tmux`

```shell script
tmux new -s jubilee_align
conda activate whisperx_pyannote
cd ~/cl_st1_carol/cl_st1_ph0_carol
python align_jubilee_debates_whisperx.py --no-test-mode
```


Detach:

```plain text
Ctrl+B
D
```


Reattach:

```shell script
tmux attach -t jubilee_align
```


---

# 6. Argument Validation

The programme must fail fast with a clear message if:

- the transcript index file does not exist;
- the transcript index path is not a file;
- the transcript index is unreadable;
- the transcript index contains invalid JSON lines;
- no eligible transcript records are found;
- the audio directory does not exist;
- the audio directory is not a directory;
- the transcript directory does not exist;
- the transcript directory is not a directory;
- the output directory cannot be created;
- `--backend` is unsupported;
- `--device` is missing or blank;
- `--language` is missing or blank;
- `--batch-size` is less than or equal to zero;
- `--test-limit` is less than or equal to zero;
- `--workers` is less than or equal to zero;
- `--workers` is not `1`;
- `--timeout` is less than or equal to zero;
- `--max-retries` is negative;
- `--retry-delay` is negative;
- `--start-corpus-id` is provided but empty;
- `--start-corpus-id` is provided but not found among eligible transcript records;
- the required Python packages are not installed;
- `--device cuda` is requested but CUDA is unavailable;
- the WhisperX alignment model cannot be loaded.

A validation error should:

- be printed clearly to the console;
- be written to the log if logging has already been configured;
- cause the programme to exit with code `2`.

---

# 7. Environment and Configuration

## 7.1 Recommended EC2 environment

Recommended EC2 deployment:

```plain text
Architecture: x86_64
Instance type: g5.xlarge initially
GPU: NVIDIA A10G, 24 GB VRAM
AMI: AWS Deep Learning AMI GPU, Ubuntu
Python: 3.11
Environment manager: conda
Environment name: whisperx_pyannote
Workers: 1
```


If memory or runtime is problematic, consider:

```plain text
g5.2xlarge
```


or:

```plain text
g5.4xlarge
```


## 7.2 Required Python packages

Required:

```plain text
whisperx
torch
torchaudio
```


Optional:

```plain text
tqdm
huggingface_hub
```


## 7.3 CUDA checks

Before alignment, verify:

```shell script
nvidia-smi
```


and:

```shell script
python -c "import torch; print(torch.cuda.is_available()); print(torch.version.cuda)"
```


If CUDA is unavailable and `--device cuda` was requested, fail fast.

---

# 8. Core Processing Architecture

## 8.1 High-level flow

The programme must follow this workflow:

1. **Startup**
   - Parse command-line arguments.
   - Resolve relative paths against programme directory.
   - Validate argument values.
   - Generate UTC `run_id`.
   - Ensure output directory exists.
   - Configure append-only logging.
   - Check Python package availability.
   - Check CUDA availability if requested.

2. **Transcript index loading**
   - Open the NDJSON transcript index.
   - Read records line by line.
   - Parse each JSON object.
   - Count total records.
   - Select only records where `transcription_status` is eligible.
   - Validate required field:
     - `corpus_id`.
   - Preserve input order.
   - Record invalid eligible rows.
   - Record ignored rows where transcription is unavailable.

3. **Planning**
   - Apply `--start-corpus-id`, if provided.
   - Resolve input audio path.
   - Resolve input transcript JSON path.
   - Compute output paths:
     - `<output_dir>/<corpus_id>.aligned.json`;
     - `<output_dir>/<corpus_id>.words.ndjson`.
   - Check missing audio.
   - Check missing transcript JSON.
   - Skip if outputs already exist and `--reprocess` is not enabled.
   - Apply test-mode limit to planned alignments.

4. **Model loading**
   - Load WhisperX alignment model once per language where practical.
   - For current project, English is default.
   - If language is `auto`, infer language per record.
   - If multiple languages appear, either:
     - load per-language model as needed; or
     - fail if multi-language support is not implemented.
   - For first implementation, English-only alignment is acceptable.

5. **Execution**
   - For each planned item:
     - load transcript JSON;
     - extract segments;
     - load or reuse alignment model;
     - run WhisperX alignment;
     - normalise output structure;
     - write `.aligned.json`;
     - write `.words.ndjson`;
     - capture timing, warnings, and errors;
     - retry according to `--max-retries`;
     - mark item as `success` or `failed`.

6. **Alignment index generation**
   - Combine source metadata and alignment metadata.
   - Write curated NDJSON alignment index.

7. **Manifest writing**
   - Count summary statistics.
   - Write latest manifest.
   - Write per-run manifest.

8. **Exit**
   - Exit `0`, `1`, `2`, or `130` according to run outcome.

---

## 8.2 Separation of concerns

Suggested function responsibilities:

```python
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the alignment programme."""
```


```python
def resolve_script_relative_path(path: Path) -> Path:
    """Resolve relative paths against the programme directory."""
```


```python
def setup_logging(log_file: Path) -> logging.Logger:
    """Configure append-only UTF-8 logging."""
```


```python
def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and filesystem paths."""
```


```python
def check_alignment_dependencies() -> dict:
    """Check required Python package availability."""
```


```python
def check_cuda_available(device: str) -> dict:
    """Validate CUDA availability when requested."""
```


```python
def load_transcript_index(
    transcript_index_path: Path,
) -> tuple[list[dict], list[dict], int, int, list[dict]]:
    """Load and validate eligible transcript records from NDJSON."""
```


```python
def resolve_audio_path(record: dict, audio_dir: Path) -> Path:
    """Resolve source audio path using audio_file or fallback audio directory."""
```


```python
def resolve_transcript_json_path(record: dict, transcript_dir: Path) -> Path:
    """Resolve transcript JSON path using transcript_json_file or fallback transcript directory."""
```


```python
def plan_alignments(
    records: list[dict],
    audio_dir: Path,
    transcript_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_corpus_id: str | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Create planned, skipped, and missing-input alignment records."""
```


```python
def load_transcript_json(transcript_json_path: Path) -> dict:
    """Load one transcript JSON file."""
```


```python
def extract_segments_for_alignment(transcript_json: dict) -> list[dict]:
    """Extract stable segment list for WhisperX alignment."""
```


```python
def load_alignment_model(language: str, device: str) -> tuple[Any, Any]:
    """Load WhisperX alignment model and metadata."""
```


```python
def align_one_debate(
    item: dict,
    alignment_model: Any,
    alignment_metadata: Any,
    model_config: dict,
    max_retries: int,
    retry_delay: int,
    logger: logging.Logger,
) -> dict:
    """Align one debate transcript to audio and return a structured result."""
```


```python
def normalise_alignment_result(raw_alignment: dict) -> dict:
    """Normalise WhisperX alignment output into project-stable JSON."""
```


```python
def write_alignment_outputs(
    aligned_json: dict,
    word_records: list[dict],
    aligned_json_path: Path,
    words_ndjson_path: Path,
) -> None:
    """Write aligned JSON and word-level NDJSON outputs."""
```


```python
def write_alignment_index(index_records: list[dict], alignment_index_file: Path) -> None:
    """Write curated NDJSON alignment index."""
```


```python
def write_manifests(
    manifest: dict,
    manifest_file: Path,
    run_id: str,
) -> tuple[Path, Path]:
    """Write latest and timestamped manifest files."""
```


```python
def main() -> int:
    """Run the batch Jubilee debate alignment workflow and return an exit code."""
```


---

# 9. Alignment Behaviour

## 9.1 Alignment backend

The required backend is:

```plain text
whisperx
```


Conceptual model loading:

```python
alignment_model, alignment_metadata = whisperx.load_align_model(
    language_code=language,
    device=device,
)
```


Conceptual alignment call:

```python
aligned = whisperx.align(
    segments,
    alignment_model,
    alignment_metadata,
    str(audio_path),
    device,
    return_char_alignments=return_char_alignments,
)
```


Exact API details may vary by WhisperX version. The implementation must normalise outputs into the project schema.

---

## 9.2 Input segment preparation

The programme should extract transcript segments from:

```plain text
transcription.segments
```


in the transcript JSON.

Each segment passed to WhisperX should include:

```json
{
  "start": 0.0,
  "end": 4.28,
  "text": "Example transcript segment."
}
```


Segment IDs should be preserved in project output if available.

Segments with blank text should be ignored or preserved with warning, depending on backend requirements.

If no usable segments are found, the item must fail with a clear error.

---

## 9.3 Aligned output structure

The aligned JSON should include:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "input_audio_path": "corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav",
  "input_transcript_json_path": "corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.json",
  "aligned_json_path": "corpus/04_jubilee_debates_alignment/jubilee_surrounded_001.aligned.json",
  "words_ndjson_path": "corpus/04_jubilee_debates_alignment/jubilee_surrounded_001.words.ndjson",
  "alignment_model": {
    "backend": "whisperx",
    "language": "en",
    "device": "cuda",
    "return_char_alignments": false,
    "interpolate_method": "nearest"
  },
  "alignment": {
    "segment_count": 950,
    "word_count": 14500,
    "segments": [
      {
        "id": 1,
        "start": 0.0,
        "end": 4.28,
        "text": "Example transcript segment.",
        "words": [
          {
            "word": "Example",
            "start": 0.12,
            "end": 0.54,
            "score": 0.91
          }
        ]
      }
    ]
  },
  "metadata": {},
  "run": {
    "alignment_run_id": "20260730T230000Z",
    "aligned_at_utc": "2026-07-30T23:30:00Z"
  },
  "status": "success",
  "error": null
}
```


---

## 9.4 Word NDJSON structure

Each line in `<corpus_id>.words.ndjson` should contain one word/token record.

Recommended fields:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "segment_id": 1,
  "word_index": 1,
  "word": "Example",
  "start": 0.12,
  "end": 0.54,
  "score": 0.91,
  "alignment_status": "aligned"
}
```


If WhisperX returns a word without timestamps, the record should still be included when possible:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "segment_id": 1,
  "word_index": 12,
  "word": "unassigned",
  "start": null,
  "end": null,
  "score": null,
  "alignment_status": "unaligned"
}
```


---

## 9.5 Existing files

If both:

```plain text
<output_dir>/<corpus_id>.aligned.json
<output_dir>/<corpus_id>.words.ndjson
```


already exist and `--reprocess` is not enabled:

- do not run alignment;
- mark item as `skipped_existing`;
- log the skip;
- include item in manifest;
- include item in alignment index.

If only one output exists:

- treat item as incomplete;
- align again;
- overwrite incomplete outputs.

---

## 9.6 Missing inputs

If audio is missing:

- mark `missing_input`;
- log missing audio;
- continue.

If transcript JSON is missing:

- mark `missing_input`;
- log missing transcript;
- continue.

Missing inputs cause exit code `1`.

---

## 9.7 Alignment failures

If WhisperX alignment raises an exception or returns invalid output:

- capture the error;
- mark item as `failed`;
- log the failure;
- continue to next item;
- exit with code `1` after the run.

---

# 10. Alignment Index Design

The programme must write:

```plain text
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
```


Each line should contain one JSON object per processed, skipped, missing, failed, or invalid eligible item.

Recommended fields:

| Field | Description |
|---|---|
| `corpus_id` | Stable debate ID |
| `debate_format` | Debate format |
| `sample_group` | Sample group |
| `sample_order` | Sample order |
| `title_selected` | Selected title |
| `title_extracted` | Extracted title |
| `youtube_id` | YouTube ID |
| `youtube_url` | YouTube URL |
| `duration_seconds` | Duration |
| `duration_string` | Human-readable duration |
| `chapters` | Chapter metadata |
| `audio_file` | Source WAV path |
| `transcript_json_file` | Source transcript JSON |
| `aligned_json_file` | Aligned JSON path |
| `words_ndjson_file` | Word NDJSON path |
| `alignment_status` | Status |
| `alignment_run_id` | Run ID |
| `aligned_at_utc` | Timestamp |
| `alignment_language` | Alignment language |
| `alignment_backend` | Backend |
| `alignment_device` | Device |
| `word_count` | Word count |
| `aligned_word_count` | Words with timestamps |
| `unaligned_word_count` | Words without timestamps |
| `segment_count` | Segment count |
| `transcription_status` | Previous stage status |
| `transcription_run_id` | Previous stage run ID |
| `selected_by` | Selector |
| `selection_source` | Selection source |
| `notes` | Notes |
| `error` | Error message |

---

# 11. JSON Manifest Design

## 11.1 Manifest structure

The manifest must use this general structure:

```json
{
  "run_metadata": {
    "run_id": "20260730T230000Z",
    "tool_name": "align_jubilee_debates_whisperx.py",
    "tool_version": "v1",
    "start_time": "2026-07-30T23:00:00Z",
    "end_time": "2026-07-30T23:50:00Z",
    "test_mode": true,
    "test_limit": 1,
    "reprocess": false,
    "workers": 1,
    "transcript_index_path": "corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson",
    "audio_dir": "corpus/02_jubilee_debates_audio",
    "transcript_dir": "corpus/03_jubilee_debates_transcripts",
    "output_dir": "corpus/04_jubilee_debates_alignment",
    "alignment_index_file": "corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson",
    "log_file": "corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx.log",
    "manifest_file": "corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx_manifest.json",
    "config": {
      "backend": "whisperx",
      "device": "cuda",
      "language": "en",
      "batch_size": 8,
      "return_char_alignments": false,
      "interpolate_method": "nearest",
      "timeout_seconds": 14400,
      "max_retries": 1,
      "retry_delay_seconds": 5,
      "start_corpus_id": null
    },
    "environment": {
      "python_version": "3.11.x",
      "cuda_available": true,
      "cuda_device_name": "NVIDIA A10G",
      "torch_version": "unknown",
      "torch_cuda_version": "unknown",
      "whisperx_version": "unknown"
    },
    "summary": {
      "transcript_index_records": 5,
      "eligible_transcript_records": 5,
      "ignored_transcript_records": 0,
      "invalid_metadata": 0,
      "planned": 1,
      "attempted": 1,
      "succeeded": 1,
      "failed": 0,
      "missing_input": 0,
      "skipped_existing": 0
    },
    "interrupted": false
  },
  "items": [
    {
      "corpus_id": "jubilee_surrounded_001",
      "input_audio_path": "corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav",
      "input_transcript_json_path": "corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.json",
      "aligned_json_path": "corpus/04_jubilee_debates_alignment/jubilee_surrounded_001.aligned.json",
      "words_ndjson_path": "corpus/04_jubilee_debates_alignment/jubilee_surrounded_001.words.ndjson",
      "status": "success",
      "error": null,
      "retries": 0,
      "duration_seconds": 300.5,
      "start_time": "2026-07-30T23:01:00Z",
      "end_time": "2026-07-30T23:06:00Z",
      "segment_count": 950,
      "word_count": 14500,
      "aligned_word_count": 14200,
      "unaligned_word_count": 300,
      "metadata": {
        "title_selected": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)",
        "youtube_id": "WV29R1M25n8",
        "duration_seconds": 5427
      }
    }
  ],
  "invalid_records": [],
  "ignored_records": []
}
```


---

## 11.2 Required item statuses

| Status | Meaning |
|---|---|
| `success` | Alignment completed successfully |
| `failed` | Alignment was attempted but failed |
| `skipped_existing` | Alignment outputs already existed and `--reprocess` was not enabled |
| `missing_input` | Source audio or transcript JSON was missing |
| `failed_metadata` | Eligible transcript-index row was invalid |
| `ignored_transcript_unavailable` | Record ignored because transcription was not available |
| `interrupted` | Processing stopped due to keyboard interruption |

---

# 12. Logging Specification

The programme must write an append-only UTF-8 log file.

Default:

```plain text
corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx.log
```


Log format:

```plain text
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```


Required log events:

- startup;
- run ID;
- parsed configuration;
- transcript index path;
- audio directory;
- transcript directory;
- output directory;
- test mode status;
- test limit;
- reprocess setting;
- start corpus ID;
- backend;
- device;
- language;
- batch size;
- return character alignments setting;
- interpolate method;
- dependency availability;
- CUDA availability;
- alignment model loading start;
- alignment model loading success;
- alignment model loading failure;
- number of transcript index records read;
- number of eligible records;
- number of ignored records;
- number of invalid metadata rows;
- number of planned alignments;
- each skipped existing alignment;
- each missing input;
- each alignment attempt;
- each retry;
- each success;
- each failure;
- word count summary per item;
- alignment index write path;
- manifest write paths;
- final summary;
- configuration errors;
- keyboard interruptions.

---

# 13. Error Handling and Resiliency

## 13.1 Configuration errors

Configuration errors must stop the programme before alignment begins.

Examples:

- transcript index missing;
- transcript index unreadable;
- invalid JSON line in transcript index;
- no eligible transcript records;
- audio directory missing;
- transcript directory missing;
- invalid command-line arguments;
- start corpus ID not found;
- `whisperx` unavailable;
- CUDA requested but unavailable;
- alignment model cannot be loaded.

Exit code:

```plain text
2
```


---

## 13.2 Per-item errors

Per-item errors must not stop the full batch.

Examples:

- source audio missing;
- transcript JSON missing;
- transcript JSON malformed;
- no usable segments;
- alignment backend exception;
- CUDA out of memory;
- output file cannot be written.

For each per-item error:

- mark the item as one of:
  - `missing_input`;
  - `failed_metadata`;
  - `failed`;
- capture short error;
- log error;
- continue to next item.

Exit code:

```plain text
1
```


if any per-item error occurred.

---

## 13.3 Keyboard interruption

If interrupted with `Ctrl+C`, the programme must:

- stop processing;
- mark run as interrupted;
- write partial manifest where possible;
- log interruption;
- exit with code:

```plain text
130
```


---

## 13.4 Exit codes

| Exit code | Meaning |
|---:|---|
| `0` | Completed with no failed attempted alignments, no missing inputs, and no invalid eligible metadata rows |
| `1` | Completed, but one or more alignments failed, source inputs were missing, or eligible metadata rows were invalid |
| `2` | Configuration or validation error |
| `130` | Interrupted by user |

Skipped existing files are not failures.

Ignored records where transcription was not available are not failures.

---

# 14. Docstrings and In-code Documentation

## 14.1 Module-level docstring

At the top of `align_jubilee_debates_whisperx.py`, include a module-level docstring explaining:

- purpose of programme;
- expected input transcript index;
- source audio input directory;
- transcript JSON input directory;
- alignment output directory;
- use of WhisperX forced alignment;
- EC2/GPU recommendation;
- default test mode;
- resumability behaviour;
- start-corpus-ID support;
- alignment-only scope;
- example commands.

Suggested module docstring:

```python
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
- `setup_logging`
- `validate_args`
- `check_alignment_dependencies`
- `check_cuda_available`
- `load_transcript_index`
- `resolve_audio_path`
- `resolve_transcript_json_path`
- `plan_alignments`
- `load_transcript_json`
- `extract_segments_for_alignment`
- `load_alignment_model`
- `align_one_debate`
- `normalise_alignment_result`
- `write_alignment_outputs`
- `write_alignment_index`
- `write_manifests`
- `main`

---

# 15. Suggested Constants

```python
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
```


---

# 16. Development Notes

## 16.1 Initial implementation scope

The first implementation should prioritise:

- correct sequential execution;
- robust transcript index reading;
- eligibility filtering by `transcription_status`;
- robust input audio resolution;
- robust transcript JSON resolution;
- stable extraction of transcript segments;
- WhisperX alignment with English model;
- stable aligned JSON output;
- stable word NDJSON output;
- reliable alignment index output;
- reliable logging;
- robust manifest writing;
- clear environment validation;
- safe resumability;
- `--start-corpus-id` support;
- conservative GPU settings.

Parallel processing should not be implemented initially.

## 16.2 Downstream pipeline note

This programme only aligns transcript text to audio.

Downstream stages include:

- pyannote speaker diarisation;
- assigning diarised speaker labels to aligned words/segments;
- quality-control reporting;
- possible manual speaker identity curation.

---

# 17. Acceptance Criteria

The programme is considered complete when:

1. Running from inside `cl_st1_ph0_carol/` works:

```shell script
python align_jubilee_debates_whisperx.py
```


2. Running from project root works:

```shell script
python cl_st1_ph0_carol/align_jubilee_debates_whisperx.py
```


3. Default paths are resolved relative to the programme directory.

4. It reads:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
```


5. It processes only records where transcript outputs are available.

6. It uses source audio from `audio_file` when present and usable.

7. It falls back to:

```plain text
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```


8. It uses transcript JSON from `transcript_json_file` when present and usable.

9. It falls back to:

```plain text
corpus/03_jubilee_debates_transcripts/<corpus_id>.json
```


10. It creates the output directory if needed:

```plain text
corpus/04_jubilee_debates_alignment/
```


11. Each successful alignment writes:

```plain text
corpus/04_jubilee_debates_alignment/<corpus_id>.aligned.json
    corpus/04_jubilee_debates_alignment/<corpus_id>.words.ndjson
```


12. The default backend is:

```plain text
whisperx
```


13. The default device is:

```plain text
cuda
```


14. The default language is:

```plain text
en
```


15. Existing complete alignment outputs are skipped unless `--reprocess` is used.

16. If only one alignment output exists, the item is treated as incomplete and planned for alignment.

17. Failed alignments do not stop the full batch.

18. Missing input audio files are marked as `missing_input`.

19. Missing transcript JSON files are marked as `missing_input`.

20. Invalid eligible metadata rows are marked as `failed_metadata`.

21. Transcript JSON files without usable segments cause item failure, not full-run failure.

22. The programme supports:

```shell script
--start-corpus-id CORPUS_ID
```


23. If `--start-corpus-id` is not found among eligible records, the programme exits with configuration error.

24. A log file is written at:

```plain text
corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx.log
```


25. A latest manifest is written at:

```plain text
corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx_manifest.json
```


26. A timestamped per-run manifest is also written.

27. An alignment index is written at:

```plain text
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
```


28. The alignment index is suitable as input to:

```plain text
assign_speakers_jubilee_debates.py
```


29. The programme exits with:
    - `0` for clean completion;
    - `1` for item-level failures, missing inputs, or invalid eligible metadata;
    - `2` for configuration errors;
    - `130` for keyboard interruption.

30. The programme does **not** transcribe, diarise, assign speakers, or produce QC reports.

---

# 18. Short README Section

## Align Jubilee debate transcripts with WhisperX

The `align_jubilee_debates_whisperx.py` programme aligns previously generated Jubilee debate transcripts to their source WAV audio using WhisperX forced alignment.

It reads the transcript index:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
```


Only records whose `transcription_status` indicates available transcript outputs are processed.

Source audio files are resolved from the `audio_file` field when available. Otherwise, audio is read from:

```plain text
corpus/02_jubilee_debates_audio/
```


Each fallback source audio file is expected as:

```plain text
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```


Transcript JSON files are resolved from the `transcript_json_file` field when available. Otherwise, transcript JSON is read from:

```plain text
corpus/03_jubilee_debates_transcripts/
```


Each fallback transcript file is expected as:

```plain text
corpus/03_jubilee_debates_transcripts/<corpus_id>.json
```


Alignment outputs are written to:

```plain text
corpus/04_jubilee_debates_alignment/
```


Each successful alignment writes:

```plain text
corpus/04_jubilee_debates_alignment/<corpus_id>.aligned.json
corpus/04_jubilee_debates_alignment/<corpus_id>.words.ndjson
```


Default test run:

```shell script
python align_jubilee_debates_whisperx.py
```


This processes one planned debate by default.

Full run:

```shell script
python align_jubilee_debates_whisperx.py --no-test-mode
```


Resume from a specific debate:

```shell script
python align_jubilee_debates_whisperx.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```


Force re-alignment:

```shell script
python align_jubilee_debates_whisperx.py \
  --no-test-mode \
  --reprocess
```


The programme writes:

```plain text
corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx.log
corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx_manifest.json
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
```


A timestamped per-run manifest is also created.

This stage performs alignment only. Transcription, diarisation, speaker assignment, and QC are handled by separate pipeline stages.