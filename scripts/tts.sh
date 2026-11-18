#!/usr/bin/env bash
# Synthèse vocale japonaise (VOICEVOX) + alignement sur la durée chinoise.
#   1. tts_generate.py : génère les WAV manquants (24 kHz mono) dans out/jp_events
#   2. tts_refine.py   : réajuste le speedScale de chaque ligne pour coller à la durée chinoise
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

python src/tts/tts_generate.py | tee logs/tts.log
python src/tts/tts_refine.py   | tee logs/tts_refine.log
python src/tts/tts_align.py    | tee logs/tts_align.log
