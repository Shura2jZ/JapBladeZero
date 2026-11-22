#!/usr/bin/env bash
# Construit le mod complet a partir des WAV japonais deja generes.
#
#   bash scripts/build.sh
#
# Etapes :
#   1. encodage des .wem          (WAV 24 kHz -> Ogg Vorbis Wwise)
#   2. durees des medias        (ce que le moteur joue -> table des durees)
#   3. verification des .wem    (la duree decodee doit etre la meme)
#   4. injection dans les paquets (uasset + ubulk)
#   5. injection dans la bibliotheque Wwise VO_CN
#   6. reecriture de DT_WwiseVoiceDuration (en place, taille constante)
#   7. construction du conteneur IoStore et installation dans le jeu
#
# Les etapes 1 a 3 dependent des WAV (out/jp_events), produites par
# scripts/tts.sh. Les etapes 4 a 6 partent des .wem.
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$BASE/scripts/common.sh"

cd "$BASE"

echo "=== 1. encodage des .wem ==="
python src/audio/wem_batch.py --workers 6 --quality 9 | tee logs/wem.log

echo "=== 2. durees des medias ==="
python src/audio/wav_durations.py | tee logs/wav_durations.log

echo "=== 3. verification des .wem ==="
python src/audio/wem_durations.py | tee logs/wem_durations.log

echo "=== 4. injection ==="
python src/patch/inject_all.py | tee logs/inject.log

# Les medias qui ne sont pas dans leur propre paquet vivent dans la
# bibliotheque Wwise VO_CN : ils doivent etre remplaces la aussi, sinon
# 243 evenements jouent encore en chinois.
echo "=== 5. bibliotheque VO_CN ==="
python src/patch/library_patch.py | tee logs/library.log
python src/patch/verify_library.py 2>&1 | tee logs/library_verify.log | head -3

echo "=== 6. durees dans DT_WwiseVoiceDuration ==="
python src/patch/patch_dt_durations.py | tee logs/dt_durations.log

echo "=== 7. conteneur et installation ==="
bash scripts/container.sh "${1:-E:/PBZ_Mod}"

echo
echo "mod construit."
