#!/usr/bin/env bash
# Conversion des WAV japonais en médias Wwise (.wem) prêts à être injectés.
#   WAV 24 kHz -> ffmpeg 48 kHz mono -> encode.exe (Ogg Vorbis) -> wem.py (RIFF 0xFFFF)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

python src/audio/wem_batch.py --workers 6 --quality 9 | tee logs/wem.log
