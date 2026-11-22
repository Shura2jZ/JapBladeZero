#!/usr/bin/env bash
# Refait le mod complet, de la voix dubbee au conteneur installe.
#
#   bash scripts/all.sh ["Where to build the container"]
#
# Etapes :
#   1. demarrage des moteurs VOICEVOX (4,=configurable)
#   2. synthese des voix japonaises, a vitesse naturelle, puis alignement
#   3. encodage des .wem, injection, bibliotheque VO_CN, table des durees
#   4. construction du conteneur IoStore et installation dans le jeu
#
# Les moteurs sont arretes a la fin, qu'il y ait une erreur ou non.
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE"

OUT="${1:-E:/PBZ_Mod}"
MOTORS="${MOTORS:-4}"

cleanup() {
    bash scripts/voicevox.sh stop
}
trap cleanup EXIT

export VOICEVOX_PORTS="${VOICEVOX_PORTS:-50021-50024}"
export VOICEVOX_WORKERS="${VOICEVOX_WORKERS:-$MOTORS}"

echo "=== 1. moteurs VOICEVOX ($MOTORS) ==="
bash scripts/voicevox.sh start "$MOTORS"

echo "=== 2. voix japonaises et alignement ==="
bash scripts/tts.sh || { echo "echec de la synthese"; exit 1; }

echo "=== 3 et 4. encodage, injection et conteneur ==="
bash scripts/build.sh "$OUT"

echo
echo "mod installe dans le jeu."
