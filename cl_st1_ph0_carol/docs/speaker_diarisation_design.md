## User request

Can you help me organise the processing of Speaker Diarisation with Whisper, WhisperX and pyannote.audio? First, please have a look at the attached documents from another project that used Whisper transcription. Does the same EC2 server sizing and problem resolution apply to this project?


## Short answer

**Partly, yes — but not completely.**

The **CUDA problem resolution from the earlier Whisper project is very likely relevant** to this project, because WhisperX and pyannote.audio also depend on GPU ML libraries. The earlier fix for:

```plain text
libcublas.so.12 is not found or cannot be loaded
```


is still a sensible starting point.

However, the **EC2 sizing should be treated more cautiously** for this project. This project is not just short-form Whisper transcription. It involves **long-form debate audio**, **alignment**, and **speaker diarisation**, with recordings around **1.5–1.9 hours each** and many speakers. That makes the workload heavier and more memory-sensitive than the commercial transcription project.

For this Jubilee debate phase, I would use the previous setup as a **baseline**, but I would not assume it is automatically sufficient for the whole workflow.

---

## 1. What carries over from the previous Whisper project?

### 1.1 The CUDA/cuBLAS issue probably carries over

The previous issue was:

```plain text
Library libcublas.so.12 is not found or cannot be loaded
```


That diagnosis and fix are still relevant because the likely stack here will include GPU-accelerated packages such as:

- `torch`
- `faster-whisper` / CTranslate2
- `whisperx`
- `pyannote.audio`
- CUDA runtime libraries
- cuBLAS
- possibly cuDNN

So the same principle applies:

> The Python environment that runs the speech pipeline must be able to find the CUDA runtime libraries required by the installed ML packages.

The previous resolution remains useful:

```shell script
conda create -n whisperx_pyannote python=3.11 -y
conda activate whisperx_pyannote

conda install -c nvidia cuda-toolkit=12 -y
conda install -c conda-forge cudnn -y

export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
```


And the persistent activation script is still a good idea:

```shell script
mkdir -p "$CONDA_PREFIX/etc/conda/activate.d"
nano "$CONDA_PREFIX/etc/conda/activate.d/env_vars.sh"
```


Add:

```shell script
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
```


Then reactivate:

```shell script
conda deactivate
conda activate whisperx_pyannote
```


So: **yes, keep that CUDA fix in the playbook.**

---

## 2. What does *not* carry over exactly?

### 2.1 The workload is substantially different

The previous project transcribed short commercial clips. This project processes **full-length Jubilee debates**.

The current selected sample has durations approximately:

| Corpus ID | Duration |
|---|---:|
| `jubilee_surrounded_001` | 1:30:27 |
| `jubilee_surrounded_002` | 1:40:53 |
| `jubilee_surrounded_003` | 1:38:23 |
| `jubilee_surrounded_004` | 1:53:38 |
| `jubilee_surrounded_005` | 1:29:47 |

Total current sample duration is about **8 hours 13 minutes** of audio.

That changes the engineering assumptions. Long debate audio means:

- higher risk of GPU memory pressure;
- much longer per-item runtime;
- more benefit from checkpointed outputs;
- greater need for resumability;
- higher risk of process interruption;
- more expensive reruns if output granularity is poor;
- more challenging diarisation because there may be many short turns and interruptions.

### 2.2 WhisperX + pyannote is heavier than faster-whisper transcription alone

A full WhisperX-style pipeline usually includes:

1. Whisper transcription;
2. forced alignment;
3. speaker diarisation;
4. assignment of speakers to words or segments;
5. output formatting.

The earlier commercial script only covered transcription. For this project, **diarisation is the most project-critical part**, and it introduces extra dependencies and model access requirements.

---

## 3. Does `g5.xlarge` still make sense?

### 3.1 As a starting point: yes

The earlier recommended instance:

```plain text
g5.xlarge
NVIDIA A10G
24 GB VRAM
x86_64
Ubuntu Deep Learning AMI
Python 3.11 conda environment
```


is a reasonable starting point for this project.

For the current **five-debate Phase 0 sample**, a `g5.xlarge` should be acceptable for sequential processing if:

- only one file is processed at a time;
- models are loaded carefully;
- outputs are checkpointed per debate;
- the programme can skip completed items;
- CUDA is correctly configured;
- disk space is sufficient.

### 3.2 But I would not run multiple workers on `g5.xlarge`

For this project, I would keep:

```plain text
workers = 1
```


Do not parallelise transcription/diarisation initially. Running multiple long debates at once could exhaust VRAM or RAM quickly.

### 3.3 When to consider a larger instance

Move up from `g5.xlarge` if you see:

- CUDA out-of-memory errors;
- pyannote diarisation failures on long files;
- alignment crashes;
- unacceptable runtime;
- repeated model unload/reload problems;
- CPU/RAM bottlenecks during diarisation.

Possible larger options:

| Instance | Use case |
|---|---|
| `g5.xlarge` | Good baseline; likely enough for sequential Phase 0 |
| `g5.2xlarge` | More CPU/RAM, same A10G GPU; safer for long audio orchestration |
| `g5.4xlarge` | More system memory and CPU; useful if preprocessing/alignment is CPU-heavy |
| `g6` family | Possible newer alternative if available and compatible |
| `p3.2xlarge` | Older V100 option; still usable but often less convenient/cost-effective |
| `p4` / `p5` | Overkill for this 5-file Phase 0 unless doing large-scale production |

For the current sample, I would start with:

```plain text
g5.xlarge for test run
g5.2xlarge if memory or runtime becomes uncomfortable
```


---

## 4. Important difference: pyannote.audio requires Hugging Face access

The earlier Whisper run could work without a Hugging Face token, although unauthenticated downloads might be rate-limited.

For pyannote.audio, this is usually more strict. Many pyannote models require:

1. a Hugging Face account;
2. accepting the model terms on Hugging Face;
3. setting an access token.

You should plan for an environment variable such as:

```shell script
export HF_TOKEN="hf_..."
```


or:

```shell script
huggingface-cli login
```


This is a key difference from the earlier Whisper-only project.

For this project, avoid putting the token into code, manifests, or logs.

---

## 5. Recommended environment strategy

I would **not** reuse the exact `whisper_lg_v3` environment unchanged. I would create a new environment for this project because WhisperX and pyannote introduce additional dependencies.

Recommended environment:

```shell script
conda create -n whisperx_pyannote python=3.11 -y
conda activate whisperx_pyannote
```


Then install core tooling. Exact versions may need pinning after testing, but conceptually:

```shell script
pip install --upgrade pip
pip install torch torchaudio
pip install faster-whisper
pip install whisperx
pip install pyannote.audio
pip install huggingface_hub
```


Then install or expose CUDA runtime libraries as before:

```shell script
conda install -c nvidia cuda-toolkit=12 -y
conda install -c conda-forge cudnn -y
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
```


And test:

```shell script
nvidia-smi
python -c "import torch; print(torch.cuda.is_available()); print(torch.version.cuda)"
python -c "import whisperx; print('whisperx import OK')"
python -c "import pyannote.audio; print('pyannote import OK')"
```


---

## 6. Project-specific processing plan

For this project, I recommend organising the pipeline into separate stages rather than one monolithic script.

You already have the sensible upstream stages:

```plain text
corpus/01_jubilee_debates/
corpus/02_jubilee_debates_audio/
```


The next stages could be:

```plain text
corpus/03_jubilee_debates_transcripts/
corpus/04_jubilee_debates_alignment/
corpus/05_jubilee_debates_diarisation/
corpus/06_jubilee_debates_speaker_transcripts/
corpus/07_jubilee_debates_qc/
```


Or, if you prefer fewer directories:

```plain text
corpus/03_jubilee_debates_speech_processing/
```


with subdirectories:

```plain text
corpus/03_jubilee_debates_speech_processing/
├── whisper_transcripts/
├── whisperx_alignment/
├── pyannote_diarisation/
├── speaker_attributed_transcripts/
├── manifests/
└── logs/
```


For reproducibility, I prefer separate top-level corpus stages.

---

## 7. Recommended pipeline stages

### Stage 1 — Audio extraction

Already handled by the audio extraction programme.

Input:

```plain text
corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```


Output:

```plain text
corpus/02_jubilee_debates_audio/<corpus_id>.wav
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


The audio format is appropriate:

```plain text
WAV
mono
16 kHz
signed 16-bit PCM
```


This is good for WhisperX and pyannote.

---

### Stage 2 — Whisper transcription

Input:

```plain text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```


Output:

```plain text
corpus/03_jubilee_debates_transcripts/<corpus_id>.txt
corpus/03_jubilee_debates_transcripts/<corpus_id>.json
```


The JSON should preserve:

- full text;
- segment timestamps;
- model name;
- language;
- compute type;
- source audio path;
- metadata from the audio index.

Recommended settings:

```plain text
model = large-v3
language = en
device = cuda
compute_type = float16
batch_size = conservative initially, e.g. 8 or 16
```


For long debate audio, begin conservatively. Do not optimise until the full pipeline works.

---

### Stage 3 — WhisperX alignment

Input:

```plain text
corpus/03_jubilee_debates_transcripts/<corpus_id>.json
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```


Output:

```plain text
corpus/04_jubilee_debates_alignment/<corpus_id>.aligned.json
```


This stage should add word-level or near-word-level timestamps.

This matters because diarisation is most useful when speaker labels can be assigned to words or short segments.

---

### Stage 4 — pyannote speaker diarisation

Input:

```plain text
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```


Output:

```plain text
corpus/05_jubilee_debates_diarisation/<corpus_id>.rttm
corpus/05_jubilee_debates_diarisation/<corpus_id>.json
```


The diarisation output should include intervals like:

```json
{
  "speaker": "SPEAKER_00",
  "start": 12.42,
  "end": 18.91
}
```


For Jubilee `Surrounded` debates, there may be many participants. Avoid hard-coding the number of speakers at first unless you have a known count.

Recommended first-pass settings:

```plain text
num_speakers = auto / unspecified
min_speakers = optional
max_speakers = optional, perhaps 30 for Surrounded-style debates
```


If the format consistently has one central guest plus around 20–25 participants, a later tuning pass could set:

```plain text
min_speakers = 8
max_speakers = 30
```


But I would not start with strict constraints until you inspect output quality.

---

### Stage 5 — speaker assignment / merged transcript

Input:

```plain text
corpus/04_jubilee_debates_alignment/<corpus_id>.aligned.json
corpus/05_jubilee_debates_diarisation/<corpus_id>.json
```


Output:

```plain text
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_transcript.txt
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.json
```


This stage should assign each word or segment to a diarised speaker label.

Example plain-text output:

```plain text
[SPEAKER_00 00:00:12.420-00:00:18.910]
I think the question we have to ask is whether college is still worth it.

[SPEAKER_03 00:00:19.200-00:00:24.640]
But that depends entirely on what kind of degree you're getting.
```


Important: diarised speaker labels are not real identities. They should initially remain:

```plain text
SPEAKER_00
SPEAKER_01
SPEAKER_02
```


Human speaker identification can be a later curation stage.

---

### Stage 6 — QC report

For each debate, create a QC summary:

```plain text
corpus/07_jubilee_debates_qc/<corpus_id>.qc.json
corpus/07_jubilee_debates_qc/<corpus_id>.qc.md
```


Useful QC fields:

- audio duration;
- transcript duration;
- number of Whisper segments;
- number of aligned words;
- number of diarised speakers;
- total diarised speech time;
- percentage of audio covered by diarisation;
- overlaps detected;
- long unassigned transcript spans;
- average words per speaker;
- top speakers by speaking time;
- warnings.

This is particularly important because debate audio is complex.

---

## 8. Recommended EC2 run order

On EC2, I would proceed like this.

### Step 1 — Verify audio extraction locally or on EC2

```shell script
python extract_jubilee_debates_audio.py
```


Then full run if needed:

```shell script
python extract_jubilee_debates_audio.py --no-test-mode
```


### Step 2 — Create the speech ML environment

```shell script
conda create -n whisperx_pyannote python=3.11 -y
conda activate whisperx_pyannote
```


Install dependencies and apply CUDA library path fix.

### Step 3 — Run a tiny smoke test

Use one debate only:

```shell script
python transcribe_jubilee_debates_whisperx.py \
  --test-limit 1
```


or, once built:

```shell script
python speaker_diarisation_jubilee_debates.py \
  --test-limit 1
```


### Step 4 — Inspect outputs manually

For one debate, check:

- Does Whisper produce a plausible transcript?
- Are timestamps reasonable?
- Does alignment complete?
- Does pyannote produce a plausible number of speakers?
- Are speaker labels switching too often?
- Are long stretches missing?

### Step 5 — Run all five debates sequentially

Use `tmux`:

```shell script
tmux new -s jubilee_speech
conda activate whisperx_pyannote
cd ~/cl_st1_carol/cl_st1_ph0_carol
python speaker_diarisation_jubilee_debates.py --no-test-mode
```


Detach:

```plain text
Ctrl+B
D
```


Reattach:

```shell script
tmux attach -t jubilee_speech
```


---

## 9. Practical sizing recommendation

For the current Phase 0 sample, I would use:

```plain text
Initial test: g5.xlarge
If unstable or slow: g5.2xlarge
Workers: 1
GPU: A10G 24 GB VRAM
Python: 3.11
Environment: dedicated conda env
Storage: at least 100–200 GB EBS for comfort
```


Why 100–200 GB? The videos, WAV files, model caches, transcripts, diarisation outputs, and intermediate JSON files can accumulate. The WAV files alone are not enormous but are not tiny either: 16 kHz mono PCM is roughly:

```plain text
32 KB/s
~115 MB/hour
```


For ~8.2 hours:

```plain text
~945 MB of WAV audio
```


The larger storage need comes from:

- downloaded MP4s;
- model caches;
- raw metadata;
- repeated output experiments;
- logs/manifests;
- possible temporary files.

So the audio itself is fine, but the project directory plus model cache should have headroom.

---

## 10. Key risks for this project

### 10.1 Many speakers

The `Surrounded` format may involve:

- one featured speaker;
- a moderator or host;
- many participants;
- audience reactions;
- interruptions;
- overlapping speech.

pyannote may produce speaker labels, but these labels will not automatically correspond to real participant names. Speaker identity curation may require manual review.

### 10.2 Overlapping speech

Debates often include interruptions. Diarisation can struggle with overlap. The output may assign only one speaker to a region where two people speak.

This is not necessarily a failure, but it should be documented in QC.

### 10.3 Channel mismatch is not useful here

The extracted audio is mono. That is appropriate for ASR, but it means there is no stereo separation to help diarisation.

### 10.4 `video_file` absolute paths

Some metadata paths are absolute local paths. On EC2, those exact absolute paths will not exist unless the project is copied to the same path. For audio processing, rely on the curated audio index and local extracted WAV paths, not the original machine-specific video paths.

### 10.5 Hugging Face token and pyannote model terms

This is probably the biggest non-code setup issue beyond CUDA.

---

## 11. Should Whisper, WhisperX, and pyannote be one programme or separate programmes?

For this project, I recommend **separate stages**, but possibly one orchestrating script later.

Best initial design:

1. `transcribe_jubilee_debates_whisperx.py`
2. `align_jubilee_debates_whisperx.py`
3. `diarise_jubilee_debates_pyannote.py`
4. `assign_speakers_jubilee_debates.py`

Or a combined first implementation:

```plain text
speaker_diarisation_jubilee_debates.py
```


that performs:

```plain text
transcribe -> align -> diarise -> assign speakers
```


For research reproducibility, the separate-stage approach is cleaner. For a small Phase 0 test, a combined script is faster to operate.

My recommendation:

> Build one combined Phase 0 script first, but make the output structure stage-aware so it can later be split cleanly.

---

## 12. Does the previous problem resolution apply?

### Yes, for:

- CUDA runtime library visibility;
- `LD_LIBRARY_PATH`;
- using Python 3.11;
- using a dedicated conda environment;
- testing GPU availability before long runs;
- using `tmux` or `nohup`;
- treating `/sys/class/drm/card0` warnings as non-fatal if inference succeeds;
- not relying on unauthenticated Hugging Face downloads for production reliability.

### Not exactly, for:

- EC2 runtime expectations;
- memory behaviour;
- model dependencies;
- Hugging Face authentication requirements;
- output structure;
- error handling complexity;
- QC requirements;
- diarisation quality evaluation.

---

## Recommended conclusion

Use the earlier EC2 setup as the **baseline**, especially the CUDA/cuBLAS fix, but treat this project as a **larger and more fragile speech-processing workflow**.

For Phase 0:

```plain text
Use g5.xlarge first.
Use Python 3.11 in a dedicated conda environment.
Install CUDA 12 runtime libraries into that environment.
Set LD_LIBRARY_PATH to the conda lib directory.
Use one worker only.
Run one debate first.
Inspect diarisation quality before processing all five.
Move to g5.2xlarge if memory/runtime is problematic.
```


The previous solution is therefore **applicable as infrastructure guidance**, but the diarisation pipeline needs **additional setup, stricter manifests, Hugging Face token handling, and stronger QC**.

## Stage planning

| Stage | Purpose                                                           | Programme name                              | Main output directory                            |
|------:|-------------------------------------------------------------------|---------------------------------------------|--------------------------------------------------|
|     1 | Transcribe full-length Jubilee debate audio with Whisper/WhisperX | `transcribe_jubilee_debates_whisperx.py`    | `corpus/03_jubilee_debates_transcripts/`         |
|     2 | Align transcript text to audio with WhisperX word/segment timing  | `align_jubilee_debates_whisperx.py`         | `corpus/04_jubilee_debates_alignment/`           |
|     3 | Run speaker diarisation with pyannote.audio                       | `diarise_jubilee_debates_pyannote.py`       | `corpus/05_jubilee_debates_diarisation/`         |
|     4 | Assign diarised speaker labels to aligned words/segments          | `assign_speakers_jubilee_debates.py`        | `corpus/06_jubilee_debates_speaker_transcripts/` |
|     5 | Produce quality-control summaries and diagnostics                 | `qc_jubilee_debates_speaker_diarisation.py` | `corpus/07_jubilee_debates_qc/`                  |

## EC2 requirement by stage

| Stage | Programme name                              |              Requires EC2 GPU? | Recommendation                                                                                    |
|------:|---------------------------------------------|-------------------------------:|---------------------------------------------------------------------------------------------------|
|     1 | `transcribe_jubilee_debates_whisperx.py`    |                        **Yes** | Run on EC2 GPU. This is Whisper/WhisperX transcription and benefits strongly from CUDA.           |
|     2 | `align_jubilee_debates_whisperx.py`         | **Yes / strongly recommended** | Run on EC2 GPU. WhisperX alignment uses ML models and is better kept in the same GPU environment. |
|     3 | `diarise_jubilee_debates_pyannote.py`       |                        **Yes** | Run on EC2 GPU. pyannote.audio diarisation is the most important GPU-dependent stage.             |
|     4 | `assign_speakers_jubilee_debates.py`        |                         **No** | Can run locally or on EC2 CPU. It mainly merges alignment output with diarisation intervals.      |
|     5 | `qc_jubilee_debates_speaker_diarisation.py` |                         **No** | Can run locally or on EC2 CPU. It mainly computes diagnostics and summary reports.                |

## Practical recommendation

Run **Stages 1–3 on EC2** in the dedicated Python 3.11 GPU environment:

```plain text
transcribe -> align -> diarise
```


Then you can either:

1. **keep running Stages 4–5 on EC2** for convenience, or  
2. **copy the outputs back locally** and run Stages 4–5 on your normal development machine.

For simplicity, I would initially run all five stages on EC2 during the first end-to-end test, but only **Stages 1–3 truly need the EC2 GPU instance**.
