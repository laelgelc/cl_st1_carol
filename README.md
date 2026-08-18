# Corpus Linguistics - Study 1 - Carol

## Phase 0 - Speaker Diarisation Test

This phase evaluates whether Jubilee debate videos can be converted into reliable speaker-attributed transcripts for later corpus linguistic and LLM-response analysis.

### Update: Initial LLM-based diarisation strategy

The initial strategy was to test whether recent multimodal LLMs, especially Gemini 3.1 preview, could directly transcribe Jubilee debate audio/video while also distinguishing speaker turns. This approach was attractive because it promised a simpler workflow: one model would receive the debate media and return a transcript with timestamps and speaker labels.

However, this strategy did not succeed sufficiently for the project’s research needs. In practice, LLM-based speaker diarisation was not reliable enough for long, multi-party Jubilee debates, especially where the videos include:

- many speakers;
- rapid turn-taking;
- interruptions;
- overlapping speech;
- emotionally charged exchanges;
- inconsistent or ambiguous speaker identification;
- long-form audio/video segments.

The main limitation is that speaker labels generated directly by an LLM are not stable enough to be treated as research-grade diarisation. Even when the model can produce a plausible transcript, it may confuse speakers, change speaker labels over time, omit short turns, or fail to represent overlaps and interruptions consistently.

As a result, the project has moved away from direct LLM-based diarisation as the primary workflow.

The current approach separates the speech-processing pipeline into more controlled stages:

1. transcribe the debate audio with WhisperX;
2. align transcript words and segments to the audio timeline;
3. perform dedicated speaker diarisation with pyannote.audio;
4. assign diarised speaker labels to aligned transcript words;
5. run quality-control checks on the resulting speaker-attributed transcripts.

This staged approach is more complex, but it is better suited to reproducibility, inspection, correction, and quality control. LLMs may still be useful later in the project for analysis, interpretation, prompting experiments, or comparison, but they are no longer treated as the primary mechanism for producing the speaker-diarised corpus.

### Update: EC2 GPU server availability

The GPU-heavy stages of the speech-processing pipeline require access to an AWS EC2 GPU instance, with `g5.xlarge` recommended as the initial server type and `g5.2xlarge` or `g5.4xlarge` as possible larger alternatives if memory or runtime becomes problematic.

At the moment, availability of a `g5.xlarge` server or a superior GPU server in the AWS South America region depends on approval of the following AWS quota increase request:

```
plain text
Region: South America (São Paulo)
Service: EC2 Instances
Quota: All G and VT instances
Requested new limit: 16
```

Until this quota increase is approved, the project may not be able to launch the required GPU server for WhisperX transcription, WhisperX alignment, and pyannote.audio diarisation.

### Transcribe Jubilee debate audio with WhisperX

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

### Align Jubilee debate transcripts with WhisperX

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

### Diarise Jubilee debate audio with pyannote.audio

The `diarise_jubilee_debates_pyannote.py` programme performs speaker diarisation on extracted Jubilee debate WAV audio using pyannote.audio.

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
Diarisation outputs are written to:
```plain text
corpus/05_jubilee_debates_diarisation/
```
Each successful diarisation writes:
```plain text
corpus/05_jubilee_debates_diarisation/<corpus_id>.rttm
corpus/05_jubilee_debates_diarisation/<corpus_id>.diarisation.json
corpus/05_jubilee_debates_diarisation/<corpus_id>.segments.ndjson
```
Set Hugging Face authentication before running if required:
```shell script
export HF_TOKEN="hf_..."
```
Default test run:
```shell script
python diarise_jubilee_debates_pyannote.py
```
This processes one planned debate by default.

Full run:
```shell script
python diarise_jubilee_debates_pyannote.py --no-test-mode
```
Resume from a specific debate:
```shell script
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --start-corpus-id jubilee_surrounded_003
```
Force re-diarisation:
```shell script
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --reprocess
```
Optional speaker-count bounds:
```shell script
python diarise_jubilee_debates_pyannote.py \
  --no-test-mode \
  --min-speakers 8 \
  --max-speakers 30
```
The programme writes:
```plain text
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote.log
corpus/05_jubilee_debates_diarisation/diarise_jubilee_debates_pyannote_manifest.json
corpus/05_jubilee_debates_diarisation/jubilee_debates_diarisation_index.ndjson
```
A timestamped per-run manifest is also created.

The diarisation index preserves source media duration as `duration_seconds` and records processing runtime separately as `diarisation_runtime_seconds`.

This stage performs diarisation only. Transcription, alignment, speaker assignment, and QC are handled by separate pipeline stages.

### Assign diarised speaker labels to Jubilee debate transcripts

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

### Produce QC reports for Jubilee debate speaker diarisation

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

### Note: Observed Phase 0 processing time

Based on the completed EC2 GPU runs for the five initial `Surrounded` Jubilee debates, the current staged pipeline is substantially faster than real time on a `g5.xlarge` instance with an NVIDIA A10G GPU.

For a roughly **1h30m** debate, the observed processing time from available WAV audio to speaker-attributed transcript and QC report is approximately:
```plain text
10–12 minutes per debate
```
Including video download, which depends on YouTube/network conditions and may require cookies, a safer estimate is:
```plain text
12–17 minutes per debate
```
For the five-debate Phase 0 sample, the observed/supported planning estimate is:
```plain text
~1h15m expected total processing time
~1h30m–2h safe operational budget, including download variability
```
The main processing bottleneck is **pyannote.audio diarisation**. WhisperX transcription and alignment are comparatively fast on the tested EC2 GPU setup, while speaker assignment and QC take only seconds per debate.


