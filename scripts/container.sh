#!/usr/bin/env bash
# Builds the IoStore container of the mod and installs it in the game.
#
#   bash scripts/container.sh [out dir]
#
# Requires:
#   - the patched packages in build/patched_all and build/patched_lib
#   - the patched retoc (tools/retoc/0001-...patch), built with:
#       git clone https://github.com/trumank/retoc.git && cd retoc
#       git apply ../tools/retoc/0001-pack-raw-write-the-container-header.patch
#       export CARGO_TARGET_DIR=E:/cargo_target
#       export PATH="$PATH:/e/msys64/usr/bin:/e/msys64/ucrt64/bin"
#       cargo build --release -p retoc_cli
#   - UnrealPak.exe (moteur UE) pour le .pak vide

set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$BASE/scripts/common.sh"

OUT="${1:-E:/PBZ_Mod}"
RETOC="${RETOC:-E:/cargo_target/release/retoc.exe}"
UNREALPAK="${UNREALPAK:-F:/Epic/UE_5.7/Engine/Binaries/Win64/UnrealPak.exe}"
PAKS="${PAKS:-E:/SteamLibrary/steamapps/common/PBZ/ProjectPBZ/Content/Paks}"
NAME="PBZJapaneseVoice_9_P"

cd "$BASE"

python src/patch/container_files.py
python src/patch/build_container.py --files data/container_files.tsv --out "$OUT" --name "$NAME"

# le moteur monte le conteneur qui porte le nom du .pak : il faut un .pak (vide suffit)
: > "$BASE/build/empty_list.txt"
"$UNREALPAK" "$OUT/$NAME.pak" "-Create=$BASE/build/empty_list.txt" -MountPoint="../../../"

echo "installation dans $PAKS"
cp "$OUT/$NAME.pak" "$OUT/$NAME.ucas" "$OUT/$NAME.utoc" "$PAKS/"
ls -la "$PAKS/$NAME".*
