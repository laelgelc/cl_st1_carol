# Corpus Linguistics - Study 1 - Phase 0 - Carol

Run the commands from the project phase directory, e.g.:

```text
cl_st1_ph0_carol/
```

## EC2 / environment setup reminder

For GPU stages, activate the dedicated speech-processing environment:

```shell script
conda activate whisperx_pyannote
```

Check GPU availability:

```shell script
nvidia-smi
python -c "import torch; print('cuda available:', torch.cuda.is_available()); print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```

Check core imports:

```shell script
python -c "import whisperx; print('whisperx OK')"
python -c "import pyannote.audio; print('pyannote.audio OK')"
python -c "from faster_whisper import WhisperModel; print('faster-whisper OK')"
```

Set Hugging Face token if required by pyannote:

```shell script
export HF_TOKEN="hf_..."
```

Do not commit, print, or paste the token into source files or logs.

## 1. Download Jubilee debate videos and metadata

### Test run

```shell script
python download_jubilee_debates.py
```

### Full run with cookies

Use this if YouTube requires browser cookies:

```shell script
python download_jubilee_debates.py \
    --no-test-mode \
    --cookies env/youtube_cookies.txt
```

### Expected outputs

```plain text
corpus/01_jubilee_debates/
```

## 2. Extract Jubilee debate audio

### Test run

```shell script
python extract_jubilee_debates_audio.py
```

### Full run

```shell script
python extract_jubilee_debates_audio.py --no-test-mode
```

### Force re-extraction

```shell script
python extract_jubilee_debates_audio.py \
  --no-test-mode \
  --reprocess
```

### Expected outputs

```plain text
corpus/02_jubilee_debates_audio/
```

Expected per-debate audio files:

```plain text
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```

Expected audio index:

```plain text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```

The extracted audio should be suitable for WhisperX and pyannote, normally:

```plain text
WAV
mono
16000 Hz
signed 16-bit PCM
```

## 3. Transcribe Jubilee debate audio with WhisperX

### Input

```plain text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```

### Default test run

```shell script
python transcribe_jubilee_debates_whisperx.py
```

### Explicit one-item test run

```shell script
python transcribe_jubilee_debates_whisperx.py --test-limit 1
```

### Full run

```shell script
python transcribe_jubilee_debates_whisperx.py --no-test-mode
```

### Resume from a specific debate

```shell script
python transcribe_jubilee_debates_whisperx.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

### Force re-transcription

```shell script
python transcribe_jubilee_debates_whisperx.py \
  --no-test-mode \
  --reprocess
```

### Optional smaller batch size

Use this if GPU memory is tight:

```shell script
python transcribe_jubilee_debates_whisperx.py \
  --no-test-mode \
  --batch-size 4
```

### Expected outputs

```plain text
corpus/03_jubilee_debates_transcripts/<corpus_id>.txt
corpus/03_jubilee_debates_transcripts/<corpus_id>.json
```

Expected index and run metadata:

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx.log
corpus/03_jubilee_debates_transcripts/transcribe_jubilee_debates_whisperx_manifest.json
```

A timestamped per-run manifest is also created.

## 4. Align Jubilee debate transcripts with WhisperX

### Input

```plain text
corpus/03_jubilee_debates_transcripts/jubilee_debates_transcript_index.ndjson
corpus/03_jubilee_debates_transcripts/<corpus_id>.json
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```

### Default test run

```shell script
python align_jubilee_debates_whisperx.py
```

### Explicit one-item test run

```shell script
python align_jubilee_debates_whisperx.py --test-limit 1
```

### Full run

```shell script
python align_jubilee_debates_whisperx.py --no-test-mode
```

### Resume from a specific debate

```shell script
python align_jubilee_debates_whisperx.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

### Force re-alignment

```shell script
python align_jubilee_debates_whisperx.py \
  --no-test-mode \
  --reprocess
```

### Expected outputs

```plain text
corpus/04_jubilee_debates_alignment/<corpus_id>.aligned.json
corpus/04_jubilee_debates_alignment/<corpus_id>.words.ndjson
```

Expected index and run metadata:

```plain text
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx.log
corpus/04_jubilee_debates_alignment/align_jubilee_debates_whisperx_manifest.json
```

A timestamped per-run manifest is also created.

## 5. Diarise Jubilee debate audio with pyannote.audio

### Input

```plain text
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
corpus/02_jubilee_debates_audio/<corpus_id>.wav
```

### Hugging Face authentication

Set a Hugging Face token if required:

```shell script
export HF_TOKEN="hf_..."
```

The token value must not be committed, logged, or written into any output file.

### Default test run

```shell script
python diarise_jubilee_debates_pyannote.py
```

### Explicit one-item test run without retry

Useful while debugging pyannote errors:

```shell script
python diarise_jubilee_debates_pyannote.py \
  --test-limit 1 \
  --max-retries 0
```

### Full run

```shell script
python diarise_jubilee_debates_pyannote.py --no-test-mode
```

### Resume from a specific debate

```shell script
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

### Force re-diarisation

```shell script
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --reprocess
```

### Optional speaker-count bounds

For later tuning, especially on `Surrounded`-style debates:

```shell script
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --min-speakers 8 \
  --max-speakers 30
```

### Expected outputs

```plain text
corpus/05_jubilee_debates_diarisation/<corpus_id>.rttm
corpus/05_jubilee_debates_diarisation/<corpus_id>.diarisation.json
corpus/05_jubilee_debates_diarisation/<corpus_id>.segments.ndjson
```

Expected index and run metadata:

```plain text
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote.log
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote_manifest.json
```

A timestamped per-run manifest is also created.

### Important metadata note

The diarisation index preserves source media duration as:

```plain text
duration_seconds
```

and records processing runtime separately as:

```plain text
diarisation_runtime_seconds
```

This distinction matters because downstream QC uses `duration_seconds` as the denominator for coverage metrics.

### Coverage note

The diarisation stage reports `total_speech_seconds` as the sum of diarised speaker interval durations. If speakers overlap, this sum can exceed the source media duration. Therefore QC coverage can be slightly above 100% without necessarily indicating an error.

## 6. Assign diarised speaker labels to aligned transcript words

### Purpose

Combine WhisperX alignment outputs with pyannote diarisation outputs to create speaker-attributed words, segments, and a readable speaker transcript.

This stage uses anonymous diarisation labels such as `SPEAKER_00`. It does not identify real participant names.

### Input

```plain text
corpus/04_jubilee_debates_alignment/jubilee_debates_alignment_index.ndjson
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
```

The programme resolves alignment and diarisation files from the indices when available.

### Default test run

```shell script
python assign_speakers_jubilee_debates.py
```

### Explicit one-item test run

```shell script
python assign_speakers_jubilee_debates.py --test-limit 1
```

### Full run

```shell script
python assign_speakers_jubilee_debates.py --no-test-mode
```

### Resume from a specific debate

```shell script
python assign_speakers_jubilee_debates.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

### Force re-assignment

```shell script
python assign_speakers_jubilee_debates.py \
  --no-test-mode \
  --reprocess
```

### Use midpoint assignment instead of overlap assignment

```shell script
python assign_speakers_jubilee_debates.py \
  --no-test-mode \
  --assignment-method midpoint
```

### Expected outputs

```plain text
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_words.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.json
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_segments.ndjson
corpus/06_jubilee_debates_speaker_transcripts/<corpus_id>.speaker_transcript.txt
```

Expected index and run metadata:

```plain text
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates.log
corpus/06_jubilee_debates_speaker_transcripts/assign_speakers_jubilee_debates_manifest.json
```

A timestamped per-run manifest is also created.

## 7. Produce QC reports for speaker diarisation

### Input

```plain text
corpus/06_jubilee_debates_speaker_transcripts/jubilee_debates_speaker_assignment_index.ndjson
```

The programme resolves speaker-assignment, alignment, and diarisation files from the index when available.

### Default test run

```shell script
python qc_jubilee_debates_speaker_diarisation.py
```

### Explicit one-item test run

```shell script
python qc_jubilee_debates_speaker_diarisation.py --test-limit 1
```

### Full run

```shell script
python qc_jubilee_debates_speaker_diarisation.py --no-test-mode
```

### Resume from a specific debate

```shell script
python qc_jubilee_debates_speaker_diarisation.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

### Force QC regeneration

```shell script
python qc_jubilee_debates_speaker_diarisation.py \
  --no-test-mode \
  --reprocess
```

### Expected per-debate outputs

```plain text
corpus/07_jubilee_debates_qc/<corpus_id>.qc.json
corpus/07_jubilee_debates_qc/<corpus_id>.qc.md
```

### Expected corpus-level outputs

```plain text
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_summary.json
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_summary.md
```

### Expected index and run metadata

```plain text
corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_index.ndjson
corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation.log
corpus/07_jubilee_debates_qc/qc_jubilee_debates_speaker_diarisation_manifest.json
```

A timestamped per-run manifest is also created.

### Inspect one QC report

```shell script
sed -n '1,220p' corpus/07_jubilee_debates_qc/jubilee_surrounded_001.qc.md
```

### Inspect corpus QC summary

```shell script
sed -n '1,220p' corpus/07_jubilee_debates_qc/jubilee_debates_speaker_diarisation_qc_summary.md
```

## Full one-debate smoke test sequence

Run this sequence before running the full corpus.

```shell script
conda activate whisperx_pyannote
cd ~/cl_st1_carol/cl_st1_ph0_carol

python transcribe_jubilee_debates_whisperx.py --test-limit 1
python align_jubilee_debates_whisperx.py --test-limit 1
python diarise_jubilee_debates_pyannote.py --test-limit 1
python assign_speakers_jubilee_debates.py --test-limit 1
python qc_jubilee_debates_speaker_diarisation.py --test-limit 1
```

After the smoke test, inspect:

```shell script
sed -n '1,220p' corpus/07_jubilee_debates_qc/jubilee_surrounded_001.qc.md
```

A successful smoke test should produce:

- a transcript;
- an aligned word file;
- diarisation RTTM/JSON/NDJSON;
- speaker-attributed word and segment files;
- a speaker transcript;
- a QC JSON and Markdown report.

## Full production run sequence

Run this only after the smoke test succeeds.

Use `tmux`:

```shell script
tmux new -s jubilee_speech
```

Inside the session:

```shell script
conda activate whisperx_pyannote
cd ~/cl_st1_carol/cl_st1_ph0_carol

python transcribe_jubilee_debates_whisperx.py --no-test-mode
python align_jubilee_debates_whisperx.py --no-test-mode
python diarise_jubilee_debates_pyannote.py --no-test-mode
python assign_speakers_jubilee_debates.py --no-test-mode
python qc_jubilee_debates_speaker_diarisation.py --no-test-mode
```

Detach from `tmux`:

```plain text
Ctrl+B
D
```

Reattach:

```shell script
tmux attach -t jubilee_speech
```

## Monitoring during EC2 runs

In another SSH session:

```shell script
watch -n 2 nvidia-smi
```

Useful system monitoring:

```shell script
htop
```

Disk usage:

```shell script
df -h
du -sh corpus/*
du -sh ~/.cache/huggingface
```

Project tree:

```shell script
tree -L 2 corpus
```

## Resume and reprocess patterns

### Resume from a specific debate

Use the same `--start-corpus-id` on the relevant stage:

```shell script
python transcribe_jubilee_debates_whisperx.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

```shell script
python align_jubilee_debates_whisperx.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

```shell script
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

```shell script
python assign_speakers_jubilee_debates.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```

```shell script
python qc_jubilee_debates_speaker_diarisation.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```
### Reprocess one or more stages

Use `--reprocess` on the stage whose outputs should be regenerated.

For example, to regenerate diarisation and all downstream outputs:

```shell script
python diarise_jubilee_debates_pyannote.py --no-test-mode --reprocess
python assign_speakers_jubilee_debates.py --no-test-mode --reprocess
python qc_jubilee_debates_speaker_diarisation.py --no-test-mode --reprocess
```

To regenerate only QC reports:

```shell script
python qc_jubilee_debates_speaker_diarisation.py --no-test-mode --reprocess
```

## Copy results back from EC2

After processing, copy generated outputs back to the local machine.

From the local machine:

```shell script
rsync -avz \
  -e "ssh -i ~/.ssh/carol-ec2.pem" \
  ubuntu@<EC2_PUBLIC_DNS_OR_IP>:~/cl_st1_carol/cl_st1_ph0_carol/corpus/03_jubilee_debates_transcripts/ \
  /local/path/cl_st1_carol/cl_st1_ph0_carol/corpus/03_jubilee_debates_transcripts/
```

Repeat for:

```plain text
corpus/04_jubilee_debates_alignment/
corpus/05_jubilee_debates_diarisation/
corpus/06_jubilee_debates_speaker_transcripts/
corpus/07_jubilee_debates_qc/
```

Or copy all corpus outputs at once:

```shell script
rsync -avz \
  -e "ssh -i ~/.ssh/carol-ec2.pem" \
  ubuntu@<EC2_PUBLIC_DNS_OR_IP>:~/cl_st1_carol/cl_st1_ph0_carol/corpus/ \
  /local/path/cl_st1_carol/cl_st1_ph0_carol/corpus/
```

Be careful when using `rsync`; it can overwrite local files depending on options.

## Cost-control checklist

When EC2 processing is complete:

1. Confirm that all required outputs were produced.
2. Confirm that important outputs have been copied back or backed up.
3. Confirm that no required files exist only on EC2.
4. Stop or terminate the EC2 instance.
5. Remove unused EBS volumes or snapshots if appropriate.

## Common problems and fixes

### `libcublas.so.12` not found

Symptom:

```plain text
Library libcublas.so.12 is not found or cannot be loaded
```

Fix:

```shell script
conda activate whisperx_pyannote
conda install -c nvidia cuda-toolkit=12 -y
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
```

Make persistent:

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

### CUDA is not available in PyTorch

Check:

```shell script
python -c "import torch; print(torch.cuda.is_available())"
```

If it prints:

```plain text
False
```

then check:

```shell script
nvidia-smi
```

If `nvidia-smi` works but PyTorch CUDA does not, reinstall PyTorch with CUDA-compatible wheels or use a compatible Deep Learning AMI.

### pyannote model access denied

Likely causes:

- Hugging Face token missing;
- model terms not accepted;
- token lacks required permissions.

Fix:

```shell script
huggingface-cli login
```

Then accept the required model terms in the Hugging Face web interface.

### pyannote output shape differs from expected

Recent pyannote versions may return a wrapper object such as `DiarizeOutput`, with the actual annotation in `speaker_diarization`.

The current diarisation programme should support this. If the error reappears, run a short diagnostic on a small audio excerpt and inspect the returned object type.

### CUDA out of memory

Possible fixes:

- ensure `--workers 1`;
- reduce batch size for transcription or alignment;
- process one debate at a time;
- restart the Python process between stages;
- move from `g5.xlarge` to `g5.2xlarge` or `g5.4xlarge`.

### Disk full

Check:

```shell script
df -h
du -sh corpus/*
du -sh ~/.cache/huggingface
```

Possible fixes:

- increase EBS size;
- remove temporary files;
- remove duplicated intermediate outputs;
- move completed outputs to local storage or S3.

### Diarisation coverage above 100%

QC may report diarisation coverage slightly above 100% because `total_speech_seconds` sums diarised speaker interval durations. Overlapping speech can cause the sum to exceed the source audio duration.

This is not necessarily a failure. However, very high values should be investigated because they may indicate:

- incorrect source duration metadata;
- excessive overlapping diarisation intervals;
- a bug in upstream index metadata.
