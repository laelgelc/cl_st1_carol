# `assign_speakers_jubilee_debates.py` — Programme Specification for Development

## 1. High-level Functionality Specification

### Programme Summary

`assign_speakers_jubilee_debates.py` is a batch-processing programme that combines:

1. **WhisperX forced-alignment outputs**, containing transcript words or segments with timestamps; and
2. **pyannote.audio diarisation outputs**, containing anonymous speaker-labelled time intervals;

to produce **speaker-attributed Jubilee debate transcripts**.

The programme is part of:

```
Corpus Linguistics — Study 1 — Carol, Phase 0 — Speaker Diarisation Test
```


It is the fourth stage in the speech-processing pipeline.

The preceding stages are:

| Stage | Programme |
|---:|---|
| 1 | `transcribe_jubilee_debates_whisperx.py` |
| 2 | `align_jubilee_debates_whisperx.py` |
| 3 | `diarise_jubilee_debates_pyannote.py` |

The following stage is:

| Stage | Programme |
|---:|---|
| 5 | `qc_jubilee_debates_speaker_diarisation.py` |

The programme reads:

```
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
```


and:

```
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
```


For each debate available in both upstream indices, the programme must locate:

```
corpus/04_jubilee_debates_alignment/<corpus_id>.aligned.json
corpus/04_jubilee_debates_alignment/<corpus_id>.words.ndjson
corpus/05_jubilee_debates_diarisation/<corpus_id>.diarisation.json
corpus/05_jubilee_debates_diarisation/<corpus_id>.segments.ndjson
```


where available, using paths recorded in the indices first and fallback conventions second.

Speaker-attributed outputs must be written to:

```
corpus/06_jubilee_debates_speaker_transcripts/
```


For each successfully processed debate, the programme must write:

```
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_transcript.txt
```


The programme performs **speaker assignment only**. It must not perform:

- audio extraction;
- Whisper transcription;
- WhisperX forced alignment;
- pyannote speaker diarisation;
- real speaker identity resolution;
- manual speaker-name curation;
- quality-control report generation.

Diarised labels such as:

```
SPEAKER_00
SPEAKER_01
SPEAKER_02
```


must remain anonymous speaker labels. They are not real participant identities.

---

## 2. Key Behaviours

The programme must implement the following behaviours:

- Read the alignment index from NDJSON.
- Read the diarisation index from NDJSON.
- Match records by `corpus_id`.
- Process only debates where both alignment and diarisation are available.
- Use alignment outputs with successful or skipped-existing statuses.
- Use diarisation outputs with successful or skipped-existing statuses.
- Locate aligned word data using:
  - `words_ndjson_file`, when present and usable;
  - otherwise `<alignment_dir>/<corpus_id>.words.ndjson`;
  - otherwise aligned JSON word data if NDJSON is unavailable.
- Locate aligned JSON using:
  - `aligned_json_file`, when present and usable;
  - otherwise `<alignment_dir>/<corpus_id>.aligned.json`.
- Locate diarisation segment data using:
  - `segments_ndjson_file`, when present and usable;
  - otherwise `<diarisation_dir>/<corpus_id>.segments.ndjson`;
  - otherwise diarisation JSON segment data if NDJSON is unavailable.
- Locate diarisation JSON using:
  - `diarisation_json_file`, when present and usable;
  - otherwise `<diarisation_dir>/<corpus_id>.diarisation.json`.
- Assign speaker labels to aligned words using timestamp overlap or midpoint matching.
- Build speaker-attributed transcript segments by grouping adjacent words with compatible speaker labels.
- Preserve word-level speaker assignment detail for downstream QC.
- Produce readable plain-text speaker-attributed transcripts.
- Use test mode by default, limiting processing to one eligible debate.
- Skip already-complete speaker-assignment outputs by default.
- Allow reprocessing with an explicit command-line option.
- Support starting from a specific `corpus_id`.
- Continue processing remaining debates if one item fails.
- Record progress and errors in an append-only log file.
- Produce a JSON manifest with run-level metadata and item-level results.
- Write both:
  - a timestamped per-run manifest;
  - a latest manifest overwritten on each run.
- Write a curated speaker-assignment index for downstream QC.
- Exit with status code `0` only when all attempted assignments succeed or are skipped, and there are no missing inputs or invalid eligible metadata rows.
- Exit with a non-zero status code if one or more attempted assignments fail, if source inputs are missing, if eligible metadata is invalid, or if there is a configuration/validation error.

---

## 3. Path Resolution Policy

The programme must resolve default paths relative to the directory where `assign_speakers_jubilee_debates.py` is located, not relative to the current working directory.

If the script is located at:

```
cl_st1_ph0_carol/assign_speakers_jubilee_debates.py
```


then the default alignment index path:

```
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
```


must resolve to:

```
cl_st1_ph0_carol/corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
```


and the default diarisation index path:

```
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
```


must resolve to:

```
cl_st1_ph0_carol/corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
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

- `--alignment-index`
- `--diarisation-index`
- `--alignment-dir`
- `--diarisation-dir`
- `--output-dir`
- `--log-file`
- `--manifest-file`
- `--speaker-index-file`

the programme must preserve that absolute path.

---

## 4. Input / Output Specification

## 4.1 Input

### Alignment index file

Default path:

```
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
```


The file is expected to be in **NDJSON** format: one JSON object per line.

This file is produced by:

```
align_jubilee_debates_whisperx.py
```


### Diarisation index file

Default path:

```
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
```


The file is expected to be in **NDJSON** format: one JSON object per line.

This file is produced by:

```
diarise_jubilee_debates_pyannote.py
```


---

## 4.2 Required index fields

### Required alignment-index fields

Each valid eligible alignment-index record must contain:

| Field | Type | Description |
|---|---:|---|
| `corpus_id` | string | Stable internal debate identifier |
| `alignment_status` | string | Alignment stage status |

The source alignment paths are resolved using:

| Field | Requirement | Description |
|---|---|---|
| `aligned_json_file` | optional | Preferred aligned JSON path |
| `words_ndjson_file` | optional | Preferred aligned word NDJSON path |

If these are absent, blank, or unusable, the programme must use fallback paths based on `corpus_id`.

### Required diarisation-index fields

Each valid eligible diarisation-index record must contain:

| Field | Type | Description |
|---|---:|---|
| `corpus_id` | string | Stable internal debate identifier |
| `diarisation_status` | string | Diarisation stage status |

The source diarisation paths are resolved using:

| Field | Requirement | Description |
|---|---|---|
| `diarisation_json_file` | optional | Preferred diarisation JSON path |
| `segments_ndjson_file` | optional | Preferred diarisation segment NDJSON path |

If these are absent, blank, or unusable, the programme must use fallback paths based on `corpus_id`.

---

## 4.3 Eligible statuses

### Eligible alignment statuses

The programme must process only alignment records where:

```
alignment_status = success
```


or:

```
alignment_status = skipped_existing
```


Records with other alignment statuses must not be processed.

Ineligible alignment statuses include:

```
failed
missing_input
failed_metadata
ignored_transcript_unavailable
interrupted
null
""
missing value
```


### Eligible diarisation statuses

The programme must process only diarisation records where:

```
diarisation_status = success
```


or:

```
diarisation_status = skipped_existing
```


Records with other diarisation statuses must not be processed.

Ineligible diarisation statuses include:

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


---

## 4.4 Input alignment files

### Alignment input directory

Default path:

```
corpus/04_jubilee_debates_alignment/
```


Each fallback aligned JSON file is expected as:

```
<alignment_dir>/<corpus_id>.aligned.json
```


Each fallback word NDJSON file is expected as:

```
<alignment_dir>/<corpus_id>.words.ndjson
```


Examples:

```
corpus/04_jubilee_debates_alignment/jubilee_surrounded_001.aligned.json
corpus/04_jubilee_debates_alignment/jubilee_surrounded_001.words.ndjson
```


The word NDJSON file should contain one aligned word/token per line.

Recommended input word structure:

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


Words without usable timestamps should still be preserved where possible but cannot receive a reliable speaker assignment.

---

## 4.5 Input diarisation files

### Diarisation input directory

Default path:

```
corpus/05_jubilee_debates_diarisation/
```


Each fallback diarisation JSON file is expected as:

```
<diarisation_dir>/<corpus_id>.diarisation.json
```


Each fallback diarisation segment NDJSON file is expected as:

```
<diarisation_dir>/<corpus_id>.segments.ndjson
```


Examples:

```
corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.diarisation.json
corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.segments.ndjson
```


The segment NDJSON file should contain one diarised speaker interval per line.

Recommended input diarisation segment structure:

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

## 4.6 Metadata fields to preserve

The programme should preserve these fields in speaker-assignment outputs and indices when present:

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
| `transcript_json_file` | Transcript JSON path |
| `aligned_json_file` | Aligned JSON path |
| `words_ndjson_file` | Aligned word NDJSON path |
| `rttm_file` | Diarisation RTTM path |
| `diarisation_json_file` | Diarisation JSON path |
| `segments_ndjson_file` | Diarisation segment NDJSON path |
| `alignment_status` | Alignment stage status |
| `alignment_run_id` | Alignment run ID |
| `aligned_at_utc` | Alignment timestamp |
| `diarisation_status` | Diarisation stage status |
| `diarisation_run_id` | Diarisation run ID |
| `diarised_at_utc` | Diarisation timestamp |
| `detected_speaker_count` | Number of speakers from diarisation |
| `selected_by` | Selector |
| `selection_source` | Selection source |
| `notes` | Notes |

---

## 4.7 Output

### Speaker-assignment output directory

Default path:

```
corpus/06_jubilee_debates_speaker_transcripts/
```


The programme must create this directory if it does not already exist.

### Per-debate speaker words JSON

Each successful assignment must write:

```
<output_dir>/<corpus_id>.speaker_words.json
```


Example:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_words.json
```


This file contains all aligned words with assigned speaker labels and assignment metadata.

### Per-debate speaker words NDJSON

Each successful assignment must write:

```
<output_dir>/<corpus_id>.speaker_words.ndjson
```


Example:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_words.ndjson
```


This file contains one speaker-assigned word per line.

### Per-debate speaker segments JSON

Each successful assignment must write:

```
<output_dir>/<corpus_id>.speaker_segments.json
```


Example:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_segments.json
```


This file contains speaker-grouped transcript segments suitable for reading and analysis.

### Per-debate speaker segments NDJSON

Each successful assignment must write:

```
<output_dir>/<corpus_id>.speaker_segments.ndjson
```


Example:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_segments.ndjson
```


This file contains one speaker-attributed transcript segment per line.

### Per-debate plain-text speaker transcript

Each successful assignment must write:

```
<output_dir>/<corpus_id>.speaker_transcript.txt
```


Example:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_transcript.txt
```


Example plain-text format:

```
[SPEAKER_00 00:00:12.420-00:00:18.910]
I think the question we have to ask is whether college is still worth it.

[SPEAKER_03 00:00:19.200-00:00:24.640]
But that depends entirely on what kind of degree you're getting.
```


### Log file

Default path:

```
corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates.log
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
corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates_manifest.json
```


#### Per-run manifest

A timestamped copy must also be written using the run ID.

Filename pattern:

```
assign_speakers_jubilee_debates_manifest_<run_id>.json
```


Example:

```
corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates_manifest_20260804T150000Z.json
```


### Speaker-assignment index file

Default path:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
```


This curated speaker-assignment index is used by downstream QC.

---

# 5. Command-line Interface

## 5.1 Default usage

The programme may be run from inside `cl_st1_ph0_carol/`:

```
python assign_speakers_jubilee_debates.py
```


or from the project root:

```
python cl_st1_ph0_carol/assign_speakers_jubilee_debates.py
```


Both commands should resolve default paths correctly.

Default behaviour:

- alignment index:

```
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
```


- diarisation index:

```
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
```


- alignment directory:

```
corpus/04_jubilee_debates_alignment/
```


- diarisation directory:

```
corpus/05_jubilee_debates_diarisation/
```


- output directory:

```
corpus/06_jubilee_debates_speaker_transcripts/
```


- assignment method:

```
overlap
```


- minimum overlap ratio:

```
0.0
```


- unassigned speaker label:

```
UNKNOWN_SPEAKER
```


- merge adjacent words with same speaker:

```
enabled
```


- maximum gap between merged words:

```
1.0 seconds
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


- existing complete speaker-assignment outputs are skipped;
- one worker / sequential processing.

---

## 5.2 Required arguments

There are no required command-line arguments if all defaults are used.

---

## 5.3 Optional arguments

### Alignment index

```
--alignment-index PATH
```


Default:

```
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
```


Description:

Path to the curated NDJSON alignment index from the alignment stage.

---

### Diarisation index

```
--diarisation-index PATH
```


Default:

```
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
```


Description:

Path to the curated NDJSON diarisation index from the diarisation stage.

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

Fallback directory containing aligned JSON and word NDJSON files.

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

Fallback directory containing diarisation JSON and segment NDJSON files.

---

### Output directory

```
--output-dir PATH
```


Default:

```
corpus/06_jubilee_debates_speaker_transcripts/
```


Description:

Directory where speaker-attributed outputs, logs, manifests, and speaker-assignment index are written.

---

### Assignment method

```
--assignment-method METHOD
```


Default:

```
overlap
```


Allowed values:

```
overlap
midpoint
```


Description:

Method used to assign a diarised speaker label to each aligned word.

- `overlap`: choose the diarisation segment with the greatest overlap with the word interval.
- `midpoint`: choose the diarisation segment containing the midpoint of the word interval.

The recommended default is:

```
overlap
```


because aligned words have start and end timestamps.

---

### Minimum overlap ratio

```
--min-overlap-ratio FLOAT
```


Default:

```
0.0
```


Description:

Minimum fraction of the word duration that must overlap a diarisation segment for the speaker assignment to be accepted.

For example:

```
0.5
```


means at least half the word duration must overlap the selected diarisation interval.

For initial processing, `0.0` is acceptable because any positive overlap can be useful, but QC should later review low-confidence assignments.

---

### Unassigned speaker label

```
--unassigned-speaker-label LABEL
```


Default:

```
UNKNOWN_SPEAKER
```


Description:

Speaker label used when no diarisation segment can be assigned to a word.

---

### Merge adjacent words

```
--merge-adjacent
--no-merge-adjacent
```


Default:

```
--merge-adjacent
```


Description:

Whether adjacent words assigned to the same speaker should be merged into readable speaker transcript segments.

---

### Maximum merge gap

```
--max-merge-gap SECONDS
```


Default:

```
1.0
```


Description:

Maximum gap between adjacent words for them to be merged into the same speaker segment when they share the same speaker label.

If the gap exceeds this threshold, start a new speaker segment.

---

### Maximum segment duration

```
--max-segment-duration SECONDS
```


Default:

```
30.0
```


Description:

Maximum duration of a speaker transcript segment before forcing a segment break, even if the same speaker continues.

This keeps plain-text transcripts readable.

---

### Maximum segment words

```
--max-segment-words N
```


Default:

```
120
```


Description:

Maximum number of words in one speaker transcript segment before forcing a segment break.

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

### Reprocess existing speaker assignments

```
--reprocess
```


Default:

```
False
```


When omitted, debates with all required speaker-assignment outputs present are skipped.

When provided, speaker assignment is run again and existing outputs are overwritten.

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
python assign_speakers_jubilee_debates.py \
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
corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates.log
```


---

### Manifest file

```
--manifest-file PATH
```


Default:

```
corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates_manifest.json
```


---

### Speaker-assignment index file

```
--speaker-index-file PATH
```


Default:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
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

This stage is CPU-only and could later support parallelism, but the first implementation should remain sequential for simpler logging, reproducibility, and debugging.

---

### Timeout

```
--timeout SECONDS
```


Default suggestion:

```
3600
```


A one-hour per-item timeout is generous for speaker assignment. Strict timeout enforcement may require subprocess isolation; the first implementation may record the value without hard enforcement.

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

### Default one-debate speaker-assignment test

```
python assign_speakers_jubilee_debates.py
```


### Test from a specific corpus ID

```
python assign_speakers_jubilee_debates.py \
  --test-limit 1 \
  --start-corpus-id jubilee_surrounded_003
```


### Full speaker-assignment run

```
python assign_speakers_jubilee_debates.py --no-test-mode
```


### Full run with midpoint assignment

```
python assign_speakers_jubilee_debates.py \
  --no-test-mode \
  --assignment-method midpoint
```


### Full run with stricter overlap

```
python assign_speakers_jubilee_debates.py \
  --no-test-mode \
  --assignment-method overlap \
  --min-overlap-ratio 0.5
```


### Re-assign all debates

```
python assign_speakers_jubilee_debates.py \
  --no-test-mode \
  --reprocess
```


### Local or EC2 run

This stage does not require a GPU. It can run locally or on EC2 after Stages 1–3 have produced alignment and diarisation outputs.

```
python assign_speakers_jubilee_debates.py --no-test-mode
```


---

# 6. Argument Validation

The programme must fail fast with a clear message if:

- the alignment index file does not exist;
- the alignment index path is not a file;
- the alignment index is unreadable;
- the alignment index contains invalid JSON lines;
- the diarisation index file does not exist;
- the diarisation index path is not a file;
- the diarisation index is unreadable;
- the diarisation index contains invalid JSON lines;
- no eligible matched alignment/diarisation records are found;
- the alignment directory does not exist;
- the alignment directory is not a directory;
- the diarisation directory does not exist;
- the diarisation directory is not a directory;
- the output directory cannot be created;
- `--assignment-method` is unsupported;
- `--min-overlap-ratio` is less than `0.0` or greater than `1.0`;
- `--unassigned-speaker-label` is missing or blank;
- `--max-merge-gap` is less than zero;
- `--max-segment-duration` is less than or equal to zero;
- `--max-segment-words` is less than or equal to zero;
- `--test-limit` is less than or equal to zero;
- `--workers` is less than or equal to zero;
- `--workers` is not `1`;
- `--timeout` is less than or equal to zero;
- `--max-retries` is negative;
- `--retry-delay` is negative;
- `--start-corpus-id` is provided but empty;
- `--start-corpus-id` is provided but not found among eligible matched records.

A validation error should:

- be printed clearly to the console;
- be written to the log if logging has already been configured;
- cause the programme to exit with code `2`.

---

# 7. Environment and Configuration

## 7.1 Runtime environment

This stage is primarily a JSON/NDJSON merging and timestamp assignment step.

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

- locally after copying Stages 1–3 outputs back from EC2; or
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

2. **Index loading**
   - Load alignment index from NDJSON.
   - Load diarisation index from NDJSON.
   - Parse each line as a JSON object.
   - Count total records in each index.
   - Select only eligible alignment records.
   - Select only eligible diarisation records.
   - Validate required fields.
   - Record ignored and invalid rows.
   - Match eligible records by `corpus_id`.

3. **Planning**
   - Preserve alignment-index order for matched records.
   - Apply `--start-corpus-id`, if provided.
   - Resolve required alignment paths.
   - Resolve required diarisation paths.
   - Compute output paths:
     - `<output_dir>/<corpus_id>.speaker_words.json`;
     - `<output_dir>/<corpus_id>.speaker_words.ndjson`;
     - `<output_dir>/<corpus_id>.speaker_segments.json`;
     - `<output_dir>/<corpus_id>.speaker_segments.ndjson`;
     - `<output_dir>/<corpus_id>.speaker_transcript.txt`.
   - Check missing inputs.
   - Skip if outputs already exist and `--reprocess` is not enabled.
   - Apply test-mode limit to planned assignments.

4. **Execution**
   - For each planned item:
     - load aligned words;
     - load diarisation segments;
     - validate timestamp fields;
     - assign a speaker label to each word;
     - calculate assignment confidence/metadata where possible;
     - group speaker-assigned words into speaker transcript segments;
     - write speaker word JSON;
     - write speaker word NDJSON;
     - write speaker segment JSON;
     - write speaker segment NDJSON;
     - write plain-text transcript;
     - capture timing, counts, warnings, and errors;
     - retry according to `--max-retries`;
     - mark item as `success` or `failed`.

5. **Speaker-assignment index generation**
   - Combine source metadata and speaker-assignment metadata.
   - Write curated NDJSON speaker-assignment index.

6. **Manifest writing**
   - Count summary statistics.
   - Write latest manifest.
   - Write per-run manifest.

7. **Exit**
   - Exit `0`, `1`, `2`, or `130` according to run outcome.

---

## 8.2 Separation of concerns

Suggested function responsibilities:

```python
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the speaker-assignment programme."""
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
def load_ndjson_index(index_path: Path, status_field: str, eligible_statuses: tuple[str, ...]) -> tuple[list[dict], list[dict], list[dict], int]:
    """Load and filter an NDJSON index by status."""
```


```python
def match_alignment_and_diarisation_records(
    alignment_records: list[dict],
    diarisation_records: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Match eligible alignment and diarisation records by corpus_id."""
```


```python
def resolve_alignment_paths(record: dict, alignment_dir: Path) -> dict[str, Path]:
    """Resolve aligned JSON and aligned word NDJSON paths."""
```


```python
def resolve_diarisation_paths(record: dict, diarisation_dir: Path) -> dict[str, Path]:
    """Resolve diarisation JSON and diarisation segment NDJSON paths."""
```


```python
def plan_speaker_assignments(
    matched_records: list[dict],
    alignment_dir: Path,
    diarisation_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_corpus_id: str | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Create planned, skipped, and missing-input speaker-assignment records."""
```


```python
def load_aligned_words(words_ndjson_path: Path | None, aligned_json_path: Path | None) -> list[dict]:
    """Load aligned word records from NDJSON or aligned JSON fallback."""
```


```python
def load_diarisation_segments(segments_ndjson_path: Path | None, diarisation_json_path: Path | None) -> list[dict]:
    """Load diarised speaker intervals from NDJSON or diarisation JSON fallback."""
```


```python
def assign_speakers_to_words(
    words: list[dict],
    diarisation_segments: list[dict],
    assignment_method: str,
    min_overlap_ratio: float,
    unassigned_speaker_label: str,
) -> tuple[list[dict], dict]:
    """Assign diarised speaker labels to aligned words."""
```


```python
def build_speaker_segments(
    speaker_words: list[dict],
    merge_adjacent: bool,
    max_merge_gap: float,
    max_segment_duration: float,
    max_segment_words: int,
) -> list[dict]:
    """Group speaker-assigned words into readable speaker transcript segments."""
```


```python
def write_speaker_assignment_outputs(
    speaker_words_json: dict,
    speaker_words: list[dict],
    speaker_segments_json: dict,
    speaker_segments: list[dict],
    transcript_text: str,
    output_paths: dict[str, Path],
) -> None:
    """Write speaker word, speaker segment, and plain-text transcript outputs."""
```


```python
def write_speaker_assignment_index(index_records: list[dict], speaker_index_file: Path) -> None:
    """Write curated NDJSON speaker-assignment index."""
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
    """Run the batch Jubilee debate speaker-assignment workflow and return an exit code."""
```


---

# 9. Speaker Assignment Behaviour

## 9.1 Assignment goal

The programme must assign a diarised anonymous speaker label to each aligned word where possible.

For each aligned word with timestamps:

```json
{
  "word": "Example",
  "start": 0.12,
  "end": 0.54
}
```


the programme compares the word interval to diarisation intervals such as:

```json
{
  "speaker": "SPEAKER_00",
  "start": 0.10,
  "end": 1.20
}
```


and assigns:

```json
{
  "speaker": "SPEAKER_00"
}
```


The programme must preserve the original word, word timing, segment ID, and alignment metadata where possible.

---

## 9.2 Assignment method: overlap

Default method:

```
overlap
```


For each word:

1. Compute the overlap between the word interval and every diarisation segment.
2. Select the diarisation segment with the greatest positive overlap.
3. If multiple diarisation segments have equal overlap, choose the one with:
   - the largest overlap duration;
   - then the earliest start time;
   - then stable input order.
4. Assign that segment’s speaker label.
5. Record:
   - overlap duration;
   - word duration;
   - overlap ratio;
   - assignment method;
   - assignment status.

Recommended output fields:

```json
{
  "assignment_method": "overlap",
  "assignment_status": "assigned",
  "speaker": "SPEAKER_00",
  "speaker_overlap_seconds": 0.42,
  "speaker_overlap_ratio": 1.0
}
```


If no positive overlap exists, assign:

```
UNKNOWN_SPEAKER
```


and record:

```json
{
  "assignment_status": "unassigned_no_overlap"
}
```


---

## 9.3 Assignment method: midpoint

Alternative method:

```
midpoint
```


For each word:

1. Compute the word midpoint:

```
(start + end) / 2
```


2. Find the diarisation segment containing the midpoint.
3. If multiple diarisation segments contain the midpoint, choose the one with:
   - shortest containing segment duration;
   - then earliest start time;
   - then stable input order.
4. Assign that segment’s speaker label.

If no diarisation segment contains the midpoint, assign:

```
UNKNOWN_SPEAKER
```


and record:

```json
{
  "assignment_status": "unassigned_no_midpoint_match"
}
```


---

## 9.4 Words without timestamps

If a word has missing or invalid timestamps:

- preserve the word in output;
- assign the unassigned speaker label;
- mark assignment status as:

```
unassigned_missing_word_timing
```


These words should still appear in speaker word outputs, but they may be omitted from speaker segment grouping if they cannot be positioned reliably. The preferred behaviour is to include them in the nearest segment only if safe and clearly flagged; otherwise keep them as separate unassigned records.

---

## 9.5 Diarisation overlaps

Debate audio may contain overlapping speech. pyannote may produce overlapping diarisation intervals.

The first implementation should assign **one primary speaker per word**, not multiple speakers.

If a word overlaps multiple speakers:

- choose the speaker with greatest overlap by default;
- record whether multiple candidate speakers existed;
- record the number of candidate speakers;
- optionally record top candidates for QC.

Recommended fields:

```json
{
  "speaker_candidate_count": 2,
  "speaker_candidates": [
    {
      "speaker": "SPEAKER_00",
      "overlap_seconds": 0.31
    },
    {
      "speaker": "SPEAKER_05",
      "overlap_seconds": 0.12
    }
  ]
}
```


To keep files compact, candidate lists may be disabled or truncated in later versions. The first implementation may include them when practical.

---

## 9.6 Speaker segment grouping

After assigning speakers to words, the programme must build readable speaker-attributed transcript segments.

A new speaker segment should start when:

- this is the first assignable word;
- the assigned speaker changes;
- the gap from the previous word is greater than `--max-merge-gap`;
- the current segment duration would exceed `--max-segment-duration`;
- the current segment word count would exceed `--max-segment-words`;
- the previous or current word has missing timing and cannot be merged safely.

Recommended speaker segment structure:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "speaker_segment_index": 1,
  "speaker": "SPEAKER_00",
  "start": 12.42,
  "end": 18.91,
  "duration": 6.49,
  "word_count": 18,
  "text": "I think the question we have to ask is whether college is still worth it.",
  "source_word_start_index": 120,
  "source_word_end_index": 137,
  "assignment_status": "assigned"
}
```


---

## 9.7 Text reconstruction

The programme should reconstruct text from word records conservatively.

Minimum acceptable behaviour:

- join word tokens with spaces;
- strip extra whitespace before punctuation where practical;
- preserve original word text;
- do not attempt heavy transcript normalisation.

Recommended punctuation cleanup:

```
"word ." -> "word."
"word ," -> "word,"
"word ?" -> "word?"
"word !" -> "word!"
"word :" -> "word:"
"word ;" -> "word;"
```


The programme should avoid changing lexical content.

---

# 10. Output Data Design

## 10.1 Speaker words JSON

The speaker words JSON should include:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "input_alignment_paths": {
    "aligned_json_path": "corpus/04_jubilee_debates_alignment/jubilee_surrounded_001.aligned.json",
    "words_ndjson_path": "corpus/04_jubilee_debates_alignment/jubilee_surrounded_001.words.ndjson"
  },
  "input_diarisation_paths": {
    "diarisation_json_path": "corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.diarisation.json",
    "segments_ndjson_path": "corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.segments.ndjson"
  },
  "speaker_assignment": {
    "assignment_method": "overlap",
    "min_overlap_ratio": 0.0,
    "unassigned_speaker_label": "UNKNOWN_SPEAKER",
    "word_count": 14500,
    "assigned_word_count": 14100,
    "unassigned_word_count": 400,
    "speaker_count": 18,
    "words": [
      {
        "corpus_id": "jubilee_surrounded_001",
        "segment_id": 1,
        "word_index": 1,
        "word": "Example",
        "start": 0.12,
        "end": 0.54,
        "score": 0.91,
        "alignment_status": "aligned",
        "speaker": "SPEAKER_00",
        "assignment_status": "assigned",
        "assignment_method": "overlap",
        "speaker_overlap_seconds": 0.42,
        "speaker_overlap_ratio": 1.0,
        "speaker_candidate_count": 1
      }
    ]
  },
  "metadata": {},
  "run": {
    "speaker_assignment_run_id": "20260804T150000Z",
    "assigned_at_utc": "2026-08-04T15:00:00Z"
  },
  "status": "success",
  "error": null
}
```


---

## 10.2 Speaker words NDJSON

Each line in `<corpus_id>.speaker_words.ndjson` should contain one speaker-assigned word.

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
  "alignment_status": "aligned",
  "speaker": "SPEAKER_00",
  "assignment_status": "assigned",
  "assignment_method": "overlap",
  "speaker_overlap_seconds": 0.42,
  "speaker_overlap_ratio": 1.0
}
```


---

## 10.3 Speaker segments JSON

The speaker segments JSON should include:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "speaker_segments": {
    "segment_count": 980,
    "speaker_count": 18,
    "segments": [
      {
        "corpus_id": "jubilee_surrounded_001",
        "speaker_segment_index": 1,
        "speaker": "SPEAKER_00",
        "start": 12.42,
        "end": 18.91,
        "duration": 6.49,
        "word_count": 18,
        "text": "I think the question we have to ask is whether college is still worth it.",
        "source_word_start_index": 120,
        "source_word_end_index": 137,
        "assignment_status": "assigned"
      }
    ]
  },
  "metadata": {},
  "run": {
    "speaker_assignment_run_id": "20260804T150000Z",
    "assigned_at_utc": "2026-08-04T15:00:00Z"
  },
  "status": "success",
  "error": null
}
```


---

## 10.4 Speaker segments NDJSON

Each line in `<corpus_id>.speaker_segments.ndjson` should contain one speaker-attributed transcript segment.

Recommended fields:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "speaker_segment_index": 1,
  "speaker": "SPEAKER_00",
  "start": 12.42,
  "end": 18.91,
  "duration": 6.49,
  "word_count": 18,
  "text": "I think the question we have to ask is whether college is still worth it.",
  "source_word_start_index": 120,
  "source_word_end_index": 137,
  "assignment_status": "assigned"
}
```


---

## 10.5 Plain-text speaker transcript

The plain-text transcript should be UTF-8 encoded.

Recommended format:

```
# jubilee_surrounded_001
# 1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)
# Speaker labels are anonymous diarisation labels, not real participant identities.

[SPEAKER_00 00:00:12.420-00:00:18.910]
I think the question we have to ask is whether college is still worth it.

[SPEAKER_03 00:00:19.200-00:00:24.640]
But that depends entirely on what kind of degree you're getting.
```


If a segment has no assigned speaker:

```
[UNKNOWN_SPEAKER 00:05:12.000-00:05:13.400]
...
```


---

# 11. Speaker-assignment Index Design

The programme must write:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
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
| `aligned_json_file` | Source aligned JSON path |
| `words_ndjson_file` | Source aligned word NDJSON path |
| `diarisation_json_file` | Source diarisation JSON path |
| `segments_ndjson_file` | Source diarisation segment NDJSON path |
| `speaker_words_json_file` | Speaker words JSON output path |
| `speaker_words_ndjson_file` | Speaker words NDJSON output path |
| `speaker_segments_json_file` | Speaker segments JSON output path |
| `speaker_segments_ndjson_file` | Speaker segments NDJSON output path |
| `speaker_transcript_text_file` | Plain-text speaker transcript path |
| `speaker_assignment_status` | Status |
| `speaker_assignment_run_id` | Run ID |
| `assigned_at_utc` | Timestamp |
| `assignment_method` | Assignment method |
| `min_overlap_ratio` | Minimum overlap ratio |
| `word_count` | Total aligned word count |
| `assigned_word_count` | Words assigned to a diarised speaker |
| `unassigned_word_count` | Words without a speaker assignment |
| `speaker_segment_count` | Number of speaker transcript segments |
| `detected_speaker_count` | Number of speakers from diarisation |
| `assigned_speaker_count` | Number of speakers used in assigned output |
| `unknown_speaker_word_count` | Number of words assigned to unknown label |
| `alignment_status` | Alignment stage status |
| `alignment_run_id` | Alignment run ID |
| `diarisation_status` | Diarisation stage status |
| `diarisation_run_id` | Diarisation run ID |
| `selected_by` | Selector |
| `selection_source` | Selection source |
| `notes` | Notes |
| `error` | Error message |

---

# 12. JSON Manifest Design

## 12.1 Manifest structure

The manifest must use this general structure:

```json
{
  "run_metadata": {
    "run_id": "20260804T150000Z",
    "tool_name": "assign_speakers_jubilee_debates.py",
    "tool_version": "v1",
    "start_time": "2026-08-04T15:00:00Z",
    "end_time": "2026-08-04T15:04:00Z",
    "test_mode": true,
    "test_limit": 1,
    "reprocess": false,
    "workers": 1,
    "alignment_index_path": "corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson",
    "diarisation_index_path": "corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson",
    "alignment_dir": "corpus/04_jubilee_debates_alignment",
    "diarisation_dir": "corpus/05_jubilee_debates_diarisation",
    "output_dir": "corpus/06_jubilee_debates_speaker_transcripts",
    "speaker_index_file": "corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson",
    "log_file": "corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates.log",
    "manifest_file": "corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates_manifest.json",
    "config": {
      "assignment_method": "overlap",
      "min_overlap_ratio": 0.0,
      "unassigned_speaker_label": "UNKNOWN_SPEAKER",
      "merge_adjacent": true,
      "max_merge_gap": 1.0,
      "max_segment_duration": 30.0,
      "max_segment_words": 120,
      "timeout_seconds": 3600,
      "max_retries": 1,
      "retry_delay_seconds": 5,
      "start_corpus_id": null
    },
    "environment": {
      "python_version": "3.11.x"
    },
    "summary": {
      "alignment_index_records": 5,
      "eligible_alignment_records": 5,
      "diarisation_index_records": 5,
      "eligible_diarisation_records": 5,
      "matched_records": 5,
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
      "input_aligned_json_path": "corpus/04_jubilee_debates_alignment/jubilee_surrounded_001.aligned.json",
      "input_words_ndjson_path": "corpus/04_jubilee_debates_alignment/jubilee_surrounded_001.words.ndjson",
      "input_diarisation_json_path": "corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.diarisation.json",
      "input_diarisation_segments_path": "corpus/05_jubilee_debates_diarisation/jubilee_surrounded_001.segments.ndjson",
      "speaker_words_json_path": "corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_words.json",
      "speaker_words_ndjson_path": "corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_words.ndjson",
      "speaker_segments_json_path": "corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_segments.json",
      "speaker_segments_ndjson_path": "corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_segments.ndjson",
      "speaker_transcript_text_path": "corpus/06_jubilee_debates_speaker_transcripts/jubilee_surrounded_001.speaker_transcript.txt",
      "status": "success",
      "error": null,
      "retries": 0,
      "duration_seconds": 12.5,
      "start_time": "2026-08-04T15:01:00Z",
      "end_time": "2026-08-04T15:01:13Z",
      "word_count": 14500,
      "assigned_word_count": 14100,
      "unassigned_word_count": 400,
      "speaker_segment_count": 980,
      "detected_speaker_count": 18,
      "assigned_speaker_count": 18,
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

## 12.2 Required item statuses

| Status | Meaning |
|---|---|
| `success` | Speaker assignment completed successfully |
| `failed` | Speaker assignment was attempted but failed |
| `skipped_existing` | Speaker-assignment outputs already existed and `--reprocess` was not enabled |
| `missing_input` | Required alignment or diarisation input was missing |
| `failed_metadata` | Eligible matched metadata row was invalid |
| `ignored_alignment_unavailable` | Alignment record ignored because alignment was not available |
| `ignored_diarisation_unavailable` | Diarisation record ignored because diarisation was not available |
| `unmatched_alignment` | Alignment exists but no eligible diarisation record was found |
| `unmatched_diarisation` | Diarisation exists but no eligible alignment record was found |
| `interrupted` | Processing stopped due to keyboard interruption |

---

# 13. Logging Specification

The programme must write an append-only UTF-8 log file.

Default:

```
corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates.log
```


Log format:

```
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```


Required log events:

- startup;
- run ID;
- parsed configuration;
- alignment index path;
- diarisation index path;
- alignment directory;
- diarisation directory;
- output directory;
- test mode status;
- test limit;
- reprocess setting;
- start corpus ID;
- assignment method;
- minimum overlap ratio;
- unassigned speaker label;
- merge settings;
- number of alignment index records read;
- number of eligible alignment records;
- number of diarisation index records read;
- number of eligible diarisation records;
- number of matched records;
- number of unmatched alignment records;
- number of unmatched diarisation records;
- number of invalid metadata rows;
- number of planned assignments;
- each skipped existing assignment;
- each missing input;
- each assignment attempt;
- each retry;
- each success;
- each failure;
- word assignment count summary per item;
- speaker segment count summary per item;
- speaker-assignment index write path;
- manifest write paths;
- final summary;
- configuration errors;
- keyboard interruptions.

---

# 14. Error Handling and Resiliency

## 14.1 Configuration errors

Configuration errors must stop the programme before speaker assignment begins.

Examples:

- alignment index missing;
- diarisation index missing;
- index unreadable;
- invalid JSON line in either index;
- no eligible matched records;
- alignment directory missing;
- diarisation directory missing;
- invalid command-line arguments;
- start corpus ID not found.

Exit code:

```
2
```


---

## 14.2 Per-item errors

Per-item errors must not stop the full batch.

Examples:

- aligned JSON missing;
- word NDJSON missing and no usable fallback exists;
- diarisation JSON missing;
- diarisation segment NDJSON missing and no usable fallback exists;
- malformed aligned word data;
- malformed diarisation segment data;
- no usable aligned words;
- no usable diarisation segments;
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

## 14.3 Keyboard interruption

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

## 14.4 Exit codes

| Exit code | Meaning |
|---:|---|
| `0` | Completed with no failed attempted assignments, no missing inputs, and no invalid eligible metadata rows |
| `1` | Completed, but one or more assignments failed, source inputs were missing, or eligible metadata rows were invalid |
| `2` | Configuration or validation error |
| `130` | Interrupted by user |

Skipped existing files are not failures.

Unmatched records that are not part of the planned matched set should be recorded but are not necessarily failures unless they indicate missing required downstream inputs for otherwise eligible processing.

---

# 15. Docstrings and In-code Documentation

## 15.1 Module-level docstring

At the top of `assign_speakers_jubilee_debates.py`, include a module-level docstring explaining:

- purpose of programme;
- expected input alignment index;
- expected input diarisation index;
- source alignment directory;
- source diarisation directory;
- speaker-assignment output directory;
- assignment method;
- default test mode;
- resumability behaviour;
- start-corpus-ID support;
- speaker-assignment-only scope;
- example commands.

Suggested module docstring:

```python
"""
Assign diarised speaker labels to aligned Jubilee debate transcript words.

This script reads the curated Jubilee debate alignment index and diarisation
index, matches records by corpus_id, and assigns anonymous diarised speaker
labels such as SPEAKER_00 to aligned transcript words using timestamp overlap
or midpoint matching.

Alignment inputs are resolved from the alignment index when possible, or from
the alignment directory as "<corpus_id>.aligned.json" and
"<corpus_id>.words.ndjson". Diarisation inputs are resolved from the diarisation
index when possible, or from the diarisation directory as
"<corpus_id>.diarisation.json" and "<corpus_id>.segments.ndjson".

Outputs are written to the speaker transcript output directory as speaker word
JSON/NDJSON, speaker segment JSON/NDJSON, and a readable plain-text speaker
transcript. Speaker labels are anonymous diarisation labels and are not real
participant identities.

By default, the script runs in test mode and attempts only the first planned
debate. Existing complete speaker-assignment outputs are skipped unless
--reprocess is provided, making the script safe to re-run.

Use --start-corpus-id to resume planning from a specific debate onward.

This programme performs speaker assignment only. Transcription, alignment,
diarisation, real speaker identity resolution, and quality-control reporting are
handled by separate pipeline stages.

Example:
    python assign_speakers_jubilee_debates.py

Full run:
    python assign_speakers_jubilee_debates.py --no-test-mode

Full run from a specific debate:
    python assign_speakers_jubilee_debates.py --no-test-mode --start-corpus-id jubilee_surrounded_003
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
- `load_ndjson_index`
- `match_alignment_and_diarisation_records`
- `resolve_alignment_paths`
- `resolve_diarisation_paths`
- `plan_speaker_assignments`
- `load_aligned_words`
- `load_diarisation_segments`
- `assign_speakers_to_words`
- `build_speaker_segments`
- `write_speaker_assignment_outputs`
- `write_speaker_assignment_index`
- `write_manifests`
- `main`

---

# 16. Suggested Constants

```python
TOOL_NAME = "assign_speakers_jubilee_debates.py"
TOOL_VERSION = "v1"

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_ALIGNMENT_INDEX_PATH = (
    "corpus/04_jubilee_debates_alignment/"
    "jubilee_debates_alignment_index.ndjson"
)
DEFAULT_DIARISATION_INDEX_PATH = (
    "corpus/05_jubilee_debates_diarisation/"
    "jubilee_debates_diarisation_index.ndjson"
)

DEFAULT_ALIGNMENT_DIR = "corpus/04_jubilee_debates_alignment"
DEFAULT_DIARISATION_DIR = "corpus/05_jubilee_debates_diarisation"
DEFAULT_OUTPUT_DIR = "corpus/06_jubilee_debates_speaker_transcripts"

DEFAULT_LOG_FILE = (
    "corpus/06_jubilee_debates_speaker_transcripts/"
    "assign_speakers_jubilee_debates.log"
)
DEFAULT_MANIFEST_FILE = (
    "corpus/06_jubilee_debates_speaker_transcripts/"
    "assign_speakers_jubilee_debates_manifest.json"
)
DEFAULT_SPEAKER_INDEX_FILE = (
    "corpus/06_jubilee_debates_speaker_transcripts/"
    "jubilee_debates_speaker_assignment_index.ndjson"
)

DEFAULT_ASSIGNMENT_METHOD = "overlap"
DEFAULT_MIN_OVERLAP_RATIO = 0.0
DEFAULT_UNASSIGNED_SPEAKER_LABEL = "UNKNOWN_SPEAKER"

DEFAULT_MERGE_ADJACENT = True
DEFAULT_MAX_MERGE_GAP_SECONDS = 1.0
DEFAULT_MAX_SEGMENT_DURATION_SECONDS = 30.0
DEFAULT_MAX_SEGMENT_WORDS = 120

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 1
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

OUTPUT_SPEAKER_WORDS_JSON_EXTENSION = ".speaker_words.json"
OUTPUT_SPEAKER_WORDS_NDJSON_EXTENSION = ".speaker_words.ndjson"
OUTPUT_SPEAKER_SEGMENTS_JSON_EXTENSION = ".speaker_segments.json"
OUTPUT_SPEAKER_SEGMENTS_NDJSON_EXTENSION = ".speaker_segments.ndjson"
OUTPUT_SPEAKER_TRANSCRIPT_EXTENSION = ".speaker_transcript.txt"

ELIGIBLE_ALIGNMENT_STATUSES = ("success", "skipped_existing")
ELIGIBLE_DIARISATION_STATUSES = ("success", "skipped_existing")

ALLOWED_ASSIGNMENT_METHODS = ("overlap", "midpoint")
```


---

# 17. Development Notes

## 17.1 Initial implementation scope

The first implementation should prioritise:

- correct sequential execution;
- robust alignment index reading;
- robust diarisation index reading;
- matching by `corpus_id`;
- eligibility filtering by upstream statuses;
- robust input path resolution;
- loading aligned words from `.words.ndjson`;
- loading diarisation segments from `.segments.ndjson`;
- fallback loading from JSON where practical;
- overlap-based word speaker assignment;
- midpoint-based assignment as an optional mode;
- stable speaker word JSON and NDJSON outputs;
- stable speaker segment JSON and NDJSON outputs;
- readable plain-text speaker transcript output;
- reliable speaker-assignment index output;
- reliable logging;
- robust manifest writing;
- safe resumability;
- `--start-corpus-id` support;
- clear handling of missing timestamps and unknown speakers.

Parallel processing should not be implemented initially.

## 17.2 Speaker identity note

This programme must not identify real speakers.

It should preserve anonymous diarisation labels only:

```
SPEAKER_00
SPEAKER_01
SPEAKER_02
```


Human speaker identity mapping can be a later manual curation stage.

## 17.3 QC note

This programme should produce enough summary fields to support downstream QC, but it should not itself produce full QC reports.

Useful summary fields include:

- total words;
- assigned words;
- unassigned words;
- unknown-speaker words;
- number of speaker segments;
- number of assigned speakers;
- long unassigned spans;
- words with missing timestamps;
- words with multiple speaker candidates.

Full diagnostic reporting belongs in:

```
qc_jubilee_debates_speaker_diarisation.py
```


---

# 18. Acceptance Criteria

The programme is considered complete when:

1. Running from inside `cl_st1_ph0_carol/` works:

```
python assign_speakers_jubilee_debates.py
```


2. Running from project root works:

```
python cl_st1_ph0_carol/assign_speakers_jubilee_debates.py
```


3. Default paths are resolved relative to the programme directory.

4. It reads:

```
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
```


5. It reads:

```
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
```


6. It processes only debates with eligible alignment and diarisation statuses.

7. It matches records by `corpus_id`.

8. It uses source paths from index records when present and usable.

9. It falls back to:

```
corpus/04_jubilee_debates_alignment/<corpus_id>.aligned.json
corpus/04_jubilee_debates_alignment/<corpus_id>.words.ndjson
corpus/05_jubilee_debates_diarisation/<corpus_id>.diarisation.json
corpus/05_jubilee_debates_diarisation/<corpus_id>.segments.ndjson
```


10. It creates the output directory if needed:

```
corpus/06_jubilee_debates_speaker_transcripts/
```


11. Each successful assignment writes:

```
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_transcript.txt
```


12. The default assignment method is:

```
overlap
```


13. `--assignment-method midpoint` is supported.

14. Words with valid timestamps are assigned to the best matching diarisation speaker where possible.

15. Words without valid timestamps are preserved and marked as unassigned.

16. Existing complete speaker-assignment outputs are skipped unless `--reprocess` is used.

17. If only some outputs exist, the item is treated as incomplete and planned for assignment.

18. Failed assignments do not stop the full batch.

19. Missing input files are marked as `missing_input`.

20. Invalid eligible metadata rows are marked as `failed_metadata`.

21. The programme supports:

```
--start-corpus-id CORPUS_ID
```


22. If `--start-corpus-id` is not found among eligible matched records, the programme exits with configuration error.

23. A log file is written at:

```
corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates.log
```


24. A latest manifest is written at:

```
corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates_manifest.json
```


25. A timestamped per-run manifest is also written.

26. A speaker-assignment index is written at:

```
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
```


27. The speaker-assignment index is suitable as input to:

```
qc_jubilee_debates_speaker_diarisation.py
```


28. The programme exits with:
    - `0` for clean completion;
    - `1` for item-level failures, missing inputs, or invalid eligible metadata;
    - `2` for configuration errors;
    - `130` for keyboard interruption.

29. The programme does **not** transcribe, align, diarise, identify real speakers, or produce QC reports.

---

# 19. Short README Section

## Assign diarised speaker labels to Jubilee debate transcripts

The `assign_speakers_jubilee_debates.py` programme combines WhisperX alignment outputs with pyannote diarisation outputs to create speaker-attributed Jubilee debate transcripts.

It reads the alignment index:

```
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
```


and the diarisation index:

```
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
```


Only debates with both successful alignment and successful diarisation are processed.

Alignment files are resolved from index fields when available. Otherwise, the programme expects:

```
corpus/04_jubilee_debates_alignment/<corpus_id>.aligned.json
corpus/04_jubilee_debates_alignment/<corpus_id>.words.ndjson
```


Diarisation files are resolved from index fields when available. Otherwise, the programme expects:

```
corpus/05_jubilee_debates_diarisation/<corpus_id>.diarisation.json
corpus/05_jubilee_debates_diarisation/<corpus_id>.segments.ndjson
```


Speaker-attributed outputs are written to:

```
corpus/06_jubilee_debates_speaker_transcripts/
```


Each successful assignment writes:

```
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_transcript.txt
```


Default test run:

```
python assign_speakers_jubilee_debates.py
```


This processes one planned debate by default.

Full run:

```
python assign_speakers_jubilee_debates.py --no-test-mode
```


Resume from a specific debate:

```
python assign_speakers_jubilee_debates.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```


Force re-assignment:

```
python assign_speakers_jubilee_debates.py \
  --no-test-mode \
  --reprocess
```


Use midpoint assignment instead of overlap assignment:

```
python assign_speakers_jubilee_debates.py \
  --no-test-mode \
  --assignment-method midpoint
```


The programme writes:

```
corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates.log
corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates_manifest.json
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
```


A timestamped per-run manifest is also created.

This stage performs speaker assignment only. Speaker labels are anonymous diarisation labels, not real participant identities.