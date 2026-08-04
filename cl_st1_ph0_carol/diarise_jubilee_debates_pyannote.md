# `diarise_jubilee_debates_pyannote.py` — Programme Specification for Development

## 1. High-level Functionality Specification

### Programme Summary

`diarise_jubilee_debates_pyannote.py` is a batch-processing programme that performs **speaker diarisation** on extracted Jubilee debate audio files using **pyannote.audio**.

The programme is part of:

```
Corpus Linguistics — Study 1 — Carol, Phase 0 — Speaker Diarisation Test
```


It is the third GPU-oriented speech-processing stage in the planned pipeline.

The preceding stages are:

| Stage | Programme |
|---:|---|
| 1 | `transcribe_jubilee_debates_whisperx.py` |
| 2 | `align_jubilee_debates_whisperx.py` |

The following stages are:

| Stage | Programme |
|---:|---|
| 4 | `assign_speakers_jubilee_debates.py` |
| 5 | `qc_jubilee_debates_speaker_diarisation.py` |

The programme reads the curated audio index produced by the audio extraction stage:

```
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


Each record in this index represents one extracted Jubilee debate audio file. The programme must process records where the audio is available, indicated by:

```
audio_extraction_status = success
```


or:

```
audio_extraction_status = skipped_existing
```


For each eligible record, the programme uses:

- `corpus_id` to identify the debate;
- `audio_file` to locate the source WAV file when present and usable;
- `<audio-dir>/<corpus_id>.wav` as a fallback audio path;
- `corpus_id` again to name diarisation outputs.

The source audio files are expected in:

```
corpus/02_jubilee_debates_audio/
```


Diarisation outputs must be written to:

```
corpus/05_jubilee_debates_diarisation/
```


For each successfully diarised debate, the programme must write:

```
corpus/05_jubilee_debates_diarisation/<corpus_id>.rttm
corpus/05_jubilee_debates_diarisation/<corpus_id>.diarisation.json
corpus/05_jubilee_debates_diarisation/<corpus_id>.segments.ndjson
```


The intended diarisation engine is:

```
pyannote.audio
```


The programme performs **speaker diarisation only**. It must not perform:

- audio extraction;
- Whisper transcription;
- WhisperX forced alignment;
- assignment of speaker labels to transcript words;
- real speaker identity resolution;
- manual speaker-name curation;
- downstream quality-control report generation.

---

## 2. Key Behaviours

The programme must implement the following behaviours:

- Read Jubilee debate audio metadata from an NDJSON audio index.
- Process only records where `audio_extraction_status` indicates usable audio.
- Extract required fields:
  - `corpus_id`.
- Locate source audio using:
  - `audio_file`, when present and usable;
  - otherwise `<audio_dir>/<corpus_id>.wav`.
- Create the diarisation output directory if it does not already exist.
- Load the pyannote diarisation pipeline once per run where practical.
- Use GPU acceleration by default where available.
- Require Hugging Face authentication when the selected pyannote model requires it.
- Avoid logging or writing Hugging Face token values.
- Support automatic speaker-count inference by default.
- Support optional `--num-speakers`, `--min-speakers`, and `--max-speakers` constraints.
- Use test mode by default, limiting processing to one eligible debate.
- Skip already-diarised debates by default, supporting safe re-runs.
- Allow reprocessing with an explicit command-line option.
- Support starting from a specific `corpus_id`.
- Continue processing remaining debates if one diarisation fails.
- Record progress and errors in an append-only log file.
- Produce a JSON manifest with run-level metadata and item-level results.
- Write both:
  - a timestamped per-run manifest;
  - a latest manifest overwritten on each run.
- Write a curated diarisation index for downstream speaker assignment and QC.
- Exit with status code `0` only when all attempted diarisation jobs succeed or are skipped, and there are no missing inputs or invalid eligible metadata rows.
- Exit with a non-zero status code if one or more attempted diarisation jobs fail, if source audio is missing, if eligible metadata is invalid, or if there is a configuration/validation error.

---

## 3. Path Resolution Policy

The programme must resolve default paths relative to the directory where `diarise_jubilee_debates_pyannote.py` is located, not relative to the current working directory.

If the script is located at:

```
cl_st1_ph0_carol/diarise_jubilee_debates_pyannote.py
```


then the default audio index path:

```
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


must resolve to:

```
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


This ensures that the programme works when executed from:

```
cl_st1_carol/
```


or:

```
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

- `--audio-index`
- `--audio-dir`
- `--output-dir`
- `--log-file`
- `--manifest-file`
- `--diarisation-index-file`

the programme must preserve that absolute path.

---

## 4. Input / Output Specification

## 4.1 Input

### Input audio index file

Default path:

```
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


The file is expected to be in **NDJSON** format: one JSON object per line.

This file is produced by the audio extraction stage.

### Required fields

Each valid eligible audio-index record must contain:

| Field | Type | Description |
|---|---:|---|
| `corpus_id` | string | Stable internal debate identifier, e.g. `jubilee_surrounded_001` |
| `audio_extraction_status` | string | Status from the audio extraction stage |

The source audio path is resolved using:

| Field | Requirement | Description |
|---|---|---|
| `audio_file` | optional | Preferred local WAV path when present and usable |

If `audio_file` is absent, blank, or unusable, the programme must fall back to:

```
<audio_dir>/<corpus_id>.wav
```


### Eligible audio extraction statuses

The programme must process only records where:

```
audio_extraction_status = success
```


or:

```
audio_extraction_status = skipped_existing
```


Records with other statuses must be ignored, not treated as errors.

Ineligible statuses include:

```
failed
missing_input
failed_metadata
ignored_audio_unavailable
interrupted
null
""
missing value
```


### Metadata fields to preserve

The programme should preserve these fields in diarisation outputs and indices when present:

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
| `audio_extraction_status` | Previous stage status |
| `audio_extraction_run_id` | Previous stage run ID |
| `audio_extracted_at_utc` | Previous stage timestamp |
| `audio_codec` | Audio codec, if recorded |
| `audio_sample_rate_hz` | Audio sample rate, if recorded |
| `audio_channels` | Number of audio channels, if recorded |
| `audio_duration_seconds` | Extracted audio duration, if recorded |
| `download_status` | Download stage status |
| `download_run_id` | Download stage run ID |
| `selected_by` | Selector |
| `selection_source` | Selection source |
| `notes` | Notes |

---

## 4.2 Input audio files

### Audio input directory

Default path:

```
corpus/02_jubilee_debates_audio/
```


Each fallback source audio file is expected as:

```
<audio_dir>/<corpus_id>.wav
```


Examples:

```
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

The diarisation programme may rely on the audio extraction programme for audio compatibility.

---

## 4.3 Output

### Diarisation output directory

Default path:

```
corpus/05_jubilee_debates_diarisation/
```


The programme must create this directory if it does not already exist.

### Per-debate RTTM

Each successful diarisation must write:

```
<output_dir>/<corpus_id>.rttm
```


Example:

```
corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.rttm
```


RTTM is required because it is a standard diarisation interchange format and can be used by downstream tooling.

### Per-debate diarisation JSON

Each successful diarisation must write:

```
<output_dir>/<corpus_id>.diarisation.json
```


Example:

```
corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.diarisation.json
```


This file contains project-stable diarisation metadata and a normalised list of speaker turns.

### Per-debate segments NDJSON

Each successful diarisation should write:

```
<output_dir>/<corpus_id>.segments.ndjson
```


Example:

```
corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.segments.ndjson
```


This file should contain one diarised speaker interval per line for easier downstream speaker assignment and QC.

### Log file

Default path:

```
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote.log
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

```
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote_manifest.json
```


#### Per-run manifest

A timestamped copy must also be written using the run ID.

Filename pattern:

```
diarise_jubilee_debates_pyannote_manifest_<run_id>.json
```


Example:

```
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote_manifest_20260804T140000Z.json
```


### Diarisation index file

Default path:

```
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
```


This curated diarisation index is used by downstream speaker assignment and QC stages.

---

# 5. Command-line Interface

## 5.1 Default usage

The programme may be run from inside `cl_st1_ph0_carol/`:

```
python diarise_jubilee_debates_pyannote.py
```


or from the project root:

```
python cl_st1_ph0_carol/diarise_jubilee_debates_pyannote.py
```


Both commands should resolve default paths correctly.

Default behaviour:

- audio index:

```
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


- audio directory:

```
corpus/02_jubilee_debates_audio/
```


- output directory:

```
corpus/05_jubilee_debates_diarisation/
```


- backend:

```
pyannote
```


- model:

```
pyannote/speaker-diarization-3.1
```


- device:

```
cuda
```


- speaker count:

```
auto / unspecified
```


- minimum speakers:

```
unspecified
```


- maximum speakers:

```
unspecified
```


- test mode:

```
enabled
```


- test limit:

```
1
```


- reprocess:

```
disabled
```


- existing complete diarisation outputs are skipped;
- one worker / sequential processing.

### Note on default test limit

This project processes long-form debate audio with many speakers. The default test limit should remain:

```
1
```


---

## 5.2 Required arguments

There are no required command-line arguments if all defaults are used.

However, the runtime environment must provide Hugging Face authentication if the configured pyannote model requires it.

The recommended environment variable is:

```
export HF_TOKEN="hf_..."
```


The programme must not require the token to be passed directly on the command line.

---

## 5.3 Optional arguments

### Audio index

```
--audio-index PATH
```


Default:

```
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


Description:

Path to the curated NDJSON audio index from the audio extraction stage.

---

### Audio directory

```
--audio-dir PATH
```


Default:

```
corpus/02_jubilee_debates_audio/
```


Description:

Fallback directory containing source WAV files.

---

### Output directory

```
--output-dir PATH
```


Default:

```
corpus/05_jubilee_debates_diarisation/
```


Description:

Directory where diarisation outputs, logs, manifests, and the diarisation index are written.

---

### Backend

```
--backend BACKEND
```


Default:

```
pyannote
```


Allowed values:

```
pyannote
```


Description:

Backend label recorded in outputs. The first implementation should use pyannote.audio.

---

### Model

```
--model MODEL_NAME
```


Default:

```
pyannote/speaker-diarization-3.1
```


Description:

Hugging Face model identifier for the pyannote diarisation pipeline.

The model may require the user to accept terms on Hugging Face before use.

---

### Hugging Face token environment variable

```
--hf-token-env-var ENV_VAR_NAME
```


Default:

```
HF_TOKEN
```


Description:

Name of the environment variable from which the programme reads the Hugging Face access token.

The programme must:

- read the token from the named environment variable;
- never print the token;
- never write the token to logs, manifests, JSON outputs, or index files;
- record only whether a token was present.

---

### Device

```
--device DEVICE
```


Default:

```
cuda
```


Allowed values:

```
cuda
cpu
auto
```


For EC2 GPU processing, use:

```
cuda
```


If `--device cuda` is requested and CUDA is unavailable, fail fast with configuration error.

If `--device auto` is requested:

- use CUDA when available;
- otherwise use CPU;
- log the selected device.

---

### Number of speakers

```
--num-speakers N
```


Default:

```
None
```


Description:

Optional exact speaker count passed to pyannote when known.

For the first pass, this should usually be omitted because the Jubilee `Surrounded` debates may contain many speakers and speaker-count assumptions should be tested empirically.

If provided:

- must be a positive integer;
- cannot be combined with `--min-speakers` or `--max-speakers` unless the implementation explicitly supports that combination.

---

### Minimum speakers

```
--min-speakers N
```


Default:

```
None
```


Description:

Optional lower bound on speaker count.

Potential later tuning value:

```
8
```


For the initial implementation, leave unspecified by default.

---

### Maximum speakers

```
--max-speakers N
```


Default:

```
None
```


Description:

Optional upper bound on speaker count.

Potential later tuning value for `Surrounded`-style debates:

```
30
```


For the initial implementation, leave unspecified by default.

---

### Test mode

```
--test-mode
--no-test-mode
```


Default:

```
--test-mode
```


---

### Test limit

```
--test-limit N
```


Default:

```
1
```


Must be a positive integer.

---

### Reprocess existing diarisation outputs

```
--reprocess
```


Default:

```
False
```


When omitted, debates with all required diarisation outputs present are skipped.

When provided, diarisation is run again and existing outputs are overwritten.

---

### Start corpus ID

```
--start-corpus-id CORPUS_ID
```


Default:

```
None
```


Start planning from a specific `corpus_id`.

Example:

```
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```


---

### Log file

```
--log-file PATH
```


Default:

```
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote.log
```


---

### Manifest file

```
--manifest-file PATH
```


Default:

```
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote_manifest.json
```


---

### Diarisation index file

```
--diarisation-index-file PATH
```


Default:

```
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
```


---

### Workers

```
--workers N
```


Default:

```
1
```


Only `--workers 1` is supported in the first implementation.

Parallel processing should not be implemented initially because long-form diarisation can be GPU- and memory-sensitive.

---

### Timeout

```
--timeout SECONDS
```


Default suggestion:

```
14400
```


A four-hour per-item timeout is appropriate for long debate diarisation.

Strict timeout enforcement may require subprocess isolation. The first implementation may record the value without hard enforcement.

---

### Maximum retries

```
--max-retries N
```


Default:

```
1
```


---

### Retry delay

```
--retry-delay SECONDS
```


Default:

```
5
```


---

## 5.4 Example commands

### Default one-debate diarisation test

```
python diarise_jubilee_debates_pyannote.py
```


### Test from a specific corpus ID

```
python diarise_jubilee_debates_pyannote.py \
  --test-limit 1 \
  --start-corpus-id jubilee_surrounded_003
```


### Full diarisation run

```
python diarise_jubilee_debates_pyannote.py --no-test-mode
```


### Full run with loose speaker-count bounds

```
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --min-speakers 8 \
  --max-speakers 30
```


### Full run with exact speaker count for testing

```
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --num-speakers 21
```


### Re-diarise all debates

```
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --reprocess
```


### EC2 run inside `tmux`

```
tmux new -s jubilee_diarise
conda activate whisperx_pyannote
cd ~/cl_st1_carol/cl_st1_ph0_carol
export HF_TOKEN="hf_..."
python diarise_jubilee_debates_pyannote.py --no-test-mode
```


Detach:

```
Ctrl+B
D
```


Reattach:

```
tmux attach -t jubilee_diarise
```


---

# 6. Argument Validation

The programme must fail fast with a clear message if:

- the audio index file does not exist;
- the audio index path is not a file;
- the audio index is unreadable;
- the audio index contains invalid JSON lines;
- no eligible audio records are found;
- the audio directory does not exist;
- the audio directory is not a directory;
- the output directory cannot be created;
- `--backend` is unsupported;
- `--model` is missing or blank;
- `--device` is missing or blank;
- `--hf-token-env-var` is missing or blank;
- `--num-speakers` is less than or equal to zero;
- `--min-speakers` is less than or equal to zero;
- `--max-speakers` is less than or equal to zero;
- `--min-speakers` is greater than `--max-speakers`;
- `--num-speakers` is combined with `--min-speakers` or `--max-speakers`, unless explicitly supported;
- `--test-limit` is less than or equal to zero;
- `--workers` is less than or equal to zero;
- `--workers` is not `1`;
- `--timeout` is less than or equal to zero;
- `--max-retries` is negative;
- `--retry-delay` is negative;
- `--start-corpus-id` is provided but empty;
- `--start-corpus-id` is provided but not found among eligible audio records;
- required Python packages are not installed;
- `--device cuda` is requested but CUDA is unavailable;
- the Hugging Face token is missing and the selected model cannot be loaded without it;
- the user has not accepted the selected pyannote model terms on Hugging Face;
- the pyannote pipeline cannot be loaded.

A validation error should:

- be printed clearly to the console;
- be written to the log if logging has already been configured;
- cause the programme to exit with code `2`.

---

# 7. Environment and Configuration

## 7.1 Recommended EC2 environment

Recommended EC2 deployment:

```
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

```
g5.2xlarge
```


or:

```
g5.4xlarge
```


## 7.2 Required Python packages

Required:

```
pyannote.audio
torch
torchaudio
huggingface_hub
```


Optional:

```
tqdm
```


## 7.3 CUDA checks

Before diarisation, verify:

```
nvidia-smi
```


and:

```
python -c "import torch; print(torch.cuda.is_available()); print(torch.version.cuda)"
```


If CUDA is unavailable and `--device cuda` was requested, fail fast.

## 7.4 Hugging Face access

The pyannote model may require:

1. a Hugging Face account;
2. accepting the model terms on Hugging Face;
3. an access token.

Recommended setup:

```
export HF_TOKEN="hf_..."
```


or:

```
huggingface-cli login
```


The programme must not put the token into:

- code;
- command examples in logs;
- JSON outputs;
- manifests;
- index files;
- exception traces where avoidable.

It may record:

```json
{
  "huggingface_token_present": true
}
```


but never the token value.

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
   - Check Hugging Face token presence.
   - Record environment metadata.

2. **Audio index loading**
   - Open the NDJSON audio index.
   - Read records line by line.
   - Parse each JSON object.
   - Count total records.
   - Select only records where `audio_extraction_status` is eligible.
   - Validate required field:
     - `corpus_id`.
   - Preserve input order.
   - Record invalid eligible rows.
   - Record ignored rows where audio is unavailable.

3. **Planning**
   - Apply `--start-corpus-id`, if provided.
   - Resolve input audio path.
   - Compute output paths:
     - `<output_dir>/<corpus_id>.rttm`;
     - `<output_dir>/<corpus_id>.diarisation.json`;
     - `<output_dir>/<corpus_id>.segments.ndjson`.
   - Check missing audio.
   - Skip if outputs already exist and `--reprocess` is not enabled.
   - Apply test-mode limit to planned diarisation jobs.

4. **Pipeline loading**
   - Load the pyannote diarisation pipeline once per run.
   - Move the pipeline to CUDA when configured.
   - Fail fast if the pipeline cannot be loaded because of missing token, model access, dependency errors, or device errors.

5. **Execution**
   - For each planned item:
     - run pyannote diarisation on the WAV file;
     - normalise diarisation output into project-stable speaker intervals;
     - write RTTM;
     - write diarisation JSON;
     - write segment-level NDJSON;
     - capture timing, warnings, speaker count, segment count, and errors;
     - retry according to `--max-retries`;
     - mark item as `success` or `failed`.

6. **Diarisation index generation**
   - Combine source metadata and diarisation metadata.
   - Write curated NDJSON diarisation index.

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
    """Parse command-line arguments for the diarisation programme."""
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
def check_diarisation_dependencies() -> dict:
    """Check required Python package availability."""
```


```python
def check_cuda_available(device: str) -> dict:
    """Validate CUDA availability when requested."""
```


```python
def get_hf_token(env_var_name: str) -> str | None:
    """Read Hugging Face token from an environment variable without logging it."""
```


```python
def load_audio_index(
    audio_index_path: Path,
) -> tuple[list[dict], list[dict], int, int, list[dict]]:
    """Load and validate eligible audio records from NDJSON."""
```


```python
def resolve_audio_path(record: dict, audio_dir: Path) -> Path:
    """Resolve source audio path using audio_file or fallback audio directory."""
```


```python
def plan_diarisations(
    records: list[dict],
    audio_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_corpus_id: str | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Create planned, skipped, and missing-input diarisation records."""
```


```python
def load_diarisation_pipeline(
    model_name: str,
    device: str,
    hf_token: str | None,
) -> Any:
    """Load the pyannote.audio diarisation pipeline."""
```


```python
def diarise_one_debate(
    item: dict,
    pipeline: Any,
    model_config: dict,
    max_retries: int,
    retry_delay: int,
    logger: logging.Logger,
) -> dict:
    """Diarise one debate audio file and return a structured result."""
```


```python
def normalise_diarisation_result(raw_diarisation: Any, corpus_id: str) -> list[dict]:
    """Normalise pyannote output into project-stable speaker interval records."""
```


```python
def write_rttm(
    speaker_segments: list[dict],
    rttm_path: Path,
    corpus_id: str,
) -> None:
    """Write speaker diarisation as RTTM."""
```


```python
def write_diarisation_outputs(
    diarisation_json: dict,
    speaker_segments: list[dict],
    diarisation_json_path: Path,
    segments_ndjson_path: Path,
) -> None:
    """Write diarisation JSON and segment-level NDJSON outputs."""
```


```python
def write_diarisation_index(
    index_records: list[dict],
    diarisation_index_file: Path,
) -> None:
    """Write curated NDJSON diarisation index."""
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
    """Run the batch Jubilee debate diarisation workflow and return an exit code."""
```


---

# 9. Diarisation Behaviour

## 9.1 Diarisation backend

The required backend is:

```
pyannote
```


Conceptual model loading:

```python
from pyannote.audio import Pipeline

pipeline = Pipeline.from_pretrained(
    model_name,
    use_auth_token=hf_token,
)
```


Conceptual CUDA placement:

```python
pipeline.to(torch.device("cuda"))
```


Conceptual diarisation call:

```python
diarisation = pipeline(
    str(audio_path),
    num_speakers=num_speakers,
    min_speakers=min_speakers,
    max_speakers=max_speakers,
)
```


Exact API details may vary by pyannote.audio version. The implementation must normalise outputs into the project schema.

---

## 9.2 Speaker-count policy

Default behaviour should be:

```
num_speakers = None
min_speakers = None
max_speakers = None
```


This allows pyannote to infer speaker count automatically.

For Jubilee `Surrounded` debates, there may be:

- one featured speaker;
- one or more moderators/hosts;
- many rotating participants;
- audience reactions;
- interruptions;
- overlapping speech.

The initial implementation should avoid hard-coding the number of speakers.

Later tuning runs may use:

```
min_speakers = 8
max_speakers = 30
```


or a known exact speaker count for individual debates.

The programme must record the speaker-count configuration in:

- per-debate JSON;
- manifest;
- diarisation index.

---

## 9.3 Normalised speaker segment structure

The normalised diarisation segments should use a stable schema:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "segment_index": 1,
  "speaker": "SPEAKER_00",
  "start": 12.42,
  "end": 18.91,
  "duration": 6.49,
  "diarisation_status": "speech"
}
```


The programme should preserve pyannote speaker labels such as:

```
SPEAKER_00
SPEAKER_01
SPEAKER_02
```


These labels must be treated as **anonymous diarisation labels**, not real participant identities.

The programme must not attempt to infer real speaker names.

---

## 9.4 Diarisation JSON structure

The per-debate diarisation JSON should include:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "input_audio_path": "corpus/02_jubilee_debates_audio/jubilee_surrounded_001.wav",
  "rttm_path": "corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.rttm",
  "diarisation_json_path": "corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.diarisation.json",
  "segments_ndjson_path": "corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.segments.ndjson",
  "diarisation_model": {
    "backend": "pyannote",
    "model_name": "pyannote/speaker-diarization-3.1",
    "device": "cuda",
    "num_speakers": null,
    "min_speakers": null,
    "max_speakers": null
  },
  "diarisation": {
    "speaker_count": 18,
    "segment_count": 1450,
    "total_speech_seconds": 4820.35,
    "speakers": [
      {
        "speaker": "SPEAKER_00",
        "segment_count": 320,
        "total_speech_seconds": 1700.25
      },
      {
        "speaker": "SPEAKER_01",
        "segment_count": 85,
        "total_speech_seconds": 410.8
      }
    ],
    "segments": [
      {
        "segment_index": 1,
        "speaker": "SPEAKER_00",
        "start": 12.42,
        "end": 18.91,
        "duration": 6.49,
        "diarisation_status": "speech"
      }
    ]
  },
  "metadata": {},
  "run": {
    "diarisation_run_id": "20260804T140000Z",
    "diarised_at_utc": "2026-08-04T14:00:00Z"
  },
  "status": "success",
  "error": null
}
```


---

## 9.5 Segment NDJSON structure

Each line in `<corpus_id>.segments.ndjson` should contain one diarised speaker interval.

Recommended fields:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "segment_index": 1,
  "speaker": "SPEAKER_00",
  "start": 12.42,
  "end": 18.91,
  "duration": 6.49,
  "diarisation_status": "speech"
}
```


---

## 9.6 RTTM structure

The RTTM file should use standard speaker diarisation lines.

Example:

```
SPEAKER jubilee_surrounded_001 1 12.420 6.490 <NA> <NA> SPEAKER_00 <NA> <NA>
```


Where:

- file ID is `corpus_id`;
- channel is `1`;
- start is segment start time in seconds;
- duration is `end - start`;
- speaker is the pyannote speaker label.

---

## 9.7 Existing files

If all of the following already exist:

```
<output_dir>/<corpus_id>.rttm
<output_dir>/<corpus_id>.diarisation.json
<output_dir>/<corpus_id>.segments.ndjson
```


and `--reprocess` is not enabled:

- do not run diarisation;
- mark item as `skipped_existing`;
- log the skip;
- include item in manifest;
- include item in diarisation index.

If only some outputs exist:

- treat item as incomplete;
- run diarisation again;
- overwrite incomplete outputs.

---

## 9.8 Missing inputs

If audio is missing:

- mark `missing_input`;
- log missing audio;
- continue.

Missing inputs cause exit code `1`.

---

## 9.9 Diarisation failures

If pyannote diarisation raises an exception or returns invalid output:

- capture the error;
- mark item as `failed`;
- log the failure;
- continue to next item;
- exit with code `1` after the run.

Common failure categories should be recognisable in logs where possible:

- Hugging Face authentication failure;
- Hugging Face model terms not accepted;
- model download failure;
- CUDA out-of-memory;
- audio decoding failure;
- invalid diarisation output;
- output write failure.

---

# 10. Diarisation Index Design

The programme must write:

```
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
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
| `duration_seconds` | Source duration |
| `duration_string` | Human-readable duration |
| `chapters` | Chapter metadata |
| `audio_file` | Source WAV path |
| `rttm_file` | RTTM output path |
| `diarisation_json_file` | Diarisation JSON output path |
| `segments_ndjson_file` | Segment NDJSON output path |
| `diarisation_status` | Status |
| `diarisation_run_id` | Run ID |
| `diarised_at_utc` | Timestamp |
| `diarisation_backend` | Backend |
| `diarisation_model_name` | Model name |
| `diarisation_device` | Device |
| `num_speakers` | Exact speaker constraint, if used |
| `min_speakers` | Minimum speaker constraint, if used |
| `max_speakers` | Maximum speaker constraint, if used |
| `detected_speaker_count` | Number of speaker labels returned |
| `diarised_segment_count` | Number of speaker intervals |
| `total_speech_seconds` | Total diarised speech time |
| `audio_extraction_status` | Previous stage status |
| `audio_extraction_run_id` | Previous stage run ID |
| `selected_by` | Selector |
| `selection_source` | Selection source |
| `notes` | Notes |
| `error` | Error message |

The diarisation index must be suitable as input to:

```
assign_speakers_jubilee_debates.py
```


and:

```
qc_jubilee_debates_speaker_diarisation.py
```


---

# 11. JSON Manifest Design

## 11.1 Manifest structure

The manifest must use this general structure:

```json
{
  "run_metadata": {
    "run_id": "20260804T140000Z",
    "tool_name": "diarise_jubilee_debates_pyannote.py",
    "tool_version": "v1",
    "start_time": "2026-08-04T14:00:00Z",
    "end_time": "2026-08-04T15:20:00Z",
    "test_mode": true,
    "test_limit": 1,
    "reprocess": false,
    "workers": 1,
    "audio_index_path": "corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson",
    "audio_dir": "corpus/02_jubilee_debates_audio",
    "output_dir": "corpus/05_jubilee_debates_diarisation",
    "diarisation_index_file": "corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson",
    "log_file": "corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote.log",
    "manifest_file": "corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote_manifest.json",
    "config": {
      "backend": "pyannote",
      "model_name": "pyannote/speaker-diarization-3.1",
      "device": "cuda",
      "num_speakers": null,
      "min_speakers": null,
      "max_speakers": null,
      "timeout_seconds": 14400,
      "max_retries": 1,
      "retry_delay_seconds": 5,
      "start_corpus_id": null,
      "hf_token_env_var": "HF_TOKEN",
      "huggingface_token_present": true
    },
    "environment": {
      "python_version": "3.11.x",
      "cuda_available": true,
      "cuda_device_name": "NVIDIA A10G",
      "torch_version": "unknown",
      "torch_cuda_version": "unknown",
      "pyannote_audio_version": "unknown"
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
      "rttm_path": "corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.rttm",
      "diarisation_json_path": "corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.diarisation.json",
      "segments_ndjson_path": "corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.segments.ndjson",
      "status": "success",
      "error": null,
      "retries": 0,
      "duration_seconds": 1800.5,
      "start_time": "2026-08-04T14:01:00Z",
      "end_time": "2026-08-04T14:31:00Z",
      "detected_speaker_count": 18,
      "diarised_segment_count": 1450,
      "total_speech_seconds": 4820.35,
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
| `success` | Diarisation completed successfully |
| `failed` | Diarisation was attempted but failed |
| `skipped_existing` | Diarisation outputs already existed and `--reprocess` was not enabled |
| `missing_input` | Source audio was missing |
| `failed_metadata` | Eligible audio-index row was invalid |
| `ignored_audio_unavailable` | Record ignored because extracted audio was not available |
| `interrupted` | Processing stopped due to keyboard interruption |

---

# 12. Logging Specification

The programme must write an append-only UTF-8 log file.

Default:

```
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote.log
```


Log format:

```
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```


Required log events:

- startup;
- run ID;
- parsed configuration;
- audio index path;
- audio directory;
- output directory;
- test mode status;
- test limit;
- reprocess setting;
- start corpus ID;
- backend;
- model name;
- device;
- speaker-count settings;
- Hugging Face token presence as boolean only;
- dependency availability;
- CUDA availability;
- pyannote pipeline loading start;
- pyannote pipeline loading success;
- pyannote pipeline loading failure;
- number of audio index records read;
- number of eligible records;
- number of ignored records;
- number of invalid metadata rows;
- number of planned diarisation jobs;
- each skipped existing diarisation;
- each missing input;
- each diarisation attempt;
- each retry;
- each success;
- each failure;
- detected speaker count per item;
- diarised segment count per item;
- total diarised speech time per item;
- diarisation index write path;
- manifest write paths;
- final summary;
- configuration errors;
- keyboard interruptions.

The log must never include the Hugging Face token value.

---

# 13. Error Handling and Resiliency

## 13.1 Configuration errors

Configuration errors must stop the programme before diarisation begins.

Examples:

- audio index missing;
- audio index unreadable;
- invalid JSON line in audio index;
- no eligible audio records;
- audio directory missing;
- invalid command-line arguments;
- start corpus ID not found;
- `pyannote.audio` unavailable;
- `torch` unavailable;
- CUDA requested but unavailable;
- Hugging Face model cannot be loaded;
- Hugging Face token missing when required;
- Hugging Face model terms not accepted.

Exit code:

```
2
```


---

## 13.2 Per-item errors

Per-item errors must not stop the full batch.

Examples:

- source audio missing;
- audio file unreadable;
- audio decoding failure;
- diarisation backend exception;
- CUDA out of memory;
- invalid diarisation output;
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

```
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

```
130
```


---

## 13.4 Exit codes

| Exit code | Meaning |
|---:|---|
| `0` | Completed with no failed attempted diarisation jobs, no missing inputs, and no invalid eligible metadata rows |
| `1` | Completed, but one or more diarisation jobs failed, source inputs were missing, or eligible metadata rows were invalid |
| `2` | Configuration or validation error |
| `130` | Interrupted by user |

Skipped existing files are not failures.

Ignored records where audio was not available are not failures.

---

# 14. Docstrings and In-code Documentation

## 14.1 Module-level docstring

At the top of `diarise_jubilee_debates_pyannote.py`, include a module-level docstring explaining:

- purpose of programme;
- expected input audio index;
- source audio input directory;
- diarisation output directory;
- use of pyannote.audio;
- Hugging Face token requirement;
- EC2/GPU recommendation;
- default test mode;
- resumability behaviour;
- start-corpus-ID support;
- diarisation-only scope;
- example commands.

Suggested module docstring:

```python
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
- `check_diarisation_dependencies`
- `check_cuda_available`
- `get_hf_token`
- `load_audio_index`
- `resolve_audio_path`
- `plan_diarisations`
- `load_diarisation_pipeline`
- `diarise_one_debate`
- `normalise_diarisation_result`
- `write_rttm`
- `write_diarisation_outputs`
- `write_diarisation_index`
- `write_manifests`
- `main`

---

# 15. Suggested Constants

```python
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

DEFAULT_NUM_SPEAKERS = None
DEFAULT_MIN_SPEAKERS = None
DEFAULT_MAX_SPEAKERS = None

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
```


---

# 16. Development Notes

## 16.1 Initial implementation scope

The first implementation should prioritise:

- correct sequential execution;
- robust audio index reading;
- eligibility filtering by `audio_extraction_status`;
- robust input audio resolution;
- stable pyannote pipeline loading;
- secure Hugging Face token handling;
- automatic speaker-count inference by default;
- optional speaker-count constraints;
- stable RTTM output;
- stable diarisation JSON output;
- stable segment NDJSON output;
- reliable diarisation index output;
- reliable logging;
- robust manifest writing;
- clear environment validation;
- safe resumability;
- `--start-corpus-id` support;
- conservative GPU use.

Parallel processing should not be implemented initially.

## 16.2 Downstream pipeline note

This programme only detects anonymous speaker intervals.

Downstream stages include:

- assigning diarised speaker labels to aligned words/segments;
- creating speaker-attributed transcripts;
- quality-control reporting;
- possible manual speaker identity curation.

Diarised labels such as `SPEAKER_00` are not real identities.

---

# 17. Acceptance Criteria

The programme is considered complete when:

1. Running from inside `cl_st1_ph0_carol/` works:

```
python diarise_jubilee_debates_pyannote.py
```


2. Running from project root works:

```
python cl_st1_ph0_carol/diarise_jubilee_debates_pyannote.py
```


3. Default paths are resolved relative to the programme directory.

4. It reads:

```
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


5. It processes only records where extracted audio is available.

6. It uses source audio from `audio_file` when present and usable.

7. It falls back to:

```
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```


8. It creates the output directory if needed:

```
corpus/05_jubilee_debates_diarisation/
```


9. Each successful diarisation writes:

```
corpus/05_jubilee_debates_diarisation/<corpus_id>.rttm
corpus/05_jubilee_debates_diarisation/<corpus_id>.diarisation.json
corpus/05_jubilee_debates_diarisation/<corpus_id>.segments.ndjson
```


10. The default backend is:

```
pyannote
```


11. The default model is:

```
pyannote/speaker-diarization-3.1
```


12. The default device is:

```
cuda
```


13. Existing complete diarisation outputs are skipped unless `--reprocess` is used.

14. If only some diarisation outputs exist, the item is treated as incomplete and planned for diarisation.

15. Failed diarisation jobs do not stop the full batch.

16. Missing input audio files are marked as `missing_input`.

17. Invalid eligible metadata rows are marked as `failed_metadata`.

18. The programme supports:

```
--start-corpus-id CORPUS_ID
```


19. If `--start-corpus-id` is not found among eligible records, the programme exits with configuration error.

20. The programme supports automatic speaker-count inference by default.

21. The programme supports optional:

```
--num-speakers N
--min-speakers N
--max-speakers N
```


22. Hugging Face token values are never logged or written to outputs.

23. A log file is written at:

```
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote.log
```


24. A latest manifest is written at:

```
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote_manifest.json
```


25. A timestamped per-run manifest is also written.

26. A diarisation index is written at:

```
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
```


27. The diarisation index is suitable as input to:

```
assign_speakers_jubilee_debates.py
```


28. The programme exits with:
    - `0` for clean completion;
    - `1` for item-level failures, missing inputs, or invalid eligible metadata;
    - `2` for configuration errors;
    - `130` for keyboard interruption.

29. The programme does **not** transcribe, align, assign speakers to words, identify real speakers, or produce QC reports.

---

# 18. Short README Section

## Diarise Jubilee debate audio with pyannote.audio

The `diarise_jubilee_debates_pyannote.py` programme performs speaker diarisation on extracted Jubilee debate WAV audio using pyannote.audio.

It reads the audio index:

```
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


Only records whose `audio_extraction_status` indicates available audio are processed.

Source audio files are resolved from the `audio_file` field when available. Otherwise, audio is read from:

```
corpus/02_jubilee_debates_audio/
```


Each fallback source audio file is expected as:

```
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```


Diarisation outputs are written to:

```
corpus/05_jubilee_debates_diarisation/
```


Each successful diarisation writes:

```
corpus/05_jubilee_debates_diarisation/<corpus_id>.rttm
corpus/05_jubilee_debates_diarisation/<corpus_id>.diarisation.json
corpus/05_jubilee_debates_diarisation/<corpus_id>.segments.ndjson
```


Set Hugging Face authentication before running if required:

```
export HF_TOKEN="hf_..."
```


Default test run:

```
python diarise_jubilee_debates_pyannote.py
```


This processes one planned debate by default.

Full run:

```
python diarise_jubilee_debates_pyannote.py --no-test-mode
```


Resume from a specific debate:

```
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```


Force re-diarisation:

```
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --reprocess
```


Optional speaker-count bounds:

```
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --min-speakers 8 \
  --max-speakers 30
```


The programme writes:

```
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote.log
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote_manifest.json
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
```


A timestamped per-run manifest is also created.

This stage performs diarisation only. Transcription, alignment, speaker assignment, and QC are handled by separate pipeline stages.