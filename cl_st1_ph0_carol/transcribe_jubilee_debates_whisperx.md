# `transcribe_jubilee_debates_whisperx.py` — Programme Specification for Development

## 1. High-level Functionality Specification

### Programme Summary

`transcribe_jubilee_debates_whisperx.py` is a batch-processing programme that transcribes full-length Jubilee debate audio files using Whisper/WhisperX-compatible transcription tooling.

The programme is part of:

```plain text
Corpus Linguistics — Study 1 — Carol, Phase 0 — Speaker Diarisation Test
```


It is the first GPU-heavy speech-processing stage after audio extraction.

The programme reads the curated audio index produced by the audio extraction stage:

```plain text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


Each record in this index represents one eligible Jubilee debate audio file. The programme must process records where the extracted audio is available, indicated by:

```plain text
audio_extraction_status = success
```


or:

```plain text
audio_extraction_status = skipped_existing
```


For each eligible record, the programme uses:

- `corpus_id` to identify the debate;
- `audio_file`, when present and valid, to locate the source WAV file;
- `<input_dir>/<corpus_id>.wav` as a fallback source audio path;
- `corpus_id` again to name transcript outputs.

The source audio files are expected in:

```plain text
corpus/02_jubilee_debates_audio/
```


Each source audio file is expected to be a Whisper-ready WAV file:

```plain text
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```


Transcript outputs must be written to:

```plain text
corpus/03_jubilee_debates_transcripts/
```


For each successfully transcribed debate, the programme must write:

```plain text
corpus/03_jubilee_debates_transcripts/<corpus_id>.txt
corpus/03_jubilee_debates_transcripts/<corpus_id>.json
```


The `.txt` file contains a clean plain-text transcript intended for corpus analysis and human inspection.

The `.json` file contains detailed transcription metadata, including:

- source metadata;
- transcript text;
- segment-level timestamps;
- model configuration;
- runtime information;
- output paths;
- item status.

The intended transcription engine is:

```plain text
Whisper Large v3
```


The preferred implementation is:

```plain text
WhisperX transcription interface
```


using a backend compatible with:

```plain text
faster-whisper
```


This programme performs **transcription only**. It must not perform:

- WhisperX forced alignment;
- speaker diarisation;
- speaker assignment;
- quality-control reporting;
- speaker identity resolution.

Those operations belong to later stages:

| Stage | Programme |
|---:|---|
| 2 | `align_jubilee_debates_whisperx.py` |
| 3 | `diarise_jubilee_debates_pyannote.py` |
| 4 | `assign_speakers_jubilee_debates.py` |
| 5 | `qc_jubilee_debates_speaker_diarisation.py` |

---

## 2. Key Behaviours

The programme must implement the following behaviours:

- Read Jubilee debate audio metadata from an NDJSON audio index file.
- Process only records where `audio_extraction_status` indicates usable extracted audio.
- Extract the required field:
  - `corpus_id`.
- Locate source audio files using:
  - `audio_file`, when present and usable;
  - otherwise `<input_dir>/<corpus_id>.wav`.
- Write plain-text transcripts as:

```plain text
<output_dir>/<corpus_id>.txt
```


- Write detailed JSON transcripts as:

```plain text
<output_dir>/<corpus_id>.json
```


- Create the output directory if it does not already exist.
- Load the transcription model once per run, after planning.
- Use GPU acceleration by default.
- Use Python 3.11 in a dedicated EC2 speech-processing environment.
- Use English transcription by default:

```plain text
language = en
```


- Use test mode by default, limiting processing to 1 eligible debate initially.
- Skip already-transcribed debates by default, supporting safe re-runs.
- Allow reprocessing with an explicit command-line option.
- Support starting from a specific `corpus_id`.
- Continue processing remaining debates if one transcription fails.
- Record progress and errors in an append-only log file.
- Produce a JSON manifest with run-level metadata and item-level results.
- Write both:
  - a timestamped per-run manifest;
  - a latest manifest overwritten on each run.
- Write a curated transcript index for downstream alignment.
- Exit with status code `0` only when all attempted transcriptions succeed or are skipped, and there are no missing inputs or invalid eligible metadata rows.
- Exit with non-zero status code if one or more attempted transcriptions fail, if source audio is missing, if eligible metadata is invalid, or if there is a configuration/validation error.

---

## 3. Path Resolution Policy

The programme must resolve its default paths relative to the directory where `transcribe_jubilee_debates_whisperx.py` is located, not relative to the current working directory.

If the script is located at:

```plain text
cl_st1_ph0_carol/transcribe_jubilee_debates_whisperx.py
```


then the default audio index path:

```plain text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


must resolve to:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


This ensures that the programme works when executed from:

```plain text
cl_st1_carol/
```


or:

```plain text
cl_st1_carol/cl_st1_ph0_carol/
```


or from another working directory.

### Internal path base

The implementation should define:

```python
SCRIPT_DIR = Path(__file__).resolve().parent
```


Relative default paths and relative command-line paths should be resolved against `SCRIPT_DIR`.

### Absolute paths

If the user supplies an absolute path for arguments such as:

- `--audio-index`
- `--input-dir`
- `--output-dir`
- `--log-file`
- `--manifest-file`
- `--transcript-index-file`

the programme must preserve that absolute path.

---

## 4. Input / Output Specification

## 4.1 Input

### Input audio index file

Default path:

```plain text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


The file is expected to be in **NDJSON** format: one JSON object per line.

This file is produced by the preceding audio extraction stage.

### Required fields

Each valid eligible record must contain:

| Field | Type | Description |
|---|---:|---|
| `corpus_id` | string | Stable internal debate identifier, e.g. `jubilee_surrounded_001` |
| `audio_extraction_status` | string | Status from the audio extraction stage |

The source audio path is resolved using:

| Field | Requirement | Description |
|---|---|---|
| `audio_file` | optional | Preferred local path to extracted WAV file when present and usable |

If `audio_file` is absent, blank, or unusable, the programme must fall back to:

```plain text
<input_dir>/<corpus_id>.wav
```


### Eligible audio extraction statuses

The programme must process only records where:

```plain text
audio_extraction_status = success
```


or:

```plain text
audio_extraction_status = skipped_existing
```


Records with other statuses must be ignored, not treated as errors.

Ineligible statuses include:

```plain text
failed
missing_input
failed_metadata
ignored_not_downloaded
interrupted
null
""
missing value
```


### Recommended metadata fields to preserve

The programme should preserve the following fields in transcript JSON, transcript index, and manifest items when present:

| Field | Description |
|---|---|
| `corpus_id` | Internal stable corpus ID |
| `debate_format` | Debate format, e.g. `Surrounded` |
| `sample_group` | Sample group |
| `sample_order` | Sample order |
| `title` | Selected title, if present |
| `title_selected` | Title from selected sample |
| `title_extracted` | Extracted YouTube title |
| `youtube_id` | YouTube video ID |
| `youtube_url` | Original YouTube URL |
| `webpage_url` | Canonical YouTube URL |
| `duration_seconds` | Source video/audio duration |
| `duration_string` | Human-readable duration |
| `chapters` | Chapter metadata |
| `source_video_file` | Source video path used in audio extraction |
| `audio_file` | Extracted WAV path |
| `audio_format` | Audio format |
| `audio_codec` | Audio codec |
| `audio_channels` | Audio channel count |
| `audio_sample_rate` | Audio sample rate |
| `audio_sample_format` | Audio sample format |
| `audio_file_size_bytes` | Audio file size |
| `audio_extraction_status` | Previous stage status |
| `audio_extraction_run_id` | Previous stage run ID |
| `audio_extracted_at_utc` | Previous stage timestamp |
| `ffmpeg_version` | ffmpeg version used in audio extraction |
| `download_run_id` | Download stage run ID |
| `downloaded_at_utc` | Download stage timestamp |
| `video_download_status` | Video download status |
| `metadata_status` | Metadata status |
| `raw_metadata_file` | Raw `.info.json` file |
| `description_file` | Description file |
| `subtitles_files` | Subtitle files |
| `selected_by` | Selector |
| `selection_source` | Selection source |
| `notes` | Optional notes |

---

## 4.2 Input audio files

### Audio input directory

Default path:

```plain text
corpus/02_jubilee_debates_audio/
```


Each fallback source audio file is expected as:

```plain text
<input_dir>/<corpus_id>.wav
```


Examples:

```plain text
corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav
corpus/02_jubilee_debates_audio/jubilee_surrounded_002.wav
corpus/02_jubilee_debates_audio/jubilee_surrounded_003.wav
```


The audio extraction stage should have produced WAV files with:

| Property | Expected value |
|---|---:|
| Container | WAV |
| Channels | mono |
| Sample rate | 16000 Hz |
| Sample format | signed 16-bit PCM |

The transcription programme may rely on the audio extraction programme for audio compatibility. It does not need to re-encode audio.

---

## 4.3 Output

### Transcript output directory

Default path:

```plain text
corpus/03_jubilee_debates_transcripts/
```


The programme must create this directory if it does not already exist.

### Per-debate plain-text transcript

Each successful transcription must write:

```plain text
<output_dir>/<corpus_id>.txt
```


Example:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.txt
```


The `.txt` file should contain only the clean transcript text. Segment boundaries should not be represented in the default `.txt` output unless a future analysis step requires this.

Recommended formatting:

```plain text
This is the debate transcript text. It is joined into readable plain text.
```


### Per-debate JSON transcript

Each successful transcription must write:

```plain text
<output_dir>/<corpus_id>.json
```


Example:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.json
```


The `.json` file must include:

- corpus ID;
- input audio path;
- output text path;
- output JSON path;
- model/backend configuration;
- full transcript text;
- segment-level timestamps;
- detected language information, if available;
- copied source metadata;
- run metadata;
- item status.

### Log file

Default path:

```plain text
corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx.log
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
corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx_manifest.json
```


This file is overwritten at the end of each run.

#### Per-run manifest

A timestamped copy must also be written using the run ID.

Filename pattern:

```plain text
transcribe_jubilee_debates_whisperx_manifest_<run_id>.json
```


Example:

```plain text
corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx_manifest_20260730T220000Z.json
```


### Transcript index file

Default path:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
```


This curated transcript index is used by the alignment stage.

---

# 5. Command-line Interface

## 5.1 Default usage

The programme may be run from inside `cl_st1_ph0_carol/`:

```shell script
python transcribe_jubilee_debates_whisperx.py
```


or from the project root:

```shell script
python cl_st1_ph0_carol/transcribe_jubilee_debates_whisperx.py
```


Both commands should resolve default paths correctly.

Default behaviour:

- audio index:

```plain text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


- input directory:

```plain text
corpus/02_jubilee_debates_audio/
```


- output directory:

```plain text
corpus/03_jubilee_debates_transcripts/
```


- model name:

```plain text
large-v3
```


- backend:

```plain text
whisperx
```


- device:

```plain text
cuda
```


- compute type:

```plain text
float16
```


- language:

```plain text
en
```


- task:

```plain text
transcribe
```


- batch size:

```plain text
8
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


- existing transcript `.txt` and `.json` files are skipped;
- one worker / sequential processing.

### Note on default test limit

The previous commercial-transcription project used a default test limit of 5. This project uses long-form debate audio, so the default test limit should be:

```plain text
1
```


A single debate may be around 1.5–1.9 hours long. A one-item default test is safer for EC2 cost, GPU memory, and debugging.

---

## 5.2 Required arguments

There are no required command-line arguments if all default paths and settings are used.

However, all important paths and processing controls must be configurable.

---

## 5.3 Optional arguments

### Audio index

```shell script
--audio-index PATH
```


Default:

```plain text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


Description:

Path to the curated NDJSON audio index from the audio extraction stage.

Relative paths are resolved relative to the programme directory.

---

### Input directory

```shell script
--input-dir PATH
```


Default:

```plain text
corpus/02_jubilee_debates_audio/
```


Description:

Directory containing source WAV files.

Used as fallback when the `audio_file` field is absent or unusable.

Relative paths are resolved relative to the programme directory.

---

### Output directory

```shell script
--output-dir PATH
```


Default:

```plain text
corpus/03_jubilee_debates_transcripts/
```


Description:

Directory where transcript `.txt`, transcript `.json`, logs, manifests, and transcript index files are written.

Relative paths are resolved relative to the programme directory.

---

### Model name

```shell script
--model-name MODEL
```


Default:

```plain text
large-v3
```


Description:

Whisper model name to use for transcription.

Recommended final value:

```plain text
large-v3
```


Possible exploratory value:

```plain text
large-v3-turbo
```


The final corpus should use one model consistently.

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
faster-whisper
```


Description:

Backend label recorded in outputs and used to select transcription implementation.

The first implementation should use WhisperX transcription functionality. If using `faster-whisper` directly internally, the manifest should record this clearly.

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


Description:

Device on which to run transcription.

For EC2 GPU processing, use:

```plain text
cuda
```


If `--device cuda` is requested and CUDA is unavailable, the programme must fail fast with configuration error instead of silently falling back to CPU.

---

### Compute type

```shell script
--compute-type COMPUTE_TYPE
```


Default:

```plain text
float16
```


Recommended for GPU:

```plain text
float16
```


Possible alternatives:

```plain text
int8_float16
int8
float32
```


For CPU operation, `float32` or `int8` may be needed.

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

Language code passed to Whisper.

For this project, English should be used explicitly to reduce language-detection variability.

If set to:

```plain text
auto
```


the programme may allow language detection by passing no fixed language to the backend.

---

### Task

```shell script
--task TASK
```


Default:

```plain text
transcribe
```


Allowed values:

```plain text
transcribe
translate
```


For this project, use:

```plain text
transcribe
```


---

### Batch size

```shell script
--batch-size N
```


Default:

```plain text
8
```


Description:

Batch size for WhisperX transcription.

Must be a positive integer.

For `g5.xlarge`, use conservative values initially:

```plain text
8
```


or:

```plain text
16
```


If CUDA out-of-memory occurs, reduce batch size.

---

### VAD filter

```shell script
--vad-filter
--no-vad-filter
```


Default:

```plain text
--vad-filter
```


Description:

Enable or disable VAD filtering if supported by the backend.

Initial recommendation:

```plain text
--vad-filter
```


However, if the transcript appears to omit quick interjections, interruptions, or short turns, test:

```shell script
--no-vad-filter
```


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


Description:

When test mode is enabled, the programme processes only a limited number of planned transcriptions.

---

### Test limit

```shell script
--test-limit N
```


Default:

```plain text
1
```


Description:

Maximum number of debates to attempt when test mode is enabled.

Must be a positive integer.

Example:

```shell script
python transcribe_jubilee_debates_whisperx.py --test-limit 1
```


---

### Reprocess existing transcripts

```shell script
--reprocess
```


Default:

```plain text
False
```


Description:

When omitted, the programme skips any debate whose output `.txt` and `.json` transcript files both already exist.

When provided, the programme transcribes again and overwrites existing transcript files.

---

### Start corpus ID

```shell script
--start-corpus-id CORPUS_ID
```


Default:

```plain text
None
```


Description:

Optional `corpus_id` from which to start planning transcription.

When provided:

- preserve metadata order;
- ignore eligible debates before the specified `corpus_id`;
- include the specified debate;
- include all following eligible debates;
- apply existing-output skip logic after this filter;
- apply test limit after this filter and skip logic.

If the requested `corpus_id` is not found among eligible records, fail fast with configuration error.

Example:

```shell script
python transcribe_jubilee_debates_whisperx.py \
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
corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx.log
```


---

### Manifest file

```shell script
--manifest-file PATH
```


Default:

```plain text
corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx_manifest.json
```


---

### Transcript index file

```shell script
--transcript-index-file PATH
```


Default:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
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


Description:

Number of worker processes.

For the first implementation:

```plain text
--workers 1
```


is required.

Parallel transcription should not be implemented initially because long-form audio plus large GPU models can easily exceed VRAM.

---

### Timeout

```shell script
--timeout SECONDS
```


Default suggestion:

```plain text
14400
```


Description:

Maximum allowed time for a single debate transcription, in seconds.

A default of 4 hours is reasonable because each debate may be nearly 2 hours long.

Implementation note:

Since WhisperX/faster-whisper inference runs inside the Python process, strict per-item timeout enforcement is difficult unless transcription is run in subprocesses. The first implementation may record the timeout setting in the manifest without enforcing hard termination.

If strict timeout enforcement is required later, run each item in a subprocess.

---

### Maximum retries

```shell script
--max-retries N
```


Default:

```plain text
1
```


Must be zero or a positive integer.

---

### Retry delay

```shell script
--retry-delay SECONDS
```


Default:

```plain text
5
```


Must be zero or a positive integer.

---

## 5.4 Example commands

### Default one-debate test run

```shell script
python transcribe_jubilee_debates_whisperx.py
```


### Test run with explicit one-item limit

```shell script
python transcribe_jubilee_debates_whisperx.py --test-limit 1
```


### Test run from a specific corpus ID

```shell script
python transcribe_jubilee_debates_whisperx.py \
  --test-limit 1 \
  --start-corpus-id jubilee_surrounded_003
```


### Full production run on EC2 GPU

```shell script
python transcribe_jubilee_debates_whisperx.py --no-test-mode
```


### Full production run from a specific corpus ID

```shell script
python transcribe_jubilee_debates_whisperx.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```


### Full production run with explicit paths

```shell script
python transcribe_jubilee_debates_whisperx.py \
  --audio-index corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson \
  --input-dir corpus/02_jubilee_debates_audio \
  --output-dir corpus/03_jubilee_debates_transcripts \
  --model-name large-v3 \
  --device cuda \
  --compute-type float16 \
  --language en \
  --batch-size 8 \
  --no-test-mode
```


### Re-transcribe even if transcript outputs already exist

```shell script
python transcribe_jubilee_debates_whisperx.py \
  --no-test-mode \
  --reprocess
```


### Run with smaller batch size if GPU memory is tight

```shell script
python transcribe_jubilee_debates_whisperx.py \
  --no-test-mode \
  --batch-size 4
```


### EC2 run inside `tmux`

```shell script
tmux new -s jubilee_transcribe
conda activate whisperx_pyannote
cd ~/cl_st1_carol/cl_st1_ph0_carol
python transcribe_jubilee_debates_whisperx.py --no-test-mode
```


Detach:

```plain text
Ctrl+B
D
```


Reattach:

```shell script
tmux attach -t jubilee_transcribe
```


---

# 6. Argument Validation

The programme must fail fast with a clear message if:

- the audio index file does not exist;
- the audio index path is not a file;
- the audio index file is unreadable;
- the audio index contains invalid JSON lines;
- no eligible audio records are found;
- the input audio directory does not exist;
- the input audio directory is not a directory;
- the output directory cannot be created;
- `--model-name` is missing or blank;
- `--backend` is not supported;
- `--device` is missing or blank;
- `--compute-type` is missing or blank;
- `--language` is missing or blank;
- `--task` is not one of:
  - `transcribe`;
  - `translate`;
- `--batch-size` is less than or equal to zero;
- `--test-limit` is less than or equal to zero;
- `--workers` is less than or equal to zero;
- `--workers` is not `1` in the current sequential implementation;
- `--timeout` is less than or equal to zero;
- `--max-retries` is negative;
- `--retry-delay` is negative;
- `--start-corpus-id` is provided but empty;
- `--start-corpus-id` is provided but not found among eligible audio records;
- the required Python transcription package is not installed;
- `--device cuda` is requested but CUDA/GPU transcription is unavailable;
- the transcription model cannot be loaded.

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


## 7.2 Recommended environment setup

Use a dedicated environment:

```shell script
conda create -n whisperx_pyannote python=3.11 -y
conda activate whisperx_pyannote
```


Install dependencies:

```shell script
pip install --upgrade pip setuptools wheel
pip install torch torchaudio
pip install faster-whisper
pip install whisperx
pip install tqdm
```


Install CUDA runtime libraries into the active environment if needed:

```shell script
conda install -c nvidia cuda-toolkit=12 -y
conda install -c conda-forge cudnn -y
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
```


Make `LD_LIBRARY_PATH` persistent:

```shell script
mkdir -p "$CONDA_PREFIX/etc/conda/activate.d"
nano "$CONDA_PREFIX/etc/conda/activate.d/env_vars.sh"
```


Add:

```shell script
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
```


Reactivate:

```shell script
conda deactivate
conda activate whisperx_pyannote
```


## 7.3 GPU checks

Before transcription, verify:

```shell script
nvidia-smi
```


and:

```shell script
python -c "import torch; print(torch.cuda.is_available()); print(torch.version.cuda)"
```


If CUDA is unavailable and `--device cuda` was requested, the programme must fail fast.

## 7.4 Required Python packages

Required:

```plain text
whisperx
torch
torchaudio
```


Likely also required depending on implementation:

```plain text
faster-whisper
tqdm
```


Optional:

```plain text
huggingface_hub
```


A Hugging Face token is not necessarily required for Whisper transcription, but may improve model download reliability and may be needed elsewhere in the full pipeline.

---

# 8. Core Processing Architecture

## 8.1 High-level flow

The programme must follow this workflow:

1. **Startup**
   - Parse command-line arguments.
   - Resolve relative paths against the programme directory.
   - Validate simple argument values.
   - Generate UTC `run_id`.
   - Ensure output directory exists.
   - Configure append-only logging.
   - Check Python package availability.
   - Check CUDA availability if requested.

2. **Audio index loading**
   - Open the NDJSON audio index.
   - Read records line by line.
   - Parse each JSON object.
   - Count total records.
   - Select only records where `audio_extraction_status` is eligible.
   - Validate required fields:
     - `corpus_id`.
   - Preserve input order.
   - Record invalid eligible rows.
   - Record ignored rows where audio is not available.

3. **Planning**
   - Apply `--start-corpus-id`, if provided.
   - Resolve input audio path using `audio_file` or fallback input directory.
   - Compute output paths:
     - `<output_dir>/<corpus_id>.txt`;
     - `<output_dir>/<corpus_id>.json`.
   - Check whether source audio exists.
   - Mark missing source audio as `missing_input`.
   - If both output files exist and `--reprocess` is not enabled:
     - mark as `skipped_existing`.
   - If either output file is missing or `--reprocess` is enabled:
     - plan transcription.
   - Apply test-mode limit to planned transcriptions.

4. **Model loading**
   - Load the transcription model once after planning.
   - Use configured:
     - model name;
     - device;
     - compute type.
   - If loading fails, exit with configuration error.

5. **Execution**
   - For each planned item:
     - transcribe the WAV file;
     - collect segment text and timestamps;
     - join segment text into clean transcript;
     - write `.txt`;
     - write `.json`;
     - capture timing and errors;
     - retry according to `--max-retries`;
     - mark item as `success` or `failed`.

6. **Transcript index generation**
   - Combine source metadata and transcript metadata.
   - Write curated NDJSON transcript index for the alignment stage.

7. **Manifest writing**
   - Count summary statistics.
   - Write latest manifest.
   - Write timestamped manifest.

8. **Exit**
   - Exit `0` for clean completion.
   - Exit `1` for item-level failures, missing inputs, or invalid eligible metadata.
   - Exit `2` for configuration errors.
   - Exit `130` for keyboard interruption.

---

## 8.2 Separation of concerns

The implementation should be organised around these responsibilities.

### CLI parsing

```python
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the Jubilee debate transcription programme."""
```


### Path resolution

```python
def resolve_script_relative_path(path: Path) -> Path:
    """Resolve relative paths against the programme directory."""
```


### Logging

```python
def setup_logging(log_file: Path) -> logging.Logger:
    """Configure append-only UTF-8 file and console logging."""
```


### Validation

```python
def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and filesystem paths."""
```


### Package and device checks

```python
def check_transcription_dependencies() -> dict:
    """Check required Python package availability."""
```


```python
def check_cuda_available(device: str) -> dict:
    """Validate CUDA availability when requested."""
```


### Audio index loading

```python
def load_audio_index(
    audio_index_path: Path,
) -> tuple[list[dict], list[dict], int, int, list[dict]]:
    """Load and validate eligible audio records from the NDJSON audio index."""
```


Suggested return values:

```plain text
eligible_records, invalid_records, total_records, ignored_count, ignored_records
```


### Source audio resolution

```python
def resolve_source_audio_path(record: dict, input_dir: Path) -> Path:
    """Resolve source audio path using audio_file or fallback input directory."""
```


### Planning

```python
def plan_transcriptions(
    records: list[dict],
    input_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_corpus_id: str | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Create planned, skipped, and missing-input transcription records."""
```


Suggested return values:

```plain text
planned, skipped_existing, missing_input
```


### Model loading

```python
def load_transcription_model(
    model_name: str,
    device: str,
    compute_type: str,
    backend: str,
) -> Any:
    """Load the Whisper/WhisperX transcription model once for the batch."""
```


### Single-item transcription

```python
def transcribe_one_debate(
    model: Any,
    item: dict,
    model_config: dict,
    max_retries: int,
    retry_delay: int,
    logger: logging.Logger,
) -> dict:
    """Transcribe one Jubilee debate audio file and return a structured result."""
```


### Transcript text normalisation

```python
def normalise_transcript_text(segment_texts: list[str]) -> str:
    """Create clean plain text from ordered segment texts."""
```


### Output writing

```python
def write_transcript_outputs(
    text: str,
    transcript_json: dict,
    text_output_path: Path,
    json_output_path: Path,
) -> None:
    """Write text and JSON transcript outputs for one debate."""
```


### Transcript index writing

```python
def write_transcript_index(index_records: list[dict], transcript_index_file: Path) -> None:
    """Write curated NDJSON transcript index for downstream alignment."""
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
    """Run the batch Jubilee debate transcription workflow and return an exit code."""
```


---

# 9. Transcription Behaviour

## 9.1 Model backend

The recommended backend label is:

```plain text
whisperx
```


The programme may use WhisperX transcription facilities.

Conceptual model loading:

```python
model = whisperx.load_model(
    model_name,
    device=device,
    compute_type=compute_type,
    language=language,
)
```


If implementing with `faster-whisper` directly, this must be clearly recorded in the manifest.

Default values:

```plain text
model_name = large-v3
device = cuda
compute_type = float16
language = en
task = transcribe
batch_size = 8
```


---

## 9.2 Transcription call

For each eligible debate, conceptual transcription should be equivalent to:

```python
result = model.transcribe(
    str(input_path),
    batch_size=batch_size,
    language="en",
    task="transcribe",
)
```


Exact API details may vary by WhisperX version.

The programme must normalise the returned output into a stable project JSON structure.

---

## 9.3 Input filename

The input filename must be derived from `corpus_id`.

Given:

```plain text
corpus_id = jubilee_surrounded_001
```


The fallback input file must be:

```plain text
jubilee_surrounded_001.wav
```


The full default fallback input path must be:

```plain text
corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav
```


---

## 9.4 Output filenames

Output filenames must be derived from `corpus_id`.

Given:

```plain text
corpus_id = jubilee_surrounded_001
```


the output files must be:

```plain text
jubilee_surrounded_001.txt
jubilee_surrounded_001.json
```


Full default paths:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.txt
corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.json
```


---

## 9.5 Existing files

If both output files already exist and `--reprocess` is not enabled:

- do not call the model;
- mark the item as `skipped_existing`;
- log the skip;
- include the item in the manifest;
- include the item in the transcript index.

If only one output file exists:

- treat the item as incomplete;
- transcribe again;
- overwrite incomplete outputs.

If `--reprocess` is enabled:

- transcribe again;
- overwrite existing outputs.

---

## 9.6 Missing source audio

If the expected source audio does not exist:

- do not call the model;
- mark the item as `missing_input`;
- include expected input path in the manifest;
- include the item in the transcript index with missing-input status;
- log the missing input;
- continue processing other debates;
- exit with code `1` after the run.

---

## 9.7 Start corpus ID behaviour

If `--start-corpus-id CORPUS_ID` is provided:

- locate `CORPUS_ID` in eligible records;
- ignore eligible debates before it;
- include the specified debate;
- include all following debates;
- apply existing-file skip logic after the start filter;
- apply missing-input checking after the start filter;
- apply test-mode limiting after start filtering and skip logic;
- fail fast with configuration error if not found.

---

## 9.8 Transcript text normalisation

The plain-text transcript should be produced by:

1. Collecting all segment texts in order.
2. Stripping leading/trailing whitespace from each segment.
3. Removing empty segment texts.
4. Joining remaining segment texts with a single space.
5. Collapsing repeated whitespace.
6. Writing the result with a trailing newline.

The implementation should not perform heavy linguistic normalisation.

It must not:

- lowercase text;
- remove punctuation;
- remove fillers;
- remove names;
- remove discourse markers;
- stem or lemmatise words;
- remove stopwords;
- assign speakers.

Those operations belong to later analysis or curation stages.

---

## 9.9 Segment timestamps

The JSON transcript must preserve segment timestamps.

Each segment should include at least:

```json
{
  "id": 1,
  "start": 0.0,
  "end": 4.28,
  "text": "Example transcript segment."
}
```


If the backend provides additional useful fields, they may be included, but the first implementation should keep the JSON stable and simple.

---

## 9.10 Empty or no-speech transcriptions

If the transcription backend returns no segments or an empty transcript:

- the item may still be marked as `success` if backend execution completed normally;
- `.txt` should be written as an empty or near-empty UTF-8 file with trailing newline;
- `.json` should record:
  - empty text;
  - zero segments;
  - detected language information if available;
  - warning message.

This should be logged as warning:

```plain text
WARNING Empty transcript for jubilee_surrounded_001
```


Empty transcripts are not automatic programme failures.

---

## 9.11 Transcription failures

If transcription raises an exception, returns invalid output, or cannot write output files:

- capture the failure;
- mark the debate as `failed`;
- save a short error summary in the manifest;
- log the failure;
- continue with the next debate;
- exit with code `1` after the run.

---

## 9.12 Retries

Retry failed transcription attempts up to `--max-retries`.

Retry rules:

- retry only failed transcription attempts;
- do not retry missing-input records;
- do not retry failed-metadata records;
- log each retry;
- record retries used in the manifest;
- if all attempts fail, mark item as `failed`.

Default retry delay:

```plain text
5 seconds
```


---

# 10. Transcript JSON Design

Each debate JSON transcript should use this structure:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "input_audio_path": "corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav",
  "text_output_path": "corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.txt",
  "json_output_path": "corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.json",
  "model": {
    "backend": "whisperx",
    "model_name": "large-v3",
    "device": "cuda",
    "compute_type": "float16",
    "language": "en",
    "task": "transcribe",
    "batch_size": 8,
    "vad_filter": true
  },
  "transcription": {
    "text": "Full transcript text...",
    "detected_language": "en",
    "language_probability": 0.998,
    "duration_seconds": 5427,
    "segment_count": 1000,
    "segments": [
      {
        "id": 1,
        "start": 0.0,
        "end": 4.28,
        "text": "Example transcript segment."
      }
    ]
  },
  "metadata": {
    "debate_format": "Surrounded",
    "sample_group": "carol_initial_sample",
    "sample_order": 1,
    "title_selected": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)",
    "title_extracted": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk) | Surrounded",
    "youtube_id": "WV29R1M25n8",
    "youtube_url": "https://www.youtube.com/watch?v=WV29R1M25n8",
    "duration_seconds": 5427,
    "duration_string": "1:30:27",
    "chapters": []
  },
  "run": {
    "transcription_run_id": "20260730T220000Z",
    "transcribed_at_utc": "2026-07-30T22:30:00Z"
  },
  "status": "success",
  "error": null
}
```


---

# 11. Transcript Index Design

The programme must write:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
```


Each line should contain one JSON object per eligible processed, skipped, missing, or failed item.

Recommended fields:

| Field | Description |
|---|---|
| `corpus_id` | Stable internal debate ID |
| `debate_format` | Debate format |
| `sample_group` | Sample group |
| `sample_order` | Sample order |
| `title_selected` | Selected title |
| `title_extracted` | Extracted title |
| `youtube_id` | YouTube ID |
| `youtube_url` | YouTube URL |
| `duration_seconds` | Audio/video duration |
| `duration_string` | Human-readable duration |
| `chapters` | Chapter metadata |
| `audio_file` | Source WAV path |
| `transcript_text_file` | Plain-text transcript path |
| `transcript_json_file` | JSON transcript path |
| `transcription_status` | `success`, `failed`, etc. |
| `transcription_run_id` | Current run ID |
| `transcribed_at_utc` | Transcription timestamp |
| `transcript_characters` | Character count |
| `segment_count` | Number of transcript segments |
| `detected_language` | Detected language if available |
| `language_probability` | Language probability if available |
| `model_name` | Model name |
| `backend` | Backend |
| `device` | Device |
| `compute_type` | Compute type |
| `batch_size` | Batch size |
| `audio_extraction_status` | Previous stage status |
| `audio_extraction_run_id` | Previous stage run ID |
| `selected_by` | Selector |
| `selection_source` | Selection source |
| `notes` | Notes |
| `error` | Error if any |

---

# 12. JSON Manifest Design

## 12.1 Manifest structure

The manifest must use this general structure:

```json
{
  "run_metadata": {
    "run_id": "20260730T220000Z",
    "tool_name": "transcribe_jubilee_debates_whisperx.py",
    "tool_version": "v1",
    "start_time": "2026-07-30T22:00:00Z",
    "end_time": "2026-07-30T23:10:00Z",
    "test_mode": true,
    "test_limit": 1,
    "reprocess": false,
    "workers": 1,
    "audio_index_path": "corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson",
    "input_dir": "corpus/02_jubilee_debates_audio",
    "output_dir": "corpus/03_jubilee_debates_transcripts",
    "transcript_index_file": "corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson",
    "log_file": "corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx.log",
    "manifest_file": "corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx_manifest.json",
    "config": {
      "backend": "whisperx",
      "model_name": "large-v3",
      "device": "cuda",
      "compute_type": "float16",
      "language": "en",
      "task": "transcribe",
      "batch_size": 8,
      "vad_filter": true,
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
      "audio_index_records": 5,
      "eligible_audio_records": 5,
      "ignored_audio_records": 0,
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
      "text_output_path": "corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.txt",
      "json_output_path": "corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.json",
      "status": "success",
      "error": null,
      "retries": 0,
      "duration_seconds": 420.5,
      "start_time": "2026-07-30T22:01:00Z",
      "end_time": "2026-07-30T22:08:00Z",
      "transcript_characters": 123456,
      "segment_count": 950,
      "detected_language": "en",
      "language_probability": 0.998,
      "metadata": {
        "title_selected": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)",
        "title_extracted": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk) | Surrounded",
        "youtube_id": "WV29R1M25n8",
        "duration_seconds": 5427,
        "duration_string": "1:30:27"
      }
    }
  ],
  "invalid_records": [],
  "ignored_records": []
}
```


---

## 12.2 Required item statuses

The following statuses must be supported:

| Status | Meaning |
|---|---|
| `success` | Debate audio was transcribed successfully |
| `failed` | Transcription was attempted but failed |
| `skipped_existing` | Transcript files already existed and `--reprocess` was not enabled |
| `missing_input` | Source audio file was missing |
| `failed_metadata` | Eligible audio-index record was invalid |
| `ignored_audio_unavailable` | Record ignored because extracted audio was not available |
| `interrupted` | Processing stopped due to keyboard interruption |

---

## 12.3 Error field

The `error` field must be:

- `null` when no error occurred;
- a short string when an error occurred.

Example:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "input_audio_path": "corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav",
  "text_output_path": "corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.txt",
  "json_output_path": "corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.json",
  "status": "failed",
  "error": "CUDA out of memory while transcribing audio",
  "retries": 1
}
```


---

# 13. Logging Specification

The programme must write an append-only UTF-8 log file.

Default:

```plain text
corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx.log
```


Each line should follow:

```plain text
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```


Required log events:

- startup;
- run ID;
- parsed configuration;
- resolved audio index path;
- resolved input directory;
- resolved output directory;
- test mode status;
- test limit;
- reprocess setting;
- start corpus ID, if provided;
- backend;
- model name;
- device;
- compute type;
- language;
- task;
- batch size;
- VAD setting;
- dependency availability;
- CUDA availability;
- model loading start;
- model loading success;
- model loading failure;
- number of audio index records read;
- number of eligible audio records;
- number of ignored audio records;
- number of invalid metadata records;
- number of planned transcriptions;
- each skipped existing transcript;
- each missing source audio file;
- each transcription attempt;
- each retry attempt;
- each successful transcription;
- each failed transcription;
- empty transcript warnings;
- transcript index write path;
- manifest write paths;
- final summary;
- validation/configuration errors;
- keyboard interrupts.

Example log lines:

```plain text
[2026-07-30 22:00:00] INFO  Starting transcribe_jubilee_debates_whisperx.py run_id=20260730T220000Z
[2026-07-30 22:00:00] INFO  Audio index: corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
[2026-07-30 22:00:00] INFO  Input directory: corpus/02_jubilee_debates_audio
[2026-07-30 22:00:00] INFO  Output directory: corpus/03_jubilee_debates_transcripts
[2026-07-30 22:00:00] INFO  Model: backend=whisperx model=large-v3 device=cuda compute_type=float16
[2026-07-30 22:00:00] INFO  Transcription: language=en task=transcribe batch_size=8 vad_filter=true
[2026-07-30 22:00:01] INFO  CUDA available: true; device=NVIDIA A10G
[2026-07-30 22:00:05] INFO  Loading transcription model large-v3
[2026-07-30 22:00:20] INFO  Transcription model loaded successfully
[2026-07-30 22:00:21] INFO  Loaded audio index: input=5 eligible=5 ignored=0 invalid=0
[2026-07-30 22:08:00] INFO  SUCCESS jubilee_surrounded_001 -> corpus/03_jubilee_debates_transcripts/jubilee_surrounded_001.txt
[2026-07-30 22:08:01] INFO  Wrote transcript index: corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
[2026-07-30 22:08:01] INFO  Wrote latest manifest: corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx_manifest.json
[2026-07-30 22:08:01] INFO  Finished run: succeeded=1 failed=0 skipped_existing=0 missing_input=0 invalid_metadata=0
```


---

# 14. Error Handling and Resiliency

## 14.1 Configuration errors

Configuration errors must stop the programme before transcription begins.

Examples:

- audio index missing;
- audio index unreadable;
- invalid JSON line in audio index;
- no eligible audio records;
- input directory missing;
- output directory cannot be created;
- invalid command-line arguments;
- start corpus ID not found;
- required Python package missing;
- CUDA requested but unavailable;
- model loading failure.

Exit code:

```plain text
2
```


---

## 14.2 Per-item errors

Per-item errors must not stop the full batch.

Examples:

- source audio missing;
- source audio unreadable;
- corrupted audio;
- unsupported audio;
- CUDA out of memory during item;
- transcription backend exception;
- output text cannot be written;
- output JSON cannot be written.

For each per-item error:

- mark the item as:
  - `missing_input`;
  - `failed_metadata`;
  - `failed`;
- capture short error message;
- log error;
- continue to next item.

Exit code:

```plain text
1
```


if any per-item error occurred.

---

## 14.3 Keyboard interruption

If interrupted with `Ctrl+C`, the programme must:

- stop processing;
- mark run as interrupted;
- write partial manifest where possible;
- log interruption;
- exit with code:

```plain text
130
```


Manifest should include:

```json
"interrupted": true
```


---

## 14.4 Exit codes

| Exit code | Meaning |
|---:|---|
| `0` | Completed with no failed attempted transcriptions, no missing inputs, and no invalid eligible metadata rows |
| `1` | Completed, but one or more transcriptions failed, source audio files were missing, or eligible metadata rows were invalid |
| `2` | Configuration or validation error |
| `130` | Interrupted by user |

Skipped existing files are not failures.

Ignored records where audio was not available are not failures.

Empty transcripts are not failures if transcription completed normally.

---

# 15. Docstrings and In-code Documentation

## 15.1 Module-level docstring

At the top of `transcribe_jubilee_debates_whisperx.py`, include a module-level docstring explaining:

- purpose of the programme;
- expected input audio index;
- source audio input directory;
- transcript output directory;
- use of Whisper Large v3;
- use of WhisperX;
- EC2/GPU recommendation;
- default test mode;
- resumability behaviour;
- start-corpus-ID support;
- transcription-only scope;
- example commands.

Suggested module docstring:

```python
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
```


---

## 15.2 Function docstrings

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
- `check_transcription_dependencies`
- `check_cuda_available`
- `load_audio_index`
- `resolve_source_audio_path`
- `plan_transcriptions`
- `load_transcription_model`
- `transcribe_one_debate`
- `normalise_transcript_text`
- `write_transcript_outputs`
- `write_transcript_index`
- `write_manifests`
- `main`

---

# 16. Suggested Constants

The implementation should define constants near the top of the file:

```python
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
```


---

# 17. Development Notes

## 17.1 Initial implementation scope

The first implementation should prioritise:

- correct sequential execution;
- model loaded only once;
- robust audio index reading;
- eligibility filtering by `audio_extraction_status`;
- robust source audio path resolution;
- safe skipping of existing outputs;
- reliable transcript `.txt` output;
- stable transcript `.json` output;
- reliable transcript index output;
- reliable logging;
- robust manifest writing;
- clear environment validation;
- safe resumability;
- `--start-corpus-id` support;
- conservative GPU settings.

Parallel processing should not be implemented initially.

## 17.2 Downstream pipeline note

This programme only transcribes audio.

Downstream stages include:

- WhisperX forced alignment;
- pyannote speaker diarisation;
- speaker assignment;
- QC reporting;
- possible manual speaker identity curation.

---

# 18. Acceptance Criteria

The programme is considered complete when:

1. Running from inside `cl_st1_ph0_carol/` works:

```shell script
python transcribe_jubilee_debates_whisperx.py
```


2. Running from project root works:

```shell script
python cl_st1_ph0_carol/transcribe_jubilee_debates_whisperx.py
```


3. Default paths are resolved relative to the programme directory.

4. It reads:

```plain text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


5. It processes only rows where extracted audio is available.

6. It uses source audio from the `audio_file` field when present and usable.

7. It falls back to:

```plain text
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```


8. It creates the output directory if needed:

```plain text
corpus/03_jubilee_debates_transcripts/
```


9. Each successful transcription writes:

```plain text
corpus/03_jubilee_debates_transcripts/<corpus_id>.txt
   corpus/03_jubilee_debates_transcripts/<corpus_id>.json
```


10. The default model is:

```plain text
large-v3
```


11. The default backend label is:

```plain text
whisperx
```


12. The default device is:

```plain text
cuda
```


13. The default compute type is:

```plain text
float16
```


14. The default language is:

```plain text
en
```


15. The default batch size is conservative:

```plain text
8
```


16. Existing complete transcript outputs are skipped unless `--reprocess` is used.

17. If only one transcript output exists, the item is treated as incomplete and planned for transcription.

18. Failed transcriptions do not stop the full batch.

19. Missing input audio files are marked as `missing_input`.

20. Invalid eligible metadata rows are marked as `failed_metadata`.

21. Empty transcripts are allowed if transcription completes normally and are logged as warnings.

22. The programme supports:

```shell script
--start-corpus-id CORPUS_ID
```


23. If `--start-corpus-id` is not found among eligible records, the programme exits with configuration error.

24. A log file is written at:

```plain text
corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx.log
```


25. A latest manifest is written at:

```plain text
corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx_manifest.json
```


26. A timestamped per-run manifest is also written.

27. A transcript index is written at:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
```


28. The transcript index is suitable as input to:

```plain text
align_jubilee_debates_whisperx.py
```


29. The programme exits with:
    - `0` for clean completion;
    - `1` for item-level failures, missing inputs, or invalid eligible metadata;
    - `2` for configuration errors;
    - `130` for keyboard interruption.

30. The programme does **not** align, diarise, assign speakers, or produce QC reports.

---

# 19. Short README Section

## Transcribe Jubilee debate audio with WhisperX

The `transcribe_jubilee_debates_whisperx.py` programme transcribes full-length Jubilee debate WAV files using Whisper/WhisperX-compatible transcription.

It reads the audio index:

```plain text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


Only records whose `audio_extraction_status` indicates available audio are processed.

Source audio files are resolved from the `audio_file` field when available. Otherwise, audio is read from:

```plain text
corpus/02_jubilee_debates_audio/
```


Each fallback source audio file is expected as:

```plain text
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```


Transcripts are written to:

```plain text
corpus/03_jubilee_debates_transcripts/
```


Each successful transcription writes:

```plain text
corpus/03_jubilee_debates_transcripts/<corpus_id>.txt
corpus/03_jubilee_debates_transcripts/<corpus_id>.json
```


Default test run:

```shell script
python transcribe_jubilee_debates_whisperx.py
```


This processes one planned debate by default.

Full run:

```shell script
python transcribe_jubilee_debates_whisperx.py --no-test-mode
```


Resume from a specific debate:

```shell script
python transcribe_jubilee_debates_whisperx.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```


Force re-transcription:

```shell script
python transcribe_jubilee_debates_whisperx.py \
  --no-test-mode \
  --reprocess
```


The programme writes:

```plain text
corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx.log
corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx_manifest.json
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
```


A timestamped per-run manifest is also created.

This stage performs transcription only. Alignment, diarisation, speaker assignment, and QC are handled by later stages.