## Specification: `speaker_diarisation_jubilee_debates.py`

### 1. Programme purpose

`speaker_diarisation_jubilee_debates.py` submits Jubilee debate audio files to Gemini for transcript generation with speaker-turn differentiation.

The programme is part of the Phase 0 speaker-diarisation test for the Jubilee debate corpus. Its purpose is to assess whether Gemini can produce research-usable transcripts of multi-speaker debate audio, including:

1. faithful transcription of spoken content;
2. segmentation by speaker turn;
3. consistent anonymous speaker labels;
4. timestamps for each speaker turn;
5. preservation of interruptions, hesitations, incomplete utterances, and notable verbal reactions;
6. explicit marking of overlapping or unclear speech;
7. a short quality note identifying uncertain speaker-attribution regions.

The programme should use the Markdown prompt template:

```plain text
cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v1.md
```


by default, while allowing the template path to be overridden with a command-line argument.

The programme should use **Gemini 3.1 Pro** by default, while allowing the model name to be overridden with a command-line argument.

The programme should load `GEMINI_API_KEY` from:

```plain text
cl_st1_ph0_carol/env/.env
```


using `python-dotenv`.

The programme should save outputs in:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation
```


---

### 2. Inputs

#### 2.1 Prompt template

The programme should read the Markdown prompt template from:

```plain text
cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v1.md
```


Default CLI argument:

```shell script
--prompt-template cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v1.md
```


The prompt template is expected to contain the full instruction set for transcription and speaker diarisation.

The programme should not hard-code the diarisation prompt in the Python script, except as an optional emergency fallback if explicitly introduced later. The prompt template should be treated as the authoritative prompt text.

The programme should fail early with a clear error if:

- the prompt template file is missing;
- the prompt template file is empty;
- the prompt template cannot be read as text.

Recommended metadata to record:

```json
{
  "prompt_template": {
    "path": "cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v1.md",
    "sha256": "...",
    "character_count": 743
  }
}
```


---

#### 2.2 Environment file

The programme should load environment variables from:

```plain text
cl_st1_ph0_carol/env/.env
```


using `python-dotenv`.

Default CLI argument:

```shell script
--env-file cl_st1_ph0_carol/env/.env
```


The environment file should contain:

```plain text
GEMINI_API_KEY=...
```


The programme should fail early before any API call if:

- the `.env` file is missing;
- `python-dotenv` is unavailable;
- `GEMINI_API_KEY` is not present after loading the environment;
- `GEMINI_API_KEY` is empty.

The programme must never write the API key to:

- console output;
- logs;
- per-debate JSON outputs;
- run manifests;
- exception traces intentionally captured in output files.

Recommended run metadata:

```json
{
  "environment": {
    "env_file": "cl_st1_ph0_carol/env/.env",
    "dotenv_loaded": true,
    "gemini_api_key_present": true,
    "gemini_api_key_logged": false
  }
}
```


---

#### 2.3 Audio input directory

The programme should submit FLAC audio files generated for Gemini from:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac
```


Default CLI argument:

```shell script
--audio-dir cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac
```


Supported audio extension for this version:

```plain text
.flac
```


Each debate audio file is expected to be named after the debate `corpus_id`.

Expected path pattern:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/<corpus_id>.flac
```


Example:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/jubilee_surrounded_001.flac
```


The programme should validate and hash each audio file before submission.

Per-debate metadata should record:

- filename;
- path;
- extension;
- SHA-256 hash;
- byte size;
- whether the file was submitted to Gemini;
- upload/file API metadata if applicable;
- source role: `primary_audio_evidence`.

Recommended metadata:

```json
{
  "audio": {
    "filename": "jubilee_surrounded_001.flac",
    "path": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/jubilee_surrounded_001.flac",
    "format": "flac",
    "sha256": "...",
    "size_bytes": 123456789,
    "submitted": true,
    "role": "primary_audio_evidence"
  }
}
```


---

#### 2.4 Audio index

The programme should use the audio index, where available, to identify planned audio files and preserve metadata:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


Default CLI argument:

```shell script
--audio-index cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


The index should be read as newline-delimited JSON.

Each usable row should contain at least:

```plain text
corpus_id
```


Other metadata should be preserved where present.

The programme should process debates in index row order by default.

If no audio index is provided, or if an explicit option is used later, the programme may discover `.flac` files directly from the audio directory and process them in natural filename order.

Recommended default behaviour:

- use the audio index if it exists;
- fail early if `--audio-index` is explicitly provided and missing;
- optionally allow discovery-only mode with a future argument such as `--discover-audio-only`.

The programme should fail early with a clear error if:

- the audio index path is provided but missing;
- the audio index is empty;
- an NDJSON line is invalid JSON;
- an NDJSON row is not a JSON object;
- a row lacks `corpus_id`;
- duplicate `corpus_id` values are present.

Per-debate failures should be used if:

- a specific indexed audio file is missing;
- a specific indexed audio file has an unsupported extension;
- a specific indexed audio file cannot be read or hashed.

---

#### 2.5 Optional source debate index

The programme may optionally use the original debate metadata index to enrich reproducibility metadata:

```plain text
cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```


Recommended CLI argument:

```shell script
--debate-index cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```


This file should not be required for transcription, but if present it should be used to enrich output metadata with fields such as:

- `corpus_id`;
- `debate_format`;
- `sample_group`;
- `sample_order`;
- `title_selected`;
- `title_extracted`;
- `youtube_id`;
- `youtube_url`;
- `channel_extracted`;
- `duration_seconds`;
- `duration_string`;
- `chapters`;
- `video_file`;
- `download_status`;
- `metadata_status`.

If the optional debate index is missing, the programme should continue and record:

```json
{
  "debate_index_loaded": false
}
```


If the optional debate index is present but contains invalid NDJSON, the programme should fail early unless a future permissive mode is introduced.

---

### 3. Prompt handling

For each debate, the programme should submit:

1. the full prompt template text;
2. a neutral metadata note about the debate/audio file;
3. the FLAC audio file.

The prompt template should remain general and reusable. The programme may prepend or append a short neutral metadata block to the request, but this block must not alter the core transcription requirements or add interpretive instructions.

Recommended logical request structure:

```plain text
[prompt template text]

Debate audio metadata:
Corpus ID: jubilee_surrounded_001
Title: 1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)
Debate format: Surrounded
YouTube ID: WV29R1M25n8
Audio file: jubilee_surrounded_001.flac

Please apply the transcription and speaker-diarisation instructions above to the attached audio file.
```


The metadata note should be factual and should not ask the model to infer political, social, or theoretical interpretations. The purpose of this programme is transcription and speaker-turn differentiation, not discourse analysis.

The generated request text should be saved or reproducibly reconstructable from metadata.

Recommended per-debate metadata:

```json
{
  "prompt": {
    "template_path": "cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v1.md",
    "template_sha256": "...",
    "request_text_sha256": "...",
    "metadata_note_included": true,
    "metadata_note_sha256": "..."
  }
}
```


---

### 4. LLM submission

For each planned debate, the programme should submit the audio file and prompt to Gemini.

Default model:

```plain text
gemini-3.1-pro
```


Default CLI argument:

```shell script
--model gemini-3.1-pro
```


The model name should be configurable because Google model identifiers may differ by API version, availability, preview status, or account configuration.

The programme should be designed so the default can be changed centrally if the exact Gemini 3.1 Pro API identifier differs in practice.

Recommended CLI usage:

```shell script
python cl_st1_ph0_carol/speaker_diarisation_jubilee_debates.py \
  --model gemini-3.1-pro
```


The LLM request should include:

1. prompt text;
2. neutral debate/audio metadata note;
3. one `.flac` audio file.

The LLM request should not include:

- source video files;
- YouTube URLs as retrievable browsing targets;
- subtitles;
- automatic captions;
- prior transcripts;
- comments;
- unrelated metadata files.

This version should test Gemini’s ability to transcribe and diarise from the audio signal plus prompt instructions.

If future versions compare Gemini output against YouTube captions or other transcripts, those should be implemented as separate evaluation or benchmarking programmes, not silently added to this transcription request.

---

### 5. Output files

For each successfully processed debate, the programme should write:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/<corpus_id>.txt
cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/<corpus_id>.json
```


Example:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/jubilee_surrounded_001.txt
cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/jubilee_surrounded_001.json
```


The `.txt` file should contain only the clean model response, i.e. the diarised transcript and quality note.

The `.json` file should contain full reproducibility metadata, including:

- corpus ID;
- status;
- input paths;
- source metadata;
- prompt template path;
- prompt template hash;
- request text hash;
- audio file path;
- audio file hash;
- model configuration;
- API metadata;
- response metadata;
- response text;
- response text hash;
- timing metadata;
- retry metadata;
- errors, if any.

A failed `.txt` file is not required.

A failed `.json` file should still be written where possible.

---

### 6. Per-debate JSON output

#### 6.1 Recommended success structure

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "status": "success",
  "input": {
    "audio_index": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson",
    "debate_index": "cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson",
    "audio_file": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/jubilee_surrounded_001.flac",
    "prompt_template": "cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v1.md",
    "output_txt": "cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/jubilee_surrounded_001.txt",
    "output_json": "cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/jubilee_surrounded_001.json"
  },
  "source_metadata": {
    "audio_index_row": {},
    "debate_index_row": {
      "corpus_id": "jubilee_surrounded_001",
      "debate_format": "Surrounded",
      "sample_group": "carol_initial_sample",
      "sample_order": 1,
      "title_selected": "1 Conservative vs 25 Liberal College Students (Feat. Charlie Kirk)",
      "youtube_id": "WV29R1M25n8",
      "youtube_url": "https://www.youtube.com/watch?v=WV29R1M25n8",
      "duration_seconds": 5427,
      "duration_string": "1:30:27"
    }
  },
  "prompt": {
    "template_path": "cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v1.md",
    "template_sha256": "...",
    "template_character_count": 743,
    "metadata_note_included": true,
    "metadata_note_sha256": "...",
    "request_text_sha256": "..."
  },
  "audio": {
    "filename": "jubilee_surrounded_001.flac",
    "path": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/jubilee_surrounded_001.flac",
    "format": "flac",
    "sha256": "...",
    "size_bytes": 123456789,
    "submitted": true,
    "role": "primary_audio_evidence"
  },
  "model": {
    "provider": "google",
    "model": "gemini-3.1-pro",
    "temperature": 0,
    "temperature_sent_to_api": true,
    "max_output_tokens": null,
    "generation_config": {}
  },
  "api_metadata": {
    "uploaded_file": {},
    "response_id": null,
    "usage_metadata": {},
    "finish_reason": null,
    "safety_ratings": []
  },
  "response": {
    "text": "[00:00] Speaker A: ...",
    "text_sha256": "...",
    "character_count": 123456,
    "empty": false
  },
  "timing": {
    "started_at": "2026-08-03T00:00:00Z",
    "ended_at": "2026-08-03T00:05:00Z",
    "duration_seconds": 300.0
  },
  "retry": {
    "max_retries": 2,
    "attempts": 1,
    "succeeded_after_retry": false
  },
  "created_at": "2026-08-03T00:05:00Z",
  "error": null
}
```


---

#### 6.2 Recommended failure structure

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "status": "failed",
  "input": {
    "audio_index": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson",
    "debate_index": "cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson",
    "audio_file": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/jubilee_surrounded_001.flac",
    "prompt_template": "cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v1.md",
    "output_json": "cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/jubilee_surrounded_001.json"
  },
  "source_metadata": {
    "audio_index_row": {},
    "debate_index_row": {}
  },
  "audio": {
    "filename": "jubilee_surrounded_001.flac",
    "path": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/jubilee_surrounded_001.flac",
    "submitted": false,
    "role": "primary_audio_evidence"
  },
  "prompt": {
    "template_path": "cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v1.md",
    "template_sha256": "..."
  },
  "model": {
    "provider": "google",
    "model": "gemini-3.1-pro"
  },
  "timing": {
    "started_at": "2026-08-03T00:00:00Z",
    "ended_at": "2026-08-03T00:00:02Z",
    "duration_seconds": 2.0
  },
  "created_at": "2026-08-03T00:00:02Z",
  "error": "Missing audio file: cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/jubilee_surrounded_001.flac"
}
```


---

### 7. Run-level outputs

The programme should write run-level logs and manifests in:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation
```


Recommended files:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/speaker_diarisation_jubilee_debates.log
cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/speaker_diarisation_jubilee_debates_manifest.json
cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/speaker_diarisation_jubilee_debates_manifest_<RUN_ID>.json
```


The run manifest should include:

- run ID;
- programme name;
- start time;
- end time;
- duration;
- project/base directory;
- prompt template path;
- prompt template hash;
- environment file path;
- confirmation that `GEMINI_API_KEY` was present, without exposing the value;
- audio input directory;
- audio index path;
- optional debate index path;
- output directory;
- model configuration;
- processing strategy;
- number of audio index rows read;
- number of debates planned;
- number skipped;
- number submitted to Gemini;
- number succeeded;
- number failed;
- number failed because of missing audio;
- number failed because of invalid audio;
- number failed because of API error;
- number failed because of empty response;
- per-debate status list.

Recommended strategy metadata:

```json
{
  "strategy": {
    "task": "speaker_diarisation",
    "primary_evidence": "jubilee_debate_audio_flac",
    "model_provider": "google",
    "default_model": "gemini-3.1-pro",
    "transcript_generation": "prompted_gemini_audio_understanding",
    "speaker_labels": "model_generated_consistent_anonymous_labels",
    "timestamps": "model_generated_mm_ss_turn_timestamps",
    "subtitles_submitted": false,
    "video_submitted": false,
    "youtube_comments_submitted": false
  }
}
```


Recommended manifest structure:

```json
{
  "run_id": "20260803T120000Z",
  "programme": "speaker_diarisation_jubilee_debates.py",
  "status": "completed_with_failures",
  "started_at": "2026-08-03T12:00:00Z",
  "ended_at": "2026-08-03T12:30:00Z",
  "duration_seconds": 1800.0,
  "input": {
    "prompt_template": "cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v1.md",
    "env_file": "cl_st1_ph0_carol/env/.env",
    "audio_dir": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac",
    "audio_index": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson",
    "debate_index": "cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson"
  },
  "output": {
    "output_dir": "cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation",
    "log_file": "cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/speaker_diarisation_jubilee_debates.log",
    "manifest_file": "cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/speaker_diarisation_jubilee_debates_manifest_20260803T120000Z.json"
  },
  "model": {
    "provider": "google",
    "model": "gemini-3.1-pro",
    "temperature": 0,
    "max_output_tokens": null
  },
  "counts": {
    "audio_index_rows_read": 10,
    "debates_planned": 10,
    "skipped_existing": 0,
    "submitted": 9,
    "succeeded": 8,
    "failed": 2,
    "failed_missing_audio": 1,
    "failed_invalid_audio": 0,
    "failed_api_error": 1,
    "failed_empty_response": 0
  },
  "items": [
    {
      "corpus_id": "jubilee_surrounded_001",
      "status": "success",
      "audio_file": "cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac/jubilee_surrounded_001.flac",
      "output_txt": "cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/jubilee_surrounded_001.txt",
      "output_json": "cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/jubilee_surrounded_001.json"
    }
  ],
  "error": null
}
```


---

### 8. Processing order

Debates should be processed in audio-index row order by default.

Recommended processing sequence:

1. Parse CLI arguments.
2. Resolve all paths.
3. Create output directory if needed.
4. Configure logging.
5. Load `.env` with `python-dotenv`.
6. Validate `GEMINI_API_KEY`.
7. Validate Gemini SDK availability.
8. Load and validate prompt template.
9. Load audio index.
10. Optionally load debate index.
11. Validate global input directories and output directory.
12. Build processing plan.
13. Apply test-mode limit if enabled.
14. Apply `--start-corpus-id` if provided.
15. For each debate:
    - derive expected audio path;
    - validate audio file;
    - hash audio file;
    - check existing successful outputs;
    - skip unless `--reprocess`;
    - build request text from prompt plus neutral metadata note;
    - submit prompt and audio to Gemini;
    - extract response text;
    - write `.txt` output;
    - write `.json` metadata output;
    - log status.
16. Write run manifest.
17. Write/update latest manifest copy.

---

### 9. Existing-output skipping

Existing successful outputs should be skipped unless `--reprocess` is used.

A debate may be skipped if both files exist:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/<corpus_id>.txt
cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/<corpus_id>.json
```


and the JSON output records:

```json
"status": "success"
```


Skipped items should still be included in the run manifest with status:

```plain text
skipped_existing
```


The manifest item for a skipped debate should include:

- `corpus_id`;
- existing `.txt` path;
- existing `.json` path;
- previous model if available;
- previous prompt hash if available;
- skip reason.

Recommended skipped item:

```json
{
  "corpus_id": "jubilee_surrounded_001",
  "status": "skipped_existing",
  "reason": "Existing successful output found and --reprocess was not provided.",
  "output_txt": "cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/jubilee_surrounded_001.txt",
  "output_json": "cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/jubilee_surrounded_001.json",
  "previous_model": "gemini-3.1-pro",
  "previous_prompt_template_sha256": "..."
}
```


---

### 10. Command-line interface

Recommended CLI arguments:

| Argument | Default | Purpose |
|---|---:|---|
| `--prompt-template PATH` | `cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v1.md` | Markdown diarisation prompt template |
| `--env-file PATH` | `cl_st1_ph0_carol/env/.env` | Environment file loaded with `python-dotenv` |
| `--audio-dir PATH` | `cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac` | Gemini-ready FLAC audio input directory |
| `--audio-index PATH` | `cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson` | Audio index defining processing plan |
| `--debate-index PATH` | `cl_st1_ph0_carol/corpus/01_jubilee_debates/jubilee_debates_index.ndjson` | Optional debate metadata index |
| `--output-dir PATH` | `cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation` | Diarised transcript output directory |
| `--model MODEL` | `gemini-3.1-pro` | Gemini model identifier |
| `--temperature FLOAT` | `0` | Generation temperature |
| `--max-output-tokens N` | `0` | Optional output-token cap; `0` means API/default maximum |
| `--test-mode` | enabled | Process limited number of debates |
| `--no-test-mode` | disabled | Process all planned debates |
| `--test-limit N` | `1` | Number of debates to attempt in test mode |
| `--start-corpus-id ID` | `None` | Resume processing from a specific corpus ID |
| `--only-corpus-id ID` | `None` | Process only one specific debate |
| `--reprocess` | `False` | Regenerate existing successful outputs |
| `--workers N` | `1` | Number of concurrent workers |
| `--max-retries N` | `2` | API retry attempts |
| `--retry-backoff-seconds FLOAT` | `5.0` | Initial retry backoff |
| `--log-file PATH` | `<output-dir>/speaker_diarisation_jubilee_debates.log` | Optional explicit log file path |
| `--manifest-file PATH` | `<output-dir>/speaker_diarisation_jubilee_debates_manifest_<RUN_ID>.json` | Optional explicit run manifest path |

Recommended future arguments:

| Argument | Purpose |
|---|---|
| `--discover-audio-only` | Process `.flac` files discovered in the audio directory without an audio index |
| `--allow-missing-debate-index` | Continue if the optional debate index is missing |
| `--request-timeout-seconds N` | API request timeout, if supported by the SDK |
| `--delete-uploaded-files` | Delete Gemini uploaded file handles after response, if using a file-upload API |
| `--keep-uploaded-files` | Retain uploaded Gemini file handles for debugging/provenance |
| `--output-format {txt,json,txt-json}` | Select response output mode |
| `--prompt-metadata-note {on,off}` | Enable/disable neutral metadata note appended to prompt |

---

### 11. Example commands

#### 11.1 Default test run

```shell script
python cl_st1_ph0_carol/speaker_diarisation_jubilee_debates.py
```


This should:

- load `GEMINI_API_KEY` from `cl_st1_ph0_carol/env/.env`;
- read the default speaker diarisation prompt template;
- read the default audio index;
- process one debate in test mode;
- submit the prompt and one `.flac` audio file to Gemini;
- use `gemini-3.1-pro`;
- save outputs in `cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation`.

---

#### 11.2 Full run

```shell script
python cl_st1_ph0_carol/speaker_diarisation_jubilee_debates.py \
  --no-test-mode
```


---

#### 11.3 Reprocess all debates

```shell script
python cl_st1_ph0_carol/speaker_diarisation_jubilee_debates.py \
  --no-test-mode \
  --reprocess
```


---

#### 11.4 Use a different Gemini model

```shell script
python cl_st1_ph0_carol/speaker_diarisation_jubilee_debates.py \
  --model gemini-2.5-pro
```


---

#### 11.5 Use a different prompt template

```shell script
python cl_st1_ph0_carol/speaker_diarisation_jubilee_debates.py \
  --prompt-template cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v2.md
```


---

#### 11.6 Process only one debate

```shell script
python cl_st1_ph0_carol/speaker_diarisation_jubilee_debates.py \
  --only-corpus-id jubilee_surrounded_001
```


---

#### 11.7 Resume from a specific debate

```shell script
python cl_st1_ph0_carol/speaker_diarisation_jubilee_debates.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_004
```


---

#### 11.8 Use explicit paths

```shell script
python cl_st1_ph0_carol/speaker_diarisation_jubilee_debates.py \
  --prompt-template cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v1.md \
  --env-file cl_st1_ph0_carol/env/.env \
  --audio-dir cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac \
  --audio-index cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson \
  --output-dir cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation
```


---

### 12. Validation rules

The programme should fail before API calls if:

- the prompt template file does not exist;
- the prompt template file is empty;
- the prompt template cannot be read;
- the `.env` file does not exist;
- `python-dotenv` is unavailable;
- `GEMINI_API_KEY` is missing or empty;
- the Gemini Python SDK is unavailable;
- the audio directory does not exist;
- the audio index path is provided but does not exist;
- the audio index is empty;
- the audio index contains invalid NDJSON;
- an audio index row lacks `corpus_id`;
- duplicate `corpus_id` values are found in the audio index;
- the output directory cannot be created;
- the log file cannot be created;
- the manifest destination cannot be written;
- `--test-limit <= 0`;
- `--workers <= 0`;
- `--max-output-tokens < 0`;
- `--temperature < 0`;
- `--max-retries < 0`;
- `--retry-backoff-seconds < 0`;
- `--start-corpus-id` is provided but not found in the processing plan;
- `--only-corpus-id` is provided but not found in the processing plan.

The optional debate index should be validated if present. If it is missing, the recommended default is to continue with a warning because the audio index and audio files are sufficient for transcription.

The programme should fail early if the optional debate index is present but invalid, because invalid metadata risks corrupting reproducibility records.

---

### 13. Per-debate failure handling

A debate should be marked as failed, but the run should continue, if:

- the expected `.flac` audio file is missing;
- the audio file extension is unsupported;
- the audio file cannot be read;
- the audio file cannot be hashed;
- the audio file is empty;
- the request text cannot be constructed;
- the Gemini upload fails;
- the Gemini request fails after retries;
- the Gemini response contains no usable text;
- the `.txt` output cannot be written;
- the `.json` output cannot be written.

Each failure should be written to:

1. the run log;
2. the run manifest;
3. the per-debate JSON file, where possible.

A failure for one debate should not stop processing of later debates.

Recommended per-debate failure status values:

```plain text
failed_missing_audio
failed_invalid_audio
failed_audio_hash_error
failed_request_construction
failed_api_upload
failed_api_request
failed_empty_response
failed_output_write
```


---

### 14. API retry behaviour

The programme should retry transient API failures.

Default retry settings:

```plain text
--max-retries 2
--retry-backoff-seconds 5.0
```


Recommended strategy:

1. Attempt initial request.
2. If a retryable error occurs, wait `retry_backoff_seconds`.
3. Retry with exponential backoff.
4. Stop after `max_retries`.
5. Record all attempts in per-debate metadata.

Retryable errors may include:

- rate limits;
- temporary server errors;
- network timeouts;
- upload processing delays;
- transient SDK exceptions.

Non-retryable errors may include:

- missing API key;
- invalid model name;
- unsupported file type;
- malformed request;
- permission denied;
- file too large for the selected model/API.

Recommended retry metadata:

```json
{
  "retry": {
    "max_retries": 2,
    "attempts": 3,
    "backoff_seconds_initial": 5.0,
    "errors": [
      {
        "attempt": 1,
        "error_type": "RateLimitError",
        "message": "Rate limit exceeded"
      },
      {
        "attempt": 2,
        "error_type": "RateLimitError",
        "message": "Rate limit exceeded"
      }
    ],
    "succeeded_after_retry": true
  }
}
```


---

### 15. Logging

The programme should write a log file to:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation/speaker_diarisation_jubilee_debates.log
```


unless overridden by:

```shell script
--log-file PATH
```


The log should include:

- run ID;
- start/end time;
- resolved input paths;
- resolved output paths;
- selected model;
- test/full mode;
- processing plan summary;
- per-debate start;
- per-debate skip/success/failure;
- retry attempts;
- manifest path.

The log must not include:

- `GEMINI_API_KEY`;
- raw API authentication headers;
- full environment dumps.

Recommended log lines:

```plain text
2026-08-03T12:00:00Z INFO Run started: 20260803T120000Z
2026-08-03T12:00:00Z INFO Model: gemini-3.1-pro
2026-08-03T12:00:01Z INFO Planned debates: 10
2026-08-03T12:00:02Z INFO Processing jubilee_surrounded_001
2026-08-03T12:05:00Z INFO Success jubilee_surrounded_001
2026-08-03T12:05:01Z WARNING Failed jubilee_surrounded_002: Missing audio file
2026-08-03T12:30:00Z INFO Run completed_with_failures
```


---

### 16. Output text expectations

The `.txt` output should preserve the model response as cleanly as possible.

The expected response format is:

```plain text
[MM:SS] Speaker A: ...

[MM:SS] Speaker B: ...

[MM:SS] Speaker C: ...

Quality note: ...
```


The programme should not attempt to heavily post-process the transcript in this version.

Permitted minimal processing:

- trim leading/trailing whitespace;
- normalize final newline;
- extract text from SDK response object;
- preserve Markdown/plain-text formatting returned by the model.

The programme should not:

- correct the transcript;
- rename speakers;
- merge or split speaker turns;
- infer missing timestamps;
- remove uncertainty markers;
- remove the quality note;
- translate the transcript.

The aim is to preserve Gemini’s output for later evaluation.

---

### 17. Reproducibility requirements

For each debate, the programme should record enough metadata to reproduce or audit the request.

Required reproducibility fields:

- programme name;
- run ID;
- created timestamp;
- corpus ID;
- audio path;
- audio SHA-256;
- audio byte size;
- prompt template path;
- prompt template SHA-256;
- request text SHA-256;
- model name;
- temperature;
- max output token setting;
- SDK/API metadata where available;
- response text SHA-256;
- source index row where available;
- debate metadata row where available;
- retry count;
- duration.

The programme should record that:

```json
{
  "subtitles_submitted": false,
  "video_submitted": false,
  "comments_submitted": false,
  "prior_transcript_submitted": false
}
```


This matters methodologically because this programme is testing diarisation from audio input, not from existing captions.

---

### 18. Data-protection and research-integrity notes

The source material is public YouTube debate content, but the programme should still behave conservatively.

The programme should:

- avoid logging secrets;
- avoid adding interpretive claims to prompts;
- keep transcripts as model outputs, not ground truth;
- record that speaker labels are model-generated;
- preserve uncertainty markers;
- preserve quality notes;
- keep failed and successful metadata for audit.

Recommended per-debate methodological metadata:

```json
{
  "methodological_notes": {
    "transcript_status": "model_generated_not_ground_truth",
    "speaker_labels": "anonymous_model_generated_labels",
    "speaker_label_consistency": "requested_but_not_guaranteed",
    "timestamps": "model_generated_approximate",
    "overlap_detection": "requested_but_not_guaranteed",
    "quality_note_requested": true
  }
}
```


---

### 19. Acceptance criteria

The specification is implemented acceptably when:

1. The programme is named:

```plain text
speaker_diarisation_jubilee_debates.py
```


2. The programme reads the default prompt template from:

```plain text
cl_st1_ph0_carol/speaker_diarisation_prompts/speaker_diarisation_v1.md
```


3. The prompt template path is configurable via:

```shell script
--prompt-template
```


4. The programme uses Gemini 3.1 Pro by default.

5. The model is configurable via:

```shell script
--model
```


6. The programme loads:

```plain text
cl_st1_ph0_carol/env/.env
```


   using `python-dotenv`.

7. The programme reads `GEMINI_API_KEY` from the loaded environment.

8. The programme never logs the Gemini API key.

9. The programme reads Gemini-ready FLAC audio files from:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/gemini_flac
```


10. The audio input directory is configurable via:

```shell script
--audio-dir
```


11. The programme uses the audio index:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


   by default.

12. The audio index path is configurable via:

```shell script
--audio-index
```


13. The programme preserves debate/audio metadata in per-debate JSON outputs where available.

14. The programme submits the prompt and one `.flac` audio file per debate to Gemini.

15. The programme does not submit source video files.

16. The programme does not submit existing subtitles or automatic captions.

17. The programme does not submit YouTube comments.

18. The programme saves `.txt` outputs in:

```plain text
cl_st1_ph0_carol/corpus/02_jubilee_debates_speaker_diarisation
```


19. The programme saves `.json` metadata outputs in the same directory.

20. Per-debate output naming follows:

```plain text
<corpus_id>.txt
   <corpus_id>.json
```


21. Existing successful outputs are skipped unless `--reprocess` is used.

22. Skipped debates are recorded in the run manifest.

23. Per-debate failures are logged and do not stop the whole run.

24. The programme writes a run-level log.

25. The programme writes a run-level manifest.

26. The programme writes a run-level manifest with a run-specific filename.

27. The programme supports test mode by default.

28. The programme supports full-run mode via:

```shell script
--no-test-mode
```


29. The programme supports resuming from a corpus ID via:

```shell script
--start-corpus-id
```


30. The programme supports processing a single debate via:

```shell script
--only-corpus-id
```


31. Prompt hashes, request hashes, audio hashes, model configuration, response text, and response hashes are recorded.

32. The `.txt` response preserves Gemini’s diarised transcript without corrective post-processing.

33. The `.json` metadata records that the transcript is model-generated and not ground truth.

34. The `.json` metadata records that timestamps and speaker labels are model-generated and may require later validation.

35. The programme exits with a non-zero status for global validation failures.

36. The programme completes with a run manifest for per-debate failures where possible.