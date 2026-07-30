#!/usr/bin/env bash

# Corpus Linguistics — Study 1 — Carol
# Phase 0: Speaker Diarisation Test
#
# This script runs the Phase 0 Jubilee debate preparation pipeline.
#
# Pipeline stages:
#   1. Download Jubilee debate videos and metadata.
#   2. Extract full-length audio files from the downloaded videos.
#
# The script is intended to be run from:
#
#   cl_st1_ph0_carol/
#
# Example:
#
#   bash cl_st1_ph0_carol.sh
#
# Notes:
#   - The Python programmes resolve their own default paths relative to their
#     script directory.
#   - Existing outputs are skipped by default by the Python programmes.
#   - The download stage is run in full mode with --no-test-mode.
#   - The audio extraction stage currently uses its default settings:
#       profile: gemini_flac
#       test mode: enabled
#       test limit: 5
#
# If you want the audio extraction stage to process all eligible debates, change:
#
#   python extract_jubilee_debates_audio.py
#
# to:
#
#   python extract_jubilee_debates_audio.py --no-test-mode

set -euo pipefail

# Resolve this shell script's directory and run the pipeline from there.
# This makes the script safer if it is launched from the project root or another
# working directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "=== Corpus Linguistics — Study 1 — Carol: Phase 0 pipeline ==="
echo "Working directory: ${SCRIPT_DIR}"
echo

echo "=== Stage 1/2: Download Jubilee debate videos and metadata ==="
python download_jubilee_debates.py --no-test-mode
echo "=== Stage 1/2 complete ==="
echo

echo "=== Stage 2/2: Extract full-length Jubilee debate audio ==="
python extract_jubilee_debates_audio.py --no-test-mode
echo "=== Stage 2/2 complete ==="
echo

echo "=== Phase 0 pipeline complete ==="