# Corpus Linguistics — Study 1 — Carol
# Phase 0 Manual Pipeline

This document records the manual commands used to run the Phase 0 Jubilee debate preparation and transcription pipeline.

It is not intended to be executed as a shell script. Commands should be copied and pasted into the terminal one stage at a time.

## Working directory

Run all commands from:
```
cd cl_st1_ph0_carol
```
## Pipeline overview

| Stage | Purpose                                                   | Programme                                |
|-------|-----------------------------------------------------------|------------------------------------------|
| 1     | Download Jubilee debate videos and metadata               | `download_jubilee_debates.py`            |
| 2     | Extract audio from downloaded videos                      | `extract_jubilee_debates_audio.py`       |
| 3     | Submit audio to Gemini for speaker-diarised transcription | `speaker_diarisation_jubilee_debates.py` |

## General notes

- Python programmes resolve their own default paths relative to their script directory.
- Existing outputs are skipped by default unless a reprocessing option is used.
- Test mode is enabled by default in some stages.
- Use full mode only after confirming that test outputs are correct.

## Stage 1 — Download Jubilee debate videos and metadata

### Test run
```
python download_jubilee_debates.py
```
### Full run
```
python download_jubilee_debates.py --no-test-mode
```
### Expected outputs
```
corpus/01_jubilee_debates/
```
## Stage 2 — Extract Jubilee debate audio

### Test run
```
python extract_jubilee_debates_audio.py
```
### Full run
```
python extract_jubilee_debates_audio.py --no-test-mode
```
### Expected outputs
```
corpus/02_jubilee_debates_audio/
```
## Stage 3 — Speaker diarisation with Gemini

### Test run
```
python speaker_diarisation_jubilee_debates.py
```
### Full run
```
python speaker_diarisation_jubilee_debates.py --no-test-mode
```
### Process a single debate
```
python speaker_diarisation_jubilee_debates.py --only-corpus-id CORPUS_ID
```
### Reprocess existing output
```
python speaker_diarisation_jubilee_debates.py --only-corpus-id CORPUS_ID --reprocess
```
### Expected outputs
```
corpus/02_jubilee_debates_speaker_diarisation/
```
## Manual run log

| Date       | Stage   | Command                                                  | Notes |
|------------|---------|----------------------------------------------------------|-------|
| YYYY-MM-DD | Stage 1 | `python download_jubilee_debates.py --no-test-mode`      |       |
| YYYY-MM-DD | Stage 2 | `python extract_jubilee_debates_audio.py --no-test-mode` |       |
| YYYY-MM-DD | Stage 3 | `python speaker_diarisation_jubilee_debates.py`          |       |
