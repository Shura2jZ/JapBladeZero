#!/usr/bin/env bash
# Synthèse vocale japonaise (VOICEVOX) + alignement sur la durée chinoise.
#
#   bash scripts/tts.sh
#
# 1. tts_generate.py : génère les WAV (24 kHz mono) dans out/jp_events.
#    La voix est synthétisée à sa vitesse naturelle : la ligne japonaise est
#    une traduction, elle n'a pas la longueur de la ligne chinoise, et forcer
#    la vitesse rendrait la voix artificielle.
# 2. tts_refine.py   : si la ligne dépasse son créneau, elle est comprimée
#    (au plus 15 %) ; si elle est plus courte, le reste est comblé par un
#    silence numérique. La table des durées portera la longueur réelle.
# 3. tts_align.py    : dernière passe, uniquement du silence de remplissage.
#
# Les moteurs VOICEVOX doivent tourner. Chacun charge son modele et pese sur le
# CPU : 4 suffisent, et les scripts n'en utilisent que ceux-la.
#   bash scripts/voicevox.sh start 4
export VOICEVOX_PORTS="${VOICEVOX_PORTS:-50021-50024}"
export VOICEVOX_WORKERS="${VOICEVOX_WORKERS:-4}"

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

cd "$BASE"

# Les WAV qui précèdent la dernière affectation des voix ont été produits avec
# une autre voix : ils sont refaits. --force refait tous les others.
find out/jp_events -name '*.wav' ! -newer data/character_voices.json -delete 2>/dev/null || true

python -u src/tts/tts_generate.py --force | tee logs/tts.log
python -u src/tts/tts_refine.py             | tee logs/tts_refine.log
python -u src/tts/tts_align.py              | tee logs/tts_align.log
