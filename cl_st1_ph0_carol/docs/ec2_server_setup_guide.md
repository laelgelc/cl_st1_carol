# EC2 Server Setup Guide for Jubilee Debate Speech Processing

This guide describes how to set up an AWS EC2 GPU server for the **Corpus Linguistics — Study 1 — Carol, Phase 0** speech-processing pipeline.

The EC2 server is intended primarily for the GPU-heavy stages:

| Stage | Programme                                   | EC2 GPU needed?          |
|------:|---------------------------------------------|--------------------------|
|     1 | `transcribe_jubilee_debates_whisperx.py`    | **Yes**                  |
|     2 | `align_jubilee_debates_whisperx.py`         | **Strongly recommended** |
|     3 | `diarise_jubilee_debates_pyannote.py`       | **Yes**                  |
|     4 | `assign_speakers_jubilee_debates.py`        | No                       |
|     5 | `qc_jubilee_debates_speaker_diarisation.py` | No                       |

For simplicity, the first end-to-end run may be performed entirely on EC2, but only Stages **1–3** truly require GPU acceleration.

---

## 1. Recommended EC2 configuration

### 1.1 Initial instance recommendation

For the current five-debate Phase 0 sample, start with:

```plain text
Instance type: g5.xlarge
GPU: NVIDIA A10G
GPU memory: 24 GB VRAM
Architecture: x86_64
Operating system: Ubuntu
AMI: AWS Deep Learning AMI GPU Ubuntu
EBS storage: 100–200 GB
Workers: 1
```


`g5.xlarge` is a good initial choice because it provides an NVIDIA A10G GPU with enough VRAM for a sequential WhisperX/pyannote workflow.

### 1.2 When to use a larger instance

Consider moving to `g5.2xlarge` or `g5.4xlarge` if you encounter:

- CUDA out-of-memory errors;
- pyannote diarisation failures on long files;
- very slow alignment or diarisation;
- CPU or RAM bottlenecks;
- repeated model-loading instability.

Recommended escalation path:

| Instance     | When to use                                                                    |
|--------------|--------------------------------------------------------------------------------|
| `g5.xlarge`  | First test and likely sufficient for Phase 0                                   |
| `g5.2xlarge` | More CPU/RAM, same A10G GPU; safer for long runs                               |
| `g5.4xlarge` | More CPU/RAM again; useful if alignment/diarisation orchestration is CPU-heavy |
| `p4` / `p5`  | Usually overkill for the current five-file Phase 0                             |

---

## 2. AWS setup checklist

### 2.1 Launch instance

In the AWS EC2 console:

1. Choose **Launch instance**.
2. Select an Ubuntu **Deep Learning AMI GPU**.
3. Choose instance type:

```plain text
g5.xlarge
```


4. Configure EBS storage:

```plain text
100–200 GB
```


5. Create or select a key pair.
6. Configure a security group allowing SSH:

```plain text
TCP 22 from your IP only
```


7. Launch the instance.

### 2.2 Connect to the instance

From your local machine:

```shell script
ssh -i /path/to/key.pem ubuntu@<EC2_PUBLIC_DNS_OR_IP>
```


Example:

```shell script
ssh -i ~/.ssh/carol-ec2.pem ubuntu@ec2-00-000-000-000.compute-1.amazonaws.com
```


Make sure your key permissions are restricted:

```shell script
chmod 400 ~/.ssh/carol-ec2.pem
```


---

## 3. Verify GPU availability

After connecting to the instance, run:

```shell script
nvidia-smi
```


Expected result:

- NVIDIA driver is visible;
- A10G GPU is listed;
- CUDA version is shown;
- no driver errors.

If `nvidia-smi` fails, stop here and fix the EC2/AMI/GPU driver setup before installing Python dependencies.

---

## 4. Update system packages

Run:

```shell script
sudo apt update
sudo apt upgrade -y
```


Install useful command-line tools:

```shell script
sudo apt install -y git tmux htop tree ffmpeg unzip rsync
```


Verify `ffmpeg`:

```shell script
ffmpeg -version
```


This is useful for audio extraction and general media diagnostics.

---

## 5. Set up the project directory

Choose a working location, for example:

```shell script
cd ~
```


Clone the project repository if it is in Git:

```shell script
git clone <YOUR_REPOSITORY_URL> cl_st1_carol
```


Then enter the project phase directory:

```shell script
cd ~/cl_st1_carol/cl_st1_ph0_carol
```


If the project is not cloned from Git, copy it using `rsync` or `scp` from your local machine.

Example from your local machine:

```shell script
rsync -avz \
  -e "ssh -i ~/.ssh/carol-ec2.pem" \
  /local/path/cl_st1_carol/ \
  ubuntu@<EC2_PUBLIC_DNS_OR_IP>:~/cl_st1_carol/
```


---

## 6. Transfer or prepare corpus files

You need the project files and the corpus inputs required by the speech-processing stages.

At minimum, EC2 should have:

```plain text
cl_st1_carol/
└── cl_st1_ph0_carol/
    ├── corpus/
    │   ├── 01_jubilee_debates/
    │   └── 02_jubilee_debates_audio/
    ├── extract_jubilee_debates_audio.py
    └── future speech-processing programmes
```


For Stages 1–3, the most important files are:

```plain text
corpus/02_jubilee_debates_audio/<corpus_id>.wav
corpus/02_jubilee_debates_audio/jubilee_debates_audio_index.ndjson
```


If audio has not yet been extracted, also transfer:

```plain text
corpus/01_jubilee_debates/videos/<corpus_id>.mp4
corpus/01_jubilee_debates/jubilee_debates_index.ndjson
```


Then run audio extraction on EC2:

```shell script
python extract_jubilee_debates_audio.py --no-test-mode
```


However, if the WAV files already exist locally, it is usually simpler to copy `corpus/02_jubilee_debates_audio/` directly.

---

## 7. Install or activate Conda

Most AWS Deep Learning AMIs already include Conda.

Check:

```shell script
conda --version
```


If Conda is available, initialise it if needed:

```shell script
conda init bash
source ~/.bashrc
```


If `conda` is not available, install Miniconda or use an AMI that includes Conda.

---

## 8. Create the speech-processing Conda environment

Create a dedicated Python 3.11 environment:

```shell script
conda create -n whisperx_pyannote python=3.11 -y
conda activate whisperx_pyannote
```


Upgrade `pip`:

```shell script
python -m pip install --upgrade pip setuptools wheel
```


---

## 9. Install CUDA runtime libraries into the Conda environment

This project may require CUDA runtime libraries to be visible inside the active Python environment.

Install CUDA 12 runtime libraries:

```shell script
conda install -c nvidia cuda-toolkit=12 -y
```


Install cuDNN if needed:

```shell script
conda install -c conda-forge cudnn -y
```


Set the library path for the current shell:

```shell script
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
```


Make it persistent for this Conda environment:

```shell script
mkdir -p "$CONDA_PREFIX/etc/conda/activate.d"
nano "$CONDA_PREFIX/etc/conda/activate.d/env_vars.sh"
```


Add:

```shell script
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
```


Save, then reactivate:

```shell script
conda deactivate
conda activate whisperx_pyannote
```


Check:

```shell script
echo "$LD_LIBRARY_PATH"
```


The beginning of the output should include the Conda environment library directory, for example:

```plain text
/home/ubuntu/miniconda3/envs/whisperx_pyannote/lib
```


This helps avoid errors such as:

```plain text
Library libcublas.so.12 is not found or cannot be loaded
```


---

## 10. Install Python speech-processing packages

Install PyTorch, WhisperX, pyannote, and support packages.

A practical starting point is:

```shell script
pip install torch torchaudio
pip install faster-whisper
pip install whisperx
pip install pyannote.audio
pip install huggingface_hub
pip install tqdm
```


If package version conflicts occur, resolve them inside this environment rather than changing the project’s general Python environment.

---

## 11. Verify Python/GPU package setup

Run these checks:

```shell script
python --version
```


Expected:

```plain text
Python 3.11.x
```


Check PyTorch CUDA:

```shell script
python -c "import torch; print('torch:', torch.__version__); print('cuda available:', torch.cuda.is_available()); print('cuda version:', torch.version.cuda); print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```


Expected:

```plain text
cuda available: True
device: NVIDIA A10G
```


Check WhisperX import:

```shell script
python -c "import whisperx; print('whisperx import OK')"
```


Check pyannote import:

```shell script
python -c "import pyannote.audio; print('pyannote.audio import OK')"
```


Check faster-whisper import:

```shell script
python -c "from faster_whisper import WhisperModel; print('faster-whisper import OK')"
```


---

## 12. Configure Hugging Face access

pyannote.audio models often require Hugging Face access.

### 12.1 Create or use a Hugging Face token

On Hugging Face:

1. Log in.
2. Create an access token.
3. Accept the required model terms for the pyannote models you plan to use.

### 12.2 Log in on EC2

Option A — interactive login:

```shell script
huggingface-cli login
```


Paste the token when prompted.

Option B — environment variable:

```shell script
export HF_TOKEN="hf_your_token_here"
```


To make it persistent for the Conda environment:

```shell script
nano "$CONDA_PREFIX/etc/conda/activate.d/hf_token.sh"
```


Add:

```shell script
export HF_TOKEN="hf_your_token_here"
```


Then:

```shell script
conda deactivate
conda activate whisperx_pyannote
```


### 12.3 Security warning

Do **not**:

- commit the Hugging Face token to Git;
- print it in logs;
- include it in manifests;
- paste it into programme source code.

If using `hf_token.sh`, ensure the file is only readable by your user:

```shell script
chmod 600 "$CONDA_PREFIX/etc/conda/activate.d/hf_token.sh"
```


---

## 13. Recommended project execution layout

The staged pipeline should produce outputs like:

```plain text
corpus/
├── 02_jubilee_debates_audio/
├── 03_jubilee_debates_transcripts/
├── 04_jubilee_debates_alignment/
├── 05_jubilee_debates_diarisation/
├── 06_jubilee_debates_speaker_transcripts/
└── 07_jubilee_debates_qc/
```


The main stage programmes are:

| Stage | Programme                                   | Run on EC2 GPU?   |
|------:|---------------------------------------------|-------------------|
|     1 | `transcribe_jubilee_debates_whisperx.py`    | Yes               |
|     2 | `align_jubilee_debates_whisperx.py`         | Yes / recommended |
|     3 | `diarise_jubilee_debates_pyannote.py`       | Yes               |
|     4 | `assign_speakers_jubilee_debates.py`        | Optional          |
|     5 | `qc_jubilee_debates_speaker_diarisation.py` | Optional          |

---

## 14. Run a smoke test

Before processing all five debates, run one item only.

Activate environment:

```shell script
conda activate whisperx_pyannote
cd ~/cl_st1_carol/cl_st1_ph0_carol
```


Check that audio exists:

```shell script
ls -lh corpus/02_jubilee_debates_audio/
```


Run Stage 1 test once the programme is available:

```shell script
python transcribe_jubilee_debates_whisperx.py --test-limit 1
```


Then Stage 2:

```shell script
python align_jubilee_debates_whisperx.py --test-limit 1
```


Then Stage 3:

```shell script
python diarise_jubilee_debates_pyannote.py --test-limit 1
```


Then Stages 4–5:

```shell script
python assign_speakers_jubilee_debates.py --test-limit 1
python qc_jubilee_debates_speaker_diarisation.py --test-limit 1
```


Inspect the outputs manually before running all debates.

---

## 15. Run production processing in `tmux`

Long EC2 runs should use `tmux`.

Start a session:

```shell script
tmux new -s jubilee_speech
```


Activate environment and enter project:

```shell script
conda activate whisperx_pyannote
cd ~/cl_st1_carol/cl_st1_ph0_carol
```


Run the stages sequentially:

```shell script
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


---

## 16. Alternative: run with `nohup`

If you prefer `nohup`, run one stage at a time:

```shell script
nohup python transcribe_jubilee_debates_whisperx.py --no-test-mode \
  > transcribe_jubilee_debates_whisperx.out 2>&1 &
```


Monitor:

```shell script
tail -f transcribe_jubilee_debates_whisperx.out
```


But for this workflow, `tmux` is generally easier.

---

## 17. Monitor GPU and system usage

In another SSH session, run:

```shell script
watch -n 2 nvidia-smi
```


Useful CPU/RAM monitoring:

```shell script
htop
```


Disk usage:

```shell script
df -h
du -sh corpus/*
```


Project tree:

```shell script
tree -L 2 corpus
```


---

## 18. Copy results back to local machine

After processing, copy the generated output directories back.

From your local machine:

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


Or copy all stage outputs at once:

```shell script
rsync -avz \
  -e "ssh -i ~/.ssh/carol-ec2.pem" \
  ubuntu@<EC2_PUBLIC_DNS_OR_IP>:~/cl_st1_carol/cl_st1_ph0_carol/corpus/ \
  /local/path/cl_st1_carol/cl_st1_ph0_carol/corpus/
```


Be careful if local and remote outputs differ; `rsync` can overwrite local files depending on options.

---

## 19. Cost-control checklist

When processing is complete:

1. Confirm outputs have been copied back.
2. Confirm no needed files exist only on EC2.
3. Stop or terminate the instance.

To stop the instance:

```plain text
EC2 Console -> Instances -> Select instance -> Instance state -> Stop instance
```


To avoid ongoing storage costs, delete unused EBS volumes and snapshots if appropriate.

---

## 20. Common problems and fixes

### 20.1 `libcublas.so.12` not found

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


---

### 20.2 CUDA is not available in PyTorch

Check:

```shell script
python -c "import torch; print(torch.cuda.is_available())"
```


If it prints:

```plain text
False
```


Then check:

```shell script
nvidia-smi
```


If `nvidia-smi` works but PyTorch CUDA does not, reinstall PyTorch with CUDA-compatible wheels or use a compatible Deep Learning AMI.

---

### 20.3 pyannote model access denied

Likely causes:

- Hugging Face token missing;
- model terms not accepted;
- token lacks required permissions.

Fix:

```shell script
huggingface-cli login
```


Then accept the required model terms in the Hugging Face web interface.

---

### 20.4 CUDA out of memory

Possible fixes:

- ensure `--workers 1`;
- reduce batch size for transcription/alignment;
- process one debate at a time;
- restart the Python process between stages;
- move from `g5.xlarge` to `g5.2xlarge` or `g5.4xlarge`.

---

### 20.5 Disk full

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

---

## 21. Recommended first-run sequence

For the first complete test, use this conservative sequence:

```shell script
ssh -i ~/.ssh/carol-ec2.pem ubuntu@<EC2_PUBLIC_DNS_OR_IP>
tmux new -s jubilee_speech
conda activate whisperx_pyannote
cd ~/cl_st1_carol/cl_st1_ph0_carol

nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
python -c "import whisperx; print('whisperx OK')"
python -c "import pyannote.audio; print('pyannote OK')"

python transcribe_jubilee_debates_whisperx.py --test-limit 1
python align_jubilee_debates_whisperx.py --test-limit 1
python diarise_jubilee_debates_pyannote.py --test-limit 1
python assign_speakers_jubilee_debates.py --test-limit 1
python qc_jubilee_debates_speaker_diarisation.py --test-limit 1
```


Only after inspecting the first debate outputs should you run:

```shell script
python transcribe_jubilee_debates_whisperx.py --no-test-mode
python align_jubilee_debates_whisperx.py --no-test-mode
python diarise_jubilee_debates_pyannote.py --no-test-mode
python assign_speakers_jubilee_debates.py --no-test-mode
python qc_jubilee_debates_speaker_diarisation.py --no-test-mode
```


---

## 22. Final recommended setup

```plain text
EC2 instance: g5.xlarge initially
AMI: AWS Deep Learning AMI GPU Ubuntu
GPU: NVIDIA A10G, 24 GB VRAM
Storage: 100–200 GB EBS
Python environment: conda, Python 3.11
Environment name: whisperx_pyannote
CUDA libraries: CUDA 12 toolkit in conda env
LD_LIBRARY_PATH: $CONDA_PREFIX/lib
ML packages: torch, torchaudio, faster-whisper, whisperx, pyannote.audio
Authentication: Hugging Face token for pyannote
Execution: tmux
Workers: 1
Run order: transcribe -> align -> diarise -> assign speakers -> QC
```


This setup should be suitable for the current Phase 0 Jubilee debate speaker-diarisation test, with the option to scale up to a larger `g5` instance if memory or runtime becomes problematic.