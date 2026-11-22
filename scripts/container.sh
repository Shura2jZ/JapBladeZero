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
# retoc doit etre le binaire patche (il ecrit l'en-tete de conteneur) : la
# variable est exportee pour que build_container.py n'utilise pas son propre
# defaut, qui est le retoc stock, sans le correctif.
export RETOC="${RETOC:-E:/cargo_target/release/retoc.exe}"
UNREALPAK="${UNREALPAK:-F:/Epic/UE_5.7/Engine/Binaries/Win64/UnrealPak.exe}"
PAKS="${PAKS:-E:/SteamLibrary/steamapps/common/PBZ/ProjectPBZ/Content/Paks}"
WORK="${WORK:-E:/PBZ_Build/container}"
# Le nom du pak determine l'ordre de montage du conteneur (cf. la garde-fou
# plus bas). Le nom du projet du jeu est "ProjectPBZ" : le pak du jeu,
# "ProjectPBZ-Windows.pak", obtient l'ordre 4 (prefixe "Paks/ProjectPBZ-"),
# alors qu'un pak nomme autrement obtient l'ordre 3. Les conteneurs sont tries
# par ordre decroissant et le premier qui contient le chunk gagne
# (FileIoDispatcherBackend.cpp) : avec l'ordre 3, le conteneur du jeu passe
# devant et le jeu joue le contenu d'origine.
#
# Le nom doit donc commencer par "ProjectPBZ-" (meme ordre que le jeu) et
# etre plus petit que "ProjectPBZ-Windows.pak" : les paks sont montes dans
# l'ordre décroissant du nom, donc le plus petit est monte en dernier. Il a
# alors l'instance id la plus elevee et l'emporte a ordre egal.
NAME="ProjectPBZ-JapaneseVoice"

cd "$BASE"

python src/patch/container_files.py

# Contrôle avant construction : les chunk ids doivent etre ceux que le moteur
# resout. Un id de package ecrit dans le mauvais ordre des octets ne
# correspond a aucun chunk du jeu : le conteneur est monte mais le jeu joue
# alors le contenu d'origine (cf. docs/PIPELINE.md, section 7).
IDPROBE="${IDPROBE:-$BASE/tools/csharp/idprobe/bin/Release/net10.0/idprobe.dll}"
GAME_UTOC="${GAME_UTOC:-$PAKS/ProjectPBZ-Windows.utoc}"
if [ -f "$IDPROBE" ] && [ -f "$GAME_UTOC" ]; then
    dotnet "$IDPROBE" "$GAME_UTOC" data/container_files.tsv
else
    echo "avertissement : controle des chunk ids indisponible (idprobe ou TOC du jeu absent)"
fi

# Les chunks sont nommes par leur chunk id : deux fichiers ne peuvent pas
# partager le meme id, sinon l'un ecrase l'autre dans le conteneur et le
# contenu du mod est incomplet (sans erreur visible au montage).
python - "$BASE" <<'PY'
import os, sys, collections
base = sys.argv[1]
rows = [l.rstrip('\n').split('\t') for l in
        open(os.path.join(base, 'data', 'container_files.tsv'), encoding='utf-8') if l.strip()]
ids = collections.Counter(os.path.basename(local) for _, local in rows)
dupes = {k: v for k, v in ids.items() if v > 1}
if dupes:
    sys.exit('ERREUR : %d noms de chunk utilises plusieurs fois, le conteneur serait incomplet : %s'
             % (len(dupes), list(dupes.items())[:10]))
print('%d chunks, aucun nom duplique' % len(rows))
PY

# Garde-fou : l'ordre de montage du conteneur. Comparaison faite comme le
# moteur (FPakPlatformFile::GetPakOrderFromPakFilePath et le tri decroissant
# des noms de paks). Si le mod n'obtient pas le meme ordre que le jeu, ou s'il
# est monte avant lui, le conteneur du jeu gagne et le jeu joue l'original.
python - "$NAME" "$PAKS" <<'PY'
import os, sys
name, paks = sys.argv[1], sys.argv[2]
project = 'ProjectPBZ'


def pak_order(base_name):
    # GetPakOrderFromPakFilePath : ProjectContentDir + 'Paks/' + ProjectName + '-'
    # vaut 4, ProjectContentDir seul vaut 3.
    if ('Paks/%s-' % project).startswith('Paks/') and base_name.startswith(project + '-'):
        return 4
    return 3


# le pak du jeu : celui qui porte le conteneur IoStore du jeu
game = None
if os.path.isdir(paks):
    for f in sorted(os.listdir(paks)):
        if f.startswith(project + '-') and f.endswith('.pak') and \
                os.path.exists(os.path.join(paks, f[:-4] + '.utoc')):
            game = f[:-4]
if game is None:
    game = project + '-Windows'

mod_order, game_order = pak_order(name), pak_order(game)
if mod_order != game_order:
    sys.exit("ERREUR : le pak du mod (%s) est monte dans l'ordre %d, celui du jeu (%s) "
             "dans l'ordre %d : le conteneur du jeu sera lu en premier et le jeu jouera "
             "le contenu d'origine. Le nom du mod doit commencer par '%s-'."
             % (name, mod_order, game, game_order, project))
# les paks sont montes dans l'ordre decroissant du nom : le plus petit est
# monte en dernier, et c'est lui qui gagne a ordre egal.
if name > game:
    sys.exit("ERREUR : le pak du mod (%s) est plus grand que celui du jeu (%s) : il sera "
             "monte avant lui et perdra. Le nom doit etre plus petit." % (name, game))
print("ordre de montage : mod=%d (nom %s), jeu=%d (nom %s) -> le mod est monte en "
      "dernier, il est prioritaire" % (mod_order, name, game_order, game))
PY

python src/patch/build_container.py --files data/container_files.tsv --out "$OUT" --name "$NAME" --work "$WORK"

# Controle d'integrite : le .ucas doit contenir toutes les donnees que le .utoc
# decrit, et son en-tete (type 6) doit etre lisible — c'est lui qui donne au
# moteur la liste des paquets. Un conteneur tronque est monte sans erreur mais
# ne resout aucun paquet, et le jeu joue alors le contenu original.
python src/patch/check_container.py "$OUT" "$NAME"
# espace libre : le conteneur (1,5 Go) doit etre ecrit puis recopie dans le jeu
free_mb=$(df -Pm "$OUT" | tail -1 | awk '{print $4}')
if [ "$free_mb" -lt 4096 ]; then
    echo "avertissement : seulement ${free_mb} Mo libres sur le disque du conteneur"
fi

# le moteur monte le conteneur qui porte le nom du .pak : il faut un .pak (vide suffit)
: > "$BASE/build/empty_list.txt"
rm -f "$OUT/$NAME.pak"
"$UNREALPAK" "$OUT/$NAME.pak" "-Create=$BASE/build/empty_list.txt" -MountPoint="../../../"

echo "installation dans $PAKS"
cp "$OUT/$NAME.pak" "$OUT/$NAME.ucas" "$OUT/$NAME.utoc" "$PAKS/"
ls -la "$PAKS/$NAME".*
