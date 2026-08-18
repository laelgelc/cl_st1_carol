# Batch Debate Download and Audio Extraction

User:

In the production pipeline, we could focus on downloading a batch of debates, extract their audio, and delete the videos. What do you think?

AI Assistant:

I think that is a **very good production strategy** — and probably the right one if the pipeline scales beyond a small Phase 0 sample.

In practice, the MP4 video files are by far the largest artefacts. Once you have extracted the WAV audio and preserved the metadata/index, the videos are usually not needed for the automated speech pipeline.

## Why this makes sense

From your sample:

```
5 MP4 videos ≈ 10.76 GB
5 WAV audio files ≈ about 1 GB total, roughly
```


So the MP4s are roughly **10× larger** than the extracted audio.

If you delete videos after successful audio extraction, the same EC2 storage can support far more debates.

For example, on the current root volume:

```
Available root space: 135 GiB
Average MP4 size: ~2.0 GiB
Average WAV size: ~0.18–0.25 GiB for a 1.5h–2h debate
```


With videos retained, comfortable capacity is roughly:

```
~40–50 debates
```


With videos deleted after extraction, comfortable capacity could be closer to:

```
hundreds of debates
```


In practice, model caches, transcripts, diarisation outputs, logs, and safety margin still matter, but the storage pressure drops dramatically.

## Recommended production pattern

A good batch workflow would be:

1. **Download a batch of videos**
   - e.g. 10, 20, or 25 debates at a time.
2. **Extract WAV audio**
   - confirm that each expected `<corpus_id>.wav` exists.
3. **Verify audio extraction index**
   - ensure each item has `audio_extraction_status = success` or equivalent.
4. **Delete MP4 videos for successfully extracted audio**
   - keep metadata files and index files.
5. **Run speech pipeline on WAV audio**
   - transcribe;
   - align;
   - diarise;
   - assign speakers;
   - QC.
6. **Copy final outputs back / back up**
   - especially transcripts, speaker transcripts, QC reports, and indices.

## Important caution

I would delete videos **only after confirming**:

- the WAV exists;
- the WAV file size is non-zero;
- the audio index was written successfully;
- the original download metadata is preserved;
- the YouTube ID / URL / title / duration are preserved in the index.

For extra safety, you could also keep the videos until the downstream pipeline succeeds for the batch, then delete them. But if disk is tight, deleting immediately after successful audio extraction is reasonable.

## Suggested deletion policy

I would use one of these policies:

### Conservative policy

Delete MP4s only after:

```
audio extraction + transcription + alignment + diarisation + speaker assignment + QC all succeed
```


Pros: maximum reproducibility while processing.  
Cons: more disk usage.

### Practical production policy

Delete MP4s after:

```
audio extraction succeeds and audio index is written
```


Pros: much better disk use.  
Cons: if you later need to re-extract audio with different settings, you must re-download.

For this project, I think the **practical production policy is acceptable**, because:

- the extracted WAV is the real input for WhisperX and pyannote;
- the WAV format is already standardised;
- the source URL and metadata are preserved;
- videos can be re-downloaded if absolutely necessary.

## Recommended batch size

Given current storage and observed file sizes, a reasonable production batch size would be:

```
10–25 debates per batch
```


If using root volume only, I would start with:

```
10 debates per batch
```


If using the larger NVMe volume and backing up outputs carefully:

```
25–50 debates per batch
```


## Bottom line

Yes — I would design production around:

```
download batch -> extract audio -> verify WAV/index -> delete videos -> process WAVs
```


That will make the pipeline much more scalable and avoid wasting EC2 disk space on large MP4 files that are not needed after audio extraction.