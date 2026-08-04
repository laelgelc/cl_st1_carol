# `qc_jubilee_debates_speaker_diarisation.py` — Programme Specification for Development

## 1. High-level Functionality Specification

### Programme Summary

`qc_jubilee_debates_speaker_diarisation.py` is a batch-processing programme that produces **quality-control summaries and diagnostics** for the Jubilee debate speaker diarisation pipeline.

The programme is part of:

```
Corpus Linguistics — Study 1 — Carol, Phase 0 — Speaker Diarisation Test
```


It is the fifth stage in the speech-processing pipeline.

The preceding stages are:

| Stage | Programme |
|---:|---|
| 1 | `transcribe_jubilee_debates_whisperx.py` |
| 2 | `align_jubilee_debates_whisperx.py` |
| 3 | `diarise_jubilee_debates_pyannote.py` |
| 4 | `assign_speakers_jubilee_debates.py` |

The programme reads the speaker-assignment index produced by:

```
assign_speakers_jubilee_debates.py
```


Default input:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
```


For each eligible speaker-assignment record, the programme must inspect the available upstream and derived outputs, especially:

```
corpus/04_jubilee_debates_alignment/<corpus_id>.aligned.json
corpus/04_jubilee_debates_alignment/<corpus_id>.words.ndjson
corpus/05_jubilee_debates_diarisation/<corpus_id>.diarisation.json
corpus/05_jubilee_debates_diarisation/<corpus_id>.segments.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_transcript.txt
```


where available, using paths recorded in the speaker-assignment index first and fallback conventions second.

QC outputs must be written to:

```
corpus/07_jubilee_debates_qc/
```


For each successfully QC-processed debate, the programme must write:

```
corpus/07_jubilee_debates_qc/<corpus_id>.qc.json
corpus/07_jubilee_debates_qc/<corpus_id>.qc.md
```


The programme must also write a corpus-level QC summary:

```
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_summary.json
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_summary.md
```


The programme performs **quality-control reporting only**. It must not perform:

- audio extraction;
- transcription;
- forced alignment;
- speaker diarisation;
- speaker assignment;
- real speaker identity resolution;
- manual speaker-name curation;
- correction of upstream outputs.

The programme may recommend manual review, but it must not alter upstream processing outputs.

---

## 2. Key Behaviours

The programme must implement the following behaviours:

- Read the speaker-assignment index from NDJSON.
- Process only records where `speaker_assignment_status` indicates usable speaker-assigned outputs.
- Locate speaker-assignment outputs using index paths first and fallback paths second.
- Optionally locate alignment and diarisation upstream outputs for additional diagnostics.
- Compute per-debate QC metrics.
- Compute corpus-level QC summary metrics.
- Detect likely problems in:
  - alignment coverage;
  - diarisation coverage;
  - speaker assignment coverage;
  - unassigned words;
  - missing timestamps;
  - excessive unknown-speaker spans;
  - suspicious speaker counts;
  - speaker-label switching;
  - very short turns;
  - very long turns;
  - overlap or timing inconsistencies;
  - gaps in diarisation or speaker assignment;
  - missing or malformed expected files.
- Produce both machine-readable JSON and human-readable Markdown reports.
- Use test mode by default, limiting processing to one eligible debate.
- Skip existing QC reports by default.
- Allow reprocessing with an explicit command-line option.
- Support starting from a specific `corpus_id`.
- Continue processing remaining debates if one QC item fails.
- Record progress and errors in an append-only log file.
- Produce a JSON manifest with run-level metadata and item-level results.
- Write both:
  - a timestamped per-run manifest;
  - a latest manifest overwritten on each run.
- Write a curated QC index for downstream review.
- Exit with status code `0` only when all attempted QC reports succeed or are skipped, and there are no missing inputs or invalid eligible metadata rows.
- Exit with a non-zero status code if one or more attempted QC reports fail, if required inputs are missing, if eligible metadata is invalid, or if there is a configuration/validation error.

---

## 3. Path Resolution Policy

The programme must resolve default paths relative to the directory where `qc_jubilee_debates_speaker_diarisation.py` is located, not relative to the current working directory.

If the script is located at:

```
cl_st1_ph0_carol/qc_jubilee_debates_speaker_diarisation.py
```


then the default speaker-assignment index path:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
```


must resolve to:

```
cl_st1_ph0_carol/corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
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

- `--speaker-index`
- `--alignment-dir`
- `--diarisation-dir`
- `--speaker-transcripts-dir`
- `--output-dir`
- `--log-file`
- `--manifest-file`
- `--qc-index-file`

the programme must preserve that absolute path.

---

## 4. Input / Output Specification

## 4.1 Input

### Speaker-assignment index file

Default path:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
```


The file is expected to be in **NDJSON** format: one JSON object per line.

This file is produced by:

```
assign_speakers_jubilee_debates.py
```


### Required fields

Each valid eligible speaker-assignment index record must contain:

| Field | Type | Description |
|---|---:|---|
| `corpus_id` | string | Stable internal debate identifier |
| `speaker_assignment_status` | string | Speaker-assignment stage status |

The programme should use path fields when present:

| Field | Requirement | Description |
|---|---|---|
| `speaker_words_json_file` | optional | Preferred speaker words JSON path |
| `speaker_words_ndjson_file` | optional | Preferred speaker words NDJSON path |
| `speaker_segments_json_file` | optional | Preferred speaker segments JSON path |
| `speaker_segments_ndjson_file` | optional | Preferred speaker segments NDJSON path |
| `speaker_transcript_text_file` | optional | Preferred plain-text speaker transcript path |
| `aligned_json_file` | optional | Source aligned JSON path |
| `words_ndjson_file` | optional | Source aligned word NDJSON path |
| `diarisation_json_file` | optional | Source diarisation JSON path |
| `segments_ndjson_file` | optional | Source diarisation segment NDJSON path |

If a path field is absent, blank, or unusable, the programme must use fallback paths based on `corpus_id`.

---

## 4.2 Eligible statuses

The programme must process only speaker-assignment records where:

```
speaker_assignment_status = success
```


or:

```
speaker_assignment_status = skipped_existing
```


Records with other statuses must not be processed.

Ineligible statuses include:

```
failed
missing_input
failed_metadata
ignored_alignment_unavailable
ignored_diarisation_unavailable
unmatched_alignment
unmatched_diarisation
interrupted
null
""
missing value
```


Ignored records should be recorded in the manifest, but they are not necessarily run failures unless the programme has no eligible records.

---

## 4.3 Input speaker-assignment files

### Speaker transcripts input directory

Default path:

```
corpus/06_jubilee_debates_speaker_transcripts/
```


Fallback speaker-assignment files are expected as:

```
<speaker_transcripts_dir>/<corpus_id>.speaker_words.json
<speaker_transcripts_dir>/<corpus_id>.speaker_words.ndjson
<speaker_transcripts_dir>/<corpus_id>.speaker_segments.json
<speaker_transcripts_dir>/<corpus_id>.speaker_segments.ndjson
<speaker_transcripts_dir>/<corpus_id>.speaker_transcript.txt
```


Examples:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_words.json
corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_words.ndjson
corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_segments.json
corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_segments.ndjson
corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_transcript.txt
```


The primary QC input should be:

```
<corpus_id>.speaker_words.ndjson
```


because it provides word-level assignment detail.

The secondary QC input should be:

```
<corpus_id>.speaker_segments.ndjson
```


because it provides readable speaker-turn grouping.

JSON files may be used as fallbacks or for richer metadata.

---

## 4.4 Optional upstream input files

The programme should optionally inspect alignment and diarisation files if available.

### Alignment input directory

Default path:

```
corpus/04_jubilee_debates_alignment/
```


Fallback paths:

```
<alignment_dir>/<corpus_id>.aligned.json
<alignment_dir>/<corpus_id>.words.ndjson
```


### Diarisation input directory

Default path:

```
corpus/05_jubilee_debates_diarisation/
```


Fallback paths:

```
<diarisation_dir>/<corpus_id>.diarisation.json
<diarisation_dir>/<corpus_id>.segments.ndjson
```


If optional upstream files are missing but speaker-assignment outputs exist, the programme should still produce a QC report with warnings.

---

## 4.5 Metadata fields to preserve

The programme should preserve these fields in QC outputs and indices when present:

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
| `aligned_json_file` | Aligned JSON path |
| `words_ndjson_file` | Aligned word NDJSON path |
| `diarisation_json_file` | Diarisation JSON path |
| `segments_ndjson_file` | Diarisation segment NDJSON path |
| `speaker_words_json_file` | Speaker words JSON path |
| `speaker_words_ndjson_file` | Speaker words NDJSON path |
| `speaker_segments_json_file` | Speaker segments JSON path |
| `speaker_segments_ndjson_file` | Speaker segments NDJSON path |
| `speaker_transcript_text_file` | Speaker transcript text path |
| `alignment_status` | Alignment stage status |
| `diarisation_status` | Diarisation stage status |
| `speaker_assignment_status` | Speaker-assignment stage status |
| `alignment_run_id` | Alignment run ID |
| `diarisation_run_id` | Diarisation run ID |
| `speaker_assignment_run_id` | Speaker-assignment run ID |
| `selected_by` | Selector |
| `selection_source` | Selection source |
| `notes` | Notes |

---

## 4.6 Output

### QC output directory

Default path:

```
corpus/07_jubilee_debates_qc/
```


The programme must create this directory if it does not already exist.

### Per-debate QC JSON

Each successful QC process must write:

```
<output_dir>/<corpus_id>.qc.json
```


Example:

```
corpus/07_jubilee_debates_qc/jubilee_surrounded_001.qc.json
```


This file contains machine-readable QC metrics, warnings, and recommended review flags.

### Per-debate QC Markdown

Each successful QC process must write:

```
<output_dir>/<corpus_id>.qc.md
```


Example:

```
corpus/07_jubilee_debates_qc/jubilee_surrounded_001.qc.md
```


This file contains a human-readable QC summary.

### Corpus-level QC summary JSON

The programme must write:

```
<output_dir>/jubilee_debates_speaker_diarisation_qc_summary.json
```


### Corpus-level QC summary Markdown

The programme must write:

```
<output_dir>/jubilee_debates_speaker_diarisation_qc_summary.md
```


### Log file

Default path:

```
corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation.log
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
corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation_manifest.json
```


#### Per-run manifest

A timestamped copy must also be written using the run ID.

Filename pattern:

```
qc_jubilee_debates_speaker_diarisation_manifest_<run_id>.json
```


Example:

```
corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation_manifest_20260804T160000Z.json
```


### QC index file

Default path:

```
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_index.ndjson
```


This curated QC index is used for quick review of all processed debates.

---

# 5. Command-line Interface

## 5.1 Default usage

The programme may be run from inside `cl_st1_ph0_carol/`:

```
python qc_jubilee_debates_speaker_diarisation.py
```


or from the project root:

```
python cl_st1_ph0_carol/qc_jubilee_debates_speaker_diarisation.py
```


Both commands should resolve default paths correctly.

Default behaviour:

- speaker-assignment index:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
```


- alignment directory:

```
corpus/04_jubilee_debates_alignment/
```


- diarisation directory:

```
corpus/05_jubilee_debates_diarisation/
```


- speaker transcripts directory:

```
corpus/06_jubilee_debates_speaker_transcripts/
```


- output directory:

```
corpus/07_jubilee_debates_qc/
```


- QC severity threshold for non-zero quality rating:

```
warning
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


- existing complete QC reports are skipped;
- one worker / sequential processing.

---

## 5.2 Required arguments

There are no required command-line arguments if all defaults are used.

---

## 5.3 Optional arguments

### Speaker-assignment index

```
--speaker-index PATH
```


Default:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
```


Description:

Path to the curated speaker-assignment NDJSON index from the speaker-assignment stage.

---

### Alignment directory

```
--alignment-dir PATH
```


Default:

```
corpus/04_jubilee_debates_alignment/
```


Description:

Fallback directory containing aligned JSON and aligned word NDJSON files.

---

### Diarisation directory

```
--diarisation-dir PATH
```


Default:

```
corpus/05_jubilee_debates_diarisation/
```


Description:

Fallback directory containing diarisation JSON and diarisation segment NDJSON files.

---

### Speaker transcripts directory

```
--speaker-transcripts-dir PATH
```


Default:

```
corpus/06_jubilee_debates_speaker_transcripts/
```


Description:

Fallback directory containing speaker-assignment outputs.

---

### Output directory

```
--output-dir PATH
```


Default:

```
corpus/07_jubilee_debates_qc/
```


Description:

Directory where QC JSON, QC Markdown, logs, manifests, and QC index are written.

---

### Gap warning threshold

```
--gap-warning-threshold SECONDS
```


Default:

```
5.0
```


Description:

Minimum duration of a gap in speaker-assigned word coverage or diarisation coverage to report as a warning.

---

### Long unknown span threshold

```
--unknown-span-warning-threshold SECONDS
```


Default:

```
10.0
```


Description:

Minimum duration of a continuous `UNKNOWN_SPEAKER` span to report as a warning.

---

### High unassigned word ratio threshold

```
--unassigned-word-ratio-warning-threshold FLOAT
```


Default:

```
0.05
```


Description:

Warn if more than this fraction of aligned words are unassigned or assigned to the unknown speaker label.

For example:

```
0.05
```


means warn when more than 5% of words are unassigned.

---

### Low diarisation coverage threshold

```
--diarisation-coverage-warning-threshold FLOAT
```


Default:

```
0.60
```


Description:

Warn if diarised speech coverage is below this fraction of the expected audio or transcript duration.

---

### High diarisation coverage threshold

```
--diarisation-coverage-high-warning-threshold FLOAT
```


Default:

```
0.98
```


Description:

Warn if diarised speech coverage is unexpectedly high. Near-total coverage may indicate that non-speech regions were over-labelled as speech.

---

### Minimum expected speakers

```
--min-expected-speakers N
```


Default:

```
3
```


Description:

Warn if detected or assigned speaker count is lower than this value.

For `Surrounded` debates, very low speaker counts are suspicious.

---

### Maximum expected speakers

```
--max-expected-speakers N
```


Default:

```
35
```


Description:

Warn if detected or assigned speaker count is higher than this value.

For `Surrounded` debates, extremely high speaker counts may indicate over-segmentation.

---

### Short turn threshold

```
--short-turn-threshold SECONDS
```


Default:

```
0.5
```


Description:

Speaker transcript segments shorter than this threshold are counted as short turns.

---

### High short-turn ratio threshold

```
--short-turn-ratio-warning-threshold FLOAT
```


Default:

```
0.25
```


Description:

Warn if more than this fraction of speaker segments are shorter than `--short-turn-threshold`.

A high short-turn ratio may indicate excessive speaker switching or diarisation fragmentation.

---

### Long turn threshold

```
--long-turn-threshold SECONDS
```


Default:

```
120.0
```


Description:

Speaker transcript segments longer than this threshold are counted and reported.

Long turns are not necessarily errors, but in debate data they may require review.

---

### Speaker imbalance threshold

```
--speaker-imbalance-warning-threshold FLOAT
```


Default:

```
0.65
```


Description:

Warn if the top speaker accounts for more than this fraction of assigned words or assigned speech duration.

For some `Surrounded` debates, one featured speaker may dominate, so this is a warning rather than an error.

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

### Reprocess existing QC reports

```
--reprocess
```


Default:

```
False
```


When omitted, debates with both per-debate QC outputs present are skipped.

When provided, QC reports are generated again and existing outputs are overwritten.

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
python qc_jubilee_debates_speaker_diarisation.py \
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
corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation.log
```


---

### Manifest file

```
--manifest-file PATH
```


Default:

```
corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation_manifest.json
```


---

### QC index file

```
--qc-index-file PATH
```


Default:

```
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_index.ndjson
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

---

### Timeout

```
--timeout SECONDS
```


Default suggestion:

```
3600
```


A one-hour per-item timeout is generous for QC reporting. Strict timeout enforcement may require subprocess isolation; the first implementation may record the value without hard enforcement.

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

### Default one-debate QC test

```
python qc_jubilee_debates_speaker_diarisation.py
```


### Test from a specific corpus ID

```
python qc_jubilee_debates_speaker_diarisation.py \
  --test-limit 1 \
  --start-corpus-id jubilee_surrounded_003
```


### Full QC run

```
python qc_jubilee_debates_speaker_diarisation.py --no-test-mode
```


### Recreate all QC reports

```
python qc_jubilee_debates_speaker_diarisation.py \
  --no-test-mode \
  --reprocess
```


### Full run with stricter unassigned-word warning

```
python qc_jubilee_debates_speaker_diarisation.py \
  --no-test-mode \
  --unassigned-word-ratio-warning-threshold 0.02
```


### Local or EC2 run

This stage does not require a GPU. It can run locally or on EC2 after Stages 1–4 have produced speaker-attributed outputs.

```
python qc_jubilee_debates_speaker_diarisation.py --no-test-mode
```


---

# 6. Argument Validation

The programme must fail fast with a clear message if:

- the speaker-assignment index file does not exist;
- the speaker-assignment index path is not a file;
- the speaker-assignment index is unreadable;
- the speaker-assignment index contains invalid JSON lines;
- no eligible speaker-assignment records are found;
- the alignment directory does not exist;
- the alignment directory is not a directory;
- the diarisation directory does not exist;
- the diarisation directory is not a directory;
- the speaker transcripts directory does not exist;
- the speaker transcripts directory is not a directory;
- the output directory cannot be created;
- `--gap-warning-threshold` is less than zero;
- `--unknown-span-warning-threshold` is less than zero;
- `--unassigned-word-ratio-warning-threshold` is less than `0.0` or greater than `1.0`;
- `--diarisation-coverage-warning-threshold` is less than `0.0` or greater than `1.0`;
- `--diarisation-coverage-high-warning-threshold` is less than `0.0` or greater than `1.0`;
- low coverage threshold is greater than high coverage threshold;
- `--min-expected-speakers` is less than or equal to zero;
- `--max-expected-speakers` is less than or equal to zero;
- `--min-expected-speakers` is greater than `--max-expected-speakers`;
- `--short-turn-threshold` is less than zero;
- `--short-turn-ratio-warning-threshold` is less than `0.0` or greater than `1.0`;
- `--long-turn-threshold` is less than or equal to zero;
- `--speaker-imbalance-warning-threshold` is less than `0.0` or greater than `1.0`;
- `--test-limit` is less than or equal to zero;
- `--workers` is less than or equal to zero;
- `--workers` is not `1`;
- `--timeout` is less than or equal to zero;
- `--max-retries` is negative;
- `--retry-delay` is negative;
- `--start-corpus-id` is provided but empty;
- `--start-corpus-id` is provided but not found among eligible records.

A validation error should:

- be printed clearly to the console;
- be written to the log if logging has already been configured;
- cause the programme to exit with code `2`.

---

# 7. Environment and Configuration

## 7.1 Runtime environment

This stage is a JSON/NDJSON analytics and reporting step.

It does **not** require:

- CUDA;
- GPU;
- WhisperX;
- pyannote.audio;
- Hugging Face authentication.

It can run in a normal Python environment.

Recommended environment:

```
Python: 3.11
Workers: 1
GPU required: No
```


It may be run either:

- locally after copying Stages 1–4 outputs back from EC2; or
- on EC2 for convenience as part of the full pipeline.

## 7.2 Required Python packages

The first implementation should require only Python standard-library modules where possible:

```
argparse
json
logging
sys
time
datetime
pathlib
statistics
collections
typing
```


Optional:

```
tqdm
```


No ML packages are required for this programme.

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
   - Record environment metadata.

2. **Speaker-assignment index loading**
   - Load speaker-assignment index from NDJSON.
   - Parse each line as a JSON object.
   - Count total records.
   - Select only eligible records.
   - Validate required fields.
   - Record ignored and invalid rows.
   - Preserve input order.

3. **Planning**
   - Apply `--start-corpus-id`, if provided.
   - Resolve speaker-assignment output paths.
   - Resolve optional upstream alignment paths.
   - Resolve optional upstream diarisation paths.
   - Compute QC output paths:
     - `<output_dir>/<corpus_id>.qc.json`;
     - `<output_dir>/<corpus_id>.qc.md`.
   - Check missing required speaker-assignment inputs.
   - Skip if QC outputs already exist and `--reprocess` is not enabled.
   - Apply test-mode limit to planned QC items.

4. **Execution**
   - For each planned item:
     - load speaker words;
     - load speaker segments;
     - load optional alignment words;
     - load optional diarisation segments;
     - compute QC metrics;
     - generate warnings and review flags;
     - assign an overall QC rating;
     - write per-debate QC JSON;
     - write per-debate QC Markdown;
     - capture timing, warnings, and errors;
     - retry according to `--max-retries`;
     - mark item as `success` or `failed`.

5. **Corpus-level summary generation**
   - Aggregate per-debate QC metrics.
   - Write corpus-level QC summary JSON.
   - Write corpus-level QC summary Markdown.

6. **QC index generation**
   - Combine source metadata and QC metadata.
   - Write curated NDJSON QC index.

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
    """Parse command-line arguments for the QC programme."""
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
def load_speaker_assignment_index(index_path: Path) -> tuple[list[dict], list[dict], list[dict], int]:
    """Load and filter the speaker-assignment NDJSON index."""
```


```python
def resolve_qc_input_paths(record: dict, alignment_dir: Path, diarisation_dir: Path, speaker_transcripts_dir: Path) -> dict[str, Path | None]:
    """Resolve speaker-assignment and optional upstream input paths."""
```


```python
def plan_qc_reports(
    records: list[dict],
    alignment_dir: Path,
    diarisation_dir: Path,
    speaker_transcripts_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_corpus_id: str | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Create planned, skipped, and missing-input QC records."""
```


```python
def load_ndjson_records(path: Path) -> list[dict]:
    """Load a line-oriented NDJSON file."""
```


```python
def load_json_object(path: Path) -> dict:
    """Load a JSON object file."""
```


```python
def compute_word_assignment_metrics(speaker_words: list[dict], config: dict) -> dict:
    """Compute word-level speaker assignment QC metrics."""
```


```python
def compute_speaker_segment_metrics(speaker_segments: list[dict], config: dict) -> dict:
    """Compute speaker-segment and turn-taking QC metrics."""
```


```python
def compute_diarisation_metrics(diarisation_segments: list[dict], duration_seconds: float | None, config: dict) -> dict:
    """Compute diarisation coverage and speaker interval QC metrics."""
```


```python
def compute_alignment_metrics(alignment_words: list[dict], duration_seconds: float | None, config: dict) -> dict:
    """Compute alignment word coverage and timestamp QC metrics."""
```


```python
def generate_qc_warnings(metrics: dict, config: dict) -> list[dict]:
    """Generate structured QC warnings from computed metrics."""
```


```python
def assign_qc_rating(warnings: list[dict], metrics: dict) -> str:
    """Assign an overall QC rating for one debate."""
```


```python
def build_qc_json(item: dict, metrics: dict, warnings: list[dict], rating: str, run_metadata: dict) -> dict:
    """Build the per-debate QC JSON object."""
```


```python
def render_qc_markdown(qc_json: dict) -> str:
    """Render a human-readable Markdown QC report."""
```


```python
def build_corpus_summary(qc_results: list[dict], run_metadata: dict) -> dict:
    """Build corpus-level QC summary JSON."""
```


```python
def render_corpus_summary_markdown(summary: dict) -> str:
    """Render corpus-level QC summary Markdown."""
```


```python
def write_qc_outputs(qc_json: dict, qc_markdown: str, qc_json_path: Path, qc_md_path: Path) -> None:
    """Write per-debate QC JSON and Markdown outputs."""
```


```python
def write_qc_index(index_records: list[dict], qc_index_file: Path) -> None:
    """Write curated NDJSON QC index."""
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
    """Run the batch Jubilee debate speaker diarisation QC workflow and return an exit code."""
```


---

# 9. QC Metrics Specification

## 9.1 Core per-debate metrics

Each per-debate QC report should compute, where possible:

| Metric | Description |
|---|---|
| `audio_duration_seconds` | Expected audio/source duration |
| `alignment_word_count` | Number of aligned word records |
| `aligned_word_count` | Words with valid timing |
| `unaligned_word_count` | Words without usable timing |
| `speaker_word_count` | Number of speaker-assigned word records |
| `assigned_word_count` | Words assigned to a diarised speaker |
| `unassigned_word_count` | Words not assigned to a diarised speaker |
| `unknown_speaker_word_count` | Words assigned to unknown speaker label |
| `speaker_segment_count` | Number of speaker-attributed transcript segments |
| `diarisation_segment_count` | Number of diarisation intervals |
| `detected_speaker_count` | Number of diarised speaker labels |
| `assigned_speaker_count` | Number of speaker labels used in assigned transcript |
| `total_diarised_speech_seconds` | Sum of diarisation interval durations |
| `diarisation_coverage_ratio` | Diarised speech seconds divided by duration |
| `speaker_assignment_coverage_ratio` | Assigned words divided by total speaker words |
| `unknown_word_ratio` | Unknown speaker words divided by total speaker words |
| `missing_word_timing_ratio` | Words without valid timing divided by total words |
| `short_turn_count` | Number of short speaker segments |
| `short_turn_ratio` | Short turns divided by speaker segment count |
| `long_turn_count` | Number of long speaker segments |
| `top_speaker_by_words` | Speaker with most assigned words |
| `top_speaker_word_ratio` | Top speaker word count divided by assigned words |
| `top_speaker_by_duration` | Speaker with most attributed duration |
| `top_speaker_duration_ratio` | Top speaker duration divided by assigned duration |
| `speaker_switch_count` | Number of changes between adjacent speaker segments |
| `average_segment_duration` | Mean speaker segment duration |
| `median_segment_duration` | Median speaker segment duration |
| `average_words_per_segment` | Mean words per speaker segment |
| `long_unknown_span_count` | Count of long continuous unknown-speaker spans |
| `long_gap_count` | Count of long timing gaps |
| `timing_anomaly_count` | Count of invalid or non-monotonic timestamp problems |

---

## 9.2 Alignment QC metrics

If alignment files are available, compute:

- total word count;
- words with start and end timestamps;
- words missing start or end;
- words with `end <= start`;
- earliest word timestamp;
- latest word timestamp;
- transcript time span;
- transcript coverage relative to expected duration;
- large gaps between aligned words;
- non-monotonic word timestamps;
- unusually long word durations.

Suggested warning conditions:

| Condition | Suggested severity |
|---|---|
| No aligned words | `error` |
| More than 5% words missing timing | `warning` |
| Non-monotonic word timestamps | `warning` |
| Transcript coverage below 50% of expected duration | `warning` |
| Very large word gaps | `review` |

---

## 9.3 Diarisation QC metrics

If diarisation files are available, compute:

- diarisation segment count;
- detected speaker count;
- total diarised speech seconds;
- coverage ratio relative to expected duration;
- speaker duration distribution;
- very short diarisation intervals;
- very long diarisation intervals;
- overlaps between diarisation intervals;
- large gaps between diarisation intervals;
- speaker fragmentation by speaker label.

Suggested warning conditions:

| Condition | Suggested severity |
|---|---|
| No diarisation segments | `error` |
| Speaker count below minimum expected speakers | `warning` |
| Speaker count above maximum expected speakers | `warning` |
| Diarisation coverage below threshold | `warning` |
| Diarisation coverage above high threshold | `review` |
| Excessive short diarisation intervals | `review` |
| Large diarisation gaps | `review` |
| Overlapping diarisation intervals | `review` |

Overlaps are not always errors because debate speech may overlap, but they should be reported.

---

## 9.4 Speaker-assignment QC metrics

For speaker-assigned words and segments, compute:

- total speaker word records;
- assigned speaker word records;
- unknown speaker word records;
- unassigned or failed-assignment word records;
- assignment status distribution;
- assigned speaker distribution by word count;
- assigned speaker distribution by duration;
- unknown-speaker spans;
- speaker segment count;
- speaker segment duration distribution;
- short-turn ratio;
- long-turn count;
- speaker switches;
- repeated rapid switches between the same labels;
- consistency between speaker word counts and speaker segment word counts.

Suggested warning conditions:

| Condition | Suggested severity |
|---|---|
| No speaker words | `error` |
| No speaker segments | `error` |
| Unknown/unassigned word ratio above threshold | `warning` |
| Long unknown-speaker spans | `warning` |
| Very low assigned speaker count | `warning` |
| Very high assigned speaker count | `warning` |
| High short-turn ratio | `review` |
| Extreme top-speaker imbalance | `review` |
| Speaker word count differs from segment word totals | `warning` |

---

## 9.5 Overall QC rating

Each debate should receive an overall rating.

Suggested values:

| Rating | Meaning |
|---|---|
| `pass` | No serious issues detected |
| `review` | Usable, but manual inspection recommended |
| `warning` | Significant issues likely affecting analysis |
| `fail` | Missing or severely malformed outputs |
| `unknown` | Insufficient data to evaluate |

Suggested logic:

- `fail` if any critical input is missing or no usable speaker words/segments exist.
- `warning` if one or more high-impact warnings are present.
- `review` if only moderate review flags are present.
- `pass` if no warnings or review flags are present.
- `unknown` if insufficient optional data prevents meaningful evaluation but required files exist.

The programme should keep this rating heuristic transparent in the JSON output.

---

# 10. Output Data Design

## 10.1 Per-debate QC JSON

Each `<corpus_id>.qc.json` should use a structure similar to:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "qc_status": "success",
  "qc_rating": "review",
  "metadata": {
    "title_selected": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)",
    "youtube_id": "WV29R1M25n8",
    "duration_seconds": 5427,
    "duration_string": "1:30:27"
  },
  "input_paths": {
    "speaker_words_ndjson_file": "corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_words.ndjson",
    "speaker_segments_ndjson_file": "corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_segments.ndjson",
    "words_ndjson_file": "corpus/04_jubilee_debates_alignment/jubilee_surrounded_001.words.ndjson",
    "diarisation_segments_ndjson_file": "corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.segments.ndjson"
  },
  "metrics": {
    "audio_duration_seconds": 5427,
    "alignment": {
      "word_count": 14500,
      "aligned_word_count": 14200,
      "unaligned_word_count": 300,
      "missing_word_timing_ratio": 0.0207
    },
    "diarisation": {
      "segment_count": 1450,
      "detected_speaker_count": 18,
      "total_diarised_speech_seconds": 4820.35,
      "diarisation_coverage_ratio": 0.8883
    },
    "speaker_assignment": {
      "speaker_word_count": 14500,
      "assigned_word_count": 14100,
      "unknown_speaker_word_count": 400,
      "unknown_word_ratio": 0.0276,
      "assigned_speaker_count": 18,
      "speaker_segment_count": 980
    },
    "turn_taking": {
      "short_turn_count": 180,
      "short_turn_ratio": 0.1837,
      "long_turn_count": 4,
      "speaker_switch_count": 910
    },
    "speaker_distribution": {
      "top_speaker_by_words": "SPEAKER_00",
      "top_speaker_word_ratio": 0.31,
      "top_speaker_by_duration": "SPEAKER_00",
      "top_speaker_duration_ratio": 0.34
    }
  },
  "warnings": [
    {
      "code": "short_turn_ratio_review",
      "severity": "review",
      "message": "Short speaker-turn ratio is elevated; diarisation may be fragmented.",
      "value": 0.1837,
      "threshold": 0.25
    }
  ],
  "recommendations": [
    "Inspect the plain-text speaker transcript around long UNKNOWN_SPEAKER spans.",
    "Review top speakers by duration to confirm diarisation is plausible."
  ],
  "run": {
    "qc_run_id": "20260804T160000Z",
    "qc_at_utc": "2026-08-04T16:00:00Z"
  },
  "error": null
}
```


---

## 10.2 Per-debate QC Markdown

Each `<corpus_id>.qc.md` should include:

```markdown
# QC Report — `jubilee_surrounded_001`

## Summary

| Field | Value |
|---|---:|
| QC rating | review |
| Duration | 1:30:27 |
| Detected speakers | 18 |
| Assigned speakers | 18 |
| Speaker words | 14,500 |
| Assigned words | 14,100 |
| Unknown speaker words | 400 |
| Unknown word ratio | 2.76% |
| Diarisation coverage | 88.83% |

## Warnings

| Severity | Code | Message |
|---|---|---|
| review | short_turn_ratio_review | Short speaker-turn ratio is elevated; diarisation may be fragmented. |

## Speaker Distribution

| Speaker | Words | Word % | Duration seconds | Duration % |
|---|---:|---:|---:|---:|
| SPEAKER_00 | 4,371 | 31.00% | 1,638.92 | 34.00% |

## Recommended Manual Checks

- Inspect long `UNKNOWN_SPEAKER` spans.
- Spot-check rapid speaker switches.
- Compare detected speaker count against expected debate format.
```


The Markdown should be readable in a normal text editor and in GitHub-style renderers.

---

## 10.3 Corpus-level QC summary JSON

The corpus-level JSON should include:

```json
{
  "run": {
    "qc_run_id": "20260804T160000Z",
    "qc_at_utc": "2026-08-04T16:00:00Z"
  },
  "summary": {
    "debates_evaluated": 5,
    "passed": 2,
    "review": 2,
    "warning": 1,
    "failed": 0,
    "unknown": 0,
    "total_audio_duration_seconds": 29588,
    "total_speaker_words": 72000,
    "total_assigned_words": 69000,
    "total_unknown_speaker_words": 3000,
    "overall_unknown_word_ratio": 0.0417
  },
  "items": [
    {
      "corpus_id": "jubilee_surrounded_001",
      "qc_rating": "review",
      "detected_speaker_count": 18,
      "unknown_word_ratio": 0.0276,
      "diarisation_coverage_ratio": 0.8883,
      "warning_count": 1
    }
  ],
  "common_warnings": [
    {
      "code": "short_turn_ratio_review",
      "count": 3
    }
  ]
}
```


---

## 10.4 Corpus-level QC summary Markdown

The corpus-level Markdown should include:

- run metadata;
- count of debates evaluated;
- table of per-debate QC ratings;
- aggregate unknown word ratio;
- aggregate speaker counts;
- common warnings;
- recommended next actions.

Example:

```markdown
# Jubilee Debate Speaker Diarisation QC Summary

## Run

| Field | Value |
|---|---|
| QC run ID | 20260804T160000Z |
| Debates evaluated | 5 |

## Overall Results

| Rating | Count |
|---|---:|
| pass | 2 |
| review | 2 |
| warning | 1 |
| fail | 0 |

## Debate Summary

| Corpus ID | Rating | Speakers | Unknown word % | Diarisation coverage | Warnings |
|---|---|---:|---:|---:|---:|
| jubilee_surrounded_001 | review | 18 | 2.76% | 88.83% | 1 |

## Recommended Next Actions

- Review debates rated `warning` first.
- Spot-check debates with high unknown-speaker word ratios.
- Inspect debates with unexpectedly low or high speaker counts.
```


---

## 10.5 QC index

The programme must write:

```
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_index.ndjson
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
| `qc_json_file` | Per-debate QC JSON path |
| `qc_markdown_file` | Per-debate QC Markdown path |
| `qc_status` | QC processing status |
| `qc_rating` | Overall quality rating |
| `qc_run_id` | Run ID |
| `qc_at_utc` | Timestamp |
| `detected_speaker_count` | Number of diarised speakers |
| `assigned_speaker_count` | Number of assigned speakers |
| `speaker_word_count` | Total speaker word records |
| `assigned_word_count` | Assigned word count |
| `unknown_speaker_word_count` | Unknown speaker word count |
| `unknown_word_ratio` | Unknown speaker word ratio |
| `diarisation_coverage_ratio` | Diarisation coverage |
| `speaker_segment_count` | Speaker transcript segment count |
| `warning_count` | Number of QC warnings |
| `review_flag_count` | Number of review flags |
| `error_count` | Number of error-level QC warnings |
| `speaker_assignment_status` | Previous stage status |
| `speaker_assignment_run_id` | Previous stage run ID |
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
    "run_id": "20260804T160000Z",
    "tool_name": "qc_jubilee_debates_speaker_diarisation.py",
    "tool_version": "v1",
    "start_time": "2026-08-04T16:00:00Z",
    "end_time": "2026-08-04T16:02:00Z",
    "test_mode": true,
    "test_limit": 1,
    "reprocess": false,
    "workers": 1,
    "speaker_index_path": "corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson",
    "alignment_dir": "corpus/04_jubilee_debates_alignment",
    "diarisation_dir": "corpus/05_jubilee_debates_diarisation",
    "speaker_transcripts_dir": "corpus/06_jubilee_debates_speaker_transcripts",
    "output_dir": "corpus/07_jubilee_debates_qc",
    "qc_index_file": "corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_index.ndjson",
    "log_file": "corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation.log",
    "manifest_file": "corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation_manifest.json",
    "config": {
      "gap_warning_threshold": 5.0,
      "unknown_span_warning_threshold": 10.0,
      "unassigned_word_ratio_warning_threshold": 0.05,
      "diarisation_coverage_warning_threshold": 0.6,
      "diarisation_coverage_high_warning_threshold": 0.98,
      "min_expected_speakers": 3,
      "max_expected_speakers": 35,
      "short_turn_threshold": 0.5,
      "short_turn_ratio_warning_threshold": 0.25,
      "long_turn_threshold": 120.0,
      "speaker_imbalance_warning_threshold": 0.65,
      "timeout_seconds": 3600,
      "max_retries": 1,
      "retry_delay_seconds": 5,
      "start_corpus_id": null
    },
    "environment": {
      "python_version": "3.11.x"
    },
    "summary": {
      "speaker_index_records": 5,
      "eligible_speaker_assignment_records": 5,
      "ignored_records": 0,
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
      "qc_json_path": "corpus/07_jubilee_debates_qc/jubilee_surrounded_001.qc.json",
      "qc_markdown_path": "corpus/07_jubilee_debates_qc/jubilee_surrounded_001.qc.md",
      "status": "success",
      "qc_rating": "review",
      "error": null,
      "retries": 0,
      "duration_seconds": 2.4,
      "start_time": "2026-08-04T16:01:00Z",
      "end_time": "2026-08-04T16:01:02Z",
      "warning_count": 1,
      "detected_speaker_count": 18,
      "unknown_word_ratio": 0.0276,
      "diarisation_coverage_ratio": 0.8883,
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
| `success` | QC report completed successfully |
| `failed` | QC report was attempted but failed |
| `skipped_existing` | QC outputs already existed and `--reprocess` was not enabled |
| `missing_input` | Required speaker-assignment input was missing |
| `failed_metadata` | Eligible speaker-assignment index row was invalid |
| `ignored_speaker_assignment_unavailable` | Record ignored because speaker assignment was not available |
| `interrupted` | Processing stopped due to keyboard interruption |

---

# 12. Logging Specification

The programme must write an append-only UTF-8 log file.

Default:

```
corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation.log
```


Log format:

```
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```


Required log events:

- startup;
- run ID;
- parsed configuration;
- speaker-assignment index path;
- alignment directory;
- diarisation directory;
- speaker transcripts directory;
- output directory;
- test mode status;
- test limit;
- reprocess setting;
- start corpus ID;
- QC threshold settings;
- number of speaker-assignment index records read;
- number of eligible records;
- number of ignored records;
- number of invalid metadata rows;
- number of planned QC reports;
- each skipped existing QC report;
- each missing input;
- each QC attempt;
- each retry;
- each success;
- each failure;
- QC rating per item;
- warning count per item;
- corpus summary write paths;
- QC index write path;
- manifest write paths;
- final summary;
- configuration errors;
- keyboard interruptions.

---

# 13. Error Handling and Resiliency

## 13.1 Configuration errors

Configuration errors must stop the programme before QC begins.

Examples:

- speaker-assignment index missing;
- speaker-assignment index unreadable;
- invalid JSON line in speaker-assignment index;
- no eligible records;
- required input directory missing;
- invalid command-line arguments;
- start corpus ID not found.

Exit code:

```
2
```


---

## 13.2 Per-item errors

Per-item errors must not stop the full batch.

Examples:

- speaker words file missing;
- speaker segments file missing;
- malformed speaker words;
- malformed speaker segments;
- no usable speaker word data;
- no usable speaker segment data;
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

## 13.3 Optional upstream missing files

If optional alignment or diarisation files are missing, but required speaker-assignment files are available:

- do not fail the item;
- include a warning in the QC report;
- record the missing optional file in `input_availability`;
- continue with metrics that can be computed.

---

## 13.4 Keyboard interruption

If interrupted with `Ctrl+C`, the programme must:

- stop processing;
- mark run as interrupted;
- write partial manifest where possible;
- write partial QC index where possible;
- log interruption;
- exit with code:

```
130
```


---

## 13.5 Exit codes

| Exit code | Meaning |
|---:|---|
| `0` | Completed with no failed attempted QC reports, no missing required inputs, and no invalid eligible metadata rows |
| `1` | Completed, but one or more QC reports failed, required source inputs were missing, or eligible metadata rows were invalid |
| `2` | Configuration or validation error |
| `130` | Interrupted by user |

Skipped existing files are not failures.

QC ratings of `review` or `warning` are **not process failures**. They indicate data-quality concerns, not execution failure.

---

# 14. Docstrings and In-code Documentation

## 14.1 Module-level docstring

At the top of `qc_jubilee_debates_speaker_diarisation.py`, include a module-level docstring explaining:

- purpose of programme;
- expected input speaker-assignment index;
- source speaker transcript directory;
- optional alignment and diarisation input directories;
- QC output directory;
- key metrics produced;
- default test mode;
- resumability behaviour;
- start-corpus-ID support;
- QC-only scope;
- example commands.

Suggested module docstring:

```python
"""
Produce QC reports for Jubilee debate speaker diarisation outputs.

This script reads the curated Jubilee debate speaker-assignment index, selects
records whose speaker-attributed transcript outputs are available, and computes
quality-control metrics for alignment, diarisation, and speaker assignment.

The primary inputs are speaker word and speaker segment outputs from
assign_speakers_jubilee_debates.py. Alignment and diarisation files are also
inspected when available to compute additional coverage and timing diagnostics.

Outputs are written to the QC output directory as per-debate JSON and Markdown
reports, plus corpus-level JSON and Markdown summaries. The reports include
metrics such as word assignment coverage, unknown-speaker ratio, detected speaker
count, diarisation coverage, short-turn ratio, speaker distribution, timing
anomalies, and review warnings.

By default, the script runs in test mode and attempts only the first planned
debate. Existing complete QC outputs are skipped unless --reprocess is provided,
making the script safe to re-run.

Use --start-corpus-id to resume planning from a specific debate onward.

This programme performs QC reporting only. It does not transcribe, align,
diarise, assign speakers, identify real speakers, or modify upstream outputs.

Example:
    python qc_jubilee_debates_speaker_diarisation.py

Full run:
    python qc_jubilee_debates_speaker_diarisation.py --no-test-mode

Full run from a specific debate:
    python qc_jubilee_debates_speaker_diarisation.py --no-test-mode --start-corpus-id jubilee_surrounded_003
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
- `load_speaker_assignment_index`
- `resolve_qc_input_paths`
- `plan_qc_reports`
- `load_ndjson_records`
- `load_json_object`
- `compute_word_assignment_metrics`
- `compute_speaker_segment_metrics`
- `compute_diarisation_metrics`
- `compute_alignment_metrics`
- `generate_qc_warnings`
- `assign_qc_rating`
- `build_qc_json`
- `render_qc_markdown`
- `build_corpus_summary`
- `render_corpus_summary_markdown`
- `write_qc_outputs`
- `write_qc_index`
- `write_manifests`
- `main`

---

# 15. Suggested Constants

```python
TOOL_NAME = "qc_jubilee_debates_speaker_diarisation.py"
TOOL_VERSION = "v1"

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_SPEAKER_INDEX_PATH = (
    "corpus/06_jubilee_debates_speaker_transcripts/"
    "jubilee_debates_speaker_assignment_index.ndjson"
)

DEFAULT_ALIGNMENT_DIR = "corpus/04_jubilee_debates_alignment"
DEFAULT_DIARISATION_DIR = "corpus/05_jubilee_debates_diarisation"
DEFAULT_SPEAKER_TRANSCRIPTS_DIR = "corpus/06_jubilee_debates_speaker_transcripts"
DEFAULT_OUTPUT_DIR = "corpus/07_jubilee_debates_qc"

DEFAULT_LOG_FILE = (
    "corpus/07_jubilee_debates_qc/"
    "qc_jubilee_debates_speaker_diarisation.log"
)
DEFAULT_MANIFEST_FILE = (
    "corpus/07_jubilee_debates_qc/"
    "qc_jubilee_debates_speaker_diarisation_manifest.json"
)
DEFAULT_QC_INDEX_FILE = (
    "corpus/07_jubilee_debates_qc/"
    "jubilee_debates_speaker_diarisation_qc_index.ndjson"
)

DEFAULT_CORPUS_SUMMARY_JSON_FILE = (
    "corpus/07_jubilee_debates_qc/"
    "jubilee_debates_speaker_diarisation_qc_summary.json"
)
DEFAULT_CORPUS_SUMMARY_MD_FILE = (
    "corpus/07_jubilee_debates_qc/"
    "jubilee_debates_speaker_diarisation_qc_summary.md"
)

DEFAULT_GAP_WARNING_THRESHOLD_SECONDS = 5.0
DEFAULT_UNKNOWN_SPAN_WARNING_THRESHOLD_SECONDS = 10.0
DEFAULT_UNASSIGNED_WORD_RATIO_WARNING_THRESHOLD = 0.05
DEFAULT_DIARISATION_COVERAGE_WARNING_THRESHOLD = 0.60
DEFAULT_DIARISATION_COVERAGE_HIGH_WARNING_THRESHOLD = 0.98
DEFAULT_MIN_EXPECTED_SPEAKERS = 3
DEFAULT_MAX_EXPECTED_SPEAKERS = 35
DEFAULT_SHORT_TURN_THRESHOLD_SECONDS = 0.5
DEFAULT_SHORT_TURN_RATIO_WARNING_THRESHOLD = 0.25
DEFAULT_LONG_TURN_THRESHOLD_SECONDS = 120.0
DEFAULT_SPEAKER_IMBALANCE_WARNING_THRESHOLD = 0.65

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 1
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

OUTPUT_QC_JSON_EXTENSION = ".qc.json"
OUTPUT_QC_MARKDOWN_EXTENSION = ".qc.md"

ELIGIBLE_SPEAKER_ASSIGNMENT_STATUSES = ("success", "skipped_existing")

QC_RATINGS = ("pass", "review", "warning", "fail", "unknown")
WARNING_SEVERITIES = ("info", "review", "warning", "error")
```


---

# 16. Development Notes

## 16.1 Initial implementation scope

The first implementation should prioritise:

- correct sequential execution;
- robust speaker-assignment index reading;
- eligibility filtering by `speaker_assignment_status`;
- robust input path resolution;
- loading speaker words from `.speaker_words.ndjson`;
- loading speaker segments from `.speaker_segments.ndjson`;
- fallback loading from JSON where practical;
- useful per-debate QC metrics;
- structured QC warnings;
- readable per-debate Markdown reports;
- corpus-level JSON and Markdown summaries;
- reliable QC index output;
- reliable logging;
- robust manifest writing;
- safe resumability;
- `--start-corpus-id` support;
- clear handling of optional missing upstream files.

Parallel processing should not be implemented initially.

## 16.2 Interpretation note

QC warnings are not automatic proof that the output is unusable.

For Jubilee `Surrounded` debates:

- many speakers are expected;
- interruptions are expected;
- overlapping speech is expected;
- the featured speaker may dominate;
- short turns may be common.

The QC report should therefore distinguish:

- execution failure;
- likely data-quality error;
- review recommendation;
- expected-but-noteworthy debate behaviour.

## 16.3 Human review note

The programme should make manual review easier by identifying:

- debates with suspicious speaker counts;
- debates with high unknown-speaker ratios;
- debates with long unknown spans;
- debates with excessive short turns;
- debates with unusual diarisation coverage;
- top speakers by word count and duration.

It should not try to solve these issues automatically.

---

# 17. Acceptance Criteria

The programme is considered complete when:

1. Running from inside `cl_st1_ph0_carol/` works:

```
python qc_jubilee_debates_speaker_diarisation.py
```


2. Running from project root works:

```
python cl_st1_ph0_carol/qc_jubilee_debates_speaker_diarisation.py
```


3. Default paths are resolved relative to the programme directory.

4. It reads:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
```


5. It processes only records where speaker-assignment outputs are available.

6. It uses source paths from index records when present and usable.

7. It falls back to:

```
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_transcript.txt
```


8. It optionally uses upstream fallback files from:

```
corpus/04_jubilee_debates_alignment/
corpus/05_jubilee_debates_diarisation/
```


9. It creates the output directory if needed:

```
corpus/07_jubilee_debates_qc/
```


10. Each successful QC process writes:

```
corpus/07_jubilee_debates_qc/<corpus_id>.qc.json
corpus/07_jubilee_debates_qc/<corpus_id>.qc.md
```


11. The programme writes corpus-level summary files:

```
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_summary.json
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_summary.md
```


12. The programme computes word-assignment coverage metrics.

13. The programme computes unknown-speaker metrics.

14. The programme computes speaker-count metrics.

15. The programme computes diarisation coverage metrics when diarisation data is available.

16. The programme computes alignment timing metrics when alignment data is available.

17. The programme computes speaker segment / turn-taking metrics.

18. The programme generates structured warnings.

19. The programme assigns an overall QC rating.

20. Existing complete QC outputs are skipped unless `--reprocess` is used.

21. If only one QC output exists, the item is treated as incomplete and planned for QC generation.

22. Failed QC items do not stop the full batch.

23. Missing required speaker-assignment inputs are marked as `missing_input`.

24. Missing optional upstream inputs produce warnings but do not fail the item.

25. Invalid eligible metadata rows are marked as `failed_metadata`.

26. The programme supports:

```
--start-corpus-id CORPUS_ID
```


27. If `--start-corpus-id` is not found among eligible records, the programme exits with configuration error.

28. A log file is written at:

```
corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation.log
```


29. A latest manifest is written at:

```
corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation_manifest.json
```


30. A timestamped per-run manifest is also written.

31. A QC index is written at:

```
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_index.ndjson
```


32. The programme exits with:
    - `0` for clean execution completion;
    - `1` for item-level failures, missing required inputs, or invalid eligible metadata;
    - `2` for configuration errors;
    - `130` for keyboard interruption.

33. QC ratings of `review` or `warning` do not by themselves cause a non-zero exit code.

34. The programme does **not** transcribe, align, diarise, assign speakers, identify real speakers, or modify upstream outputs.

---

# 18. Short README Section

## Produce QC reports for Jubilee debate speaker diarisation

The `qc_jubilee_debates_speaker_diarisation.py` programme produces quality-control reports for speaker-attributed Jubilee debate transcripts.

It reads the speaker-assignment index:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
```


Only records whose `speaker_assignment_status` indicates available speaker-assignment outputs are processed.

Speaker-assignment files are resolved from index fields when available. Otherwise, the programme expects:

```
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_transcript.txt
```


QC outputs are written to:

```
corpus/07_jubilee_debates_qc/
```


Each successful QC process writes:

```
corpus/07_jubilee_debates_qc/<corpus_id>.qc.json
corpus/07_jubilee_debates_qc/<corpus_id>.qc.md
```


The programme also writes corpus-level summaries:

```
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_summary.json
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_summary.md
```


Default test run:

```
python qc_jubilee_debates_speaker_diarisation.py
```


This processes one planned debate by default.

Full run:

```
python qc_jubilee_debates_speaker_diarisation.py --no-test-mode
```


Resume from a specific debate:

```
python qc_jubilee_debates_speaker_diarisation.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```


Force QC regeneration:

```
python qc_jubilee_debates_speaker_diarisation.py \
  --no-test-mode \
  --reprocess
```


The programme writes:

```
corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation.log
corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation_manifest.json
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_index.ndjson
```


A timestamped per-run manifest is also created.

This stage performs QC reporting only. It does not modify upstream outputs or identify real speakers.