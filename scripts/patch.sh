#!/usr/bin/env bash
# Injection : remplace le média chinois par le .wem japonais dans le .ubulk de chaque
# AkAudioEvent, puis réécrit la table de bulk-data du .uasset.
# Entrée : build/raw_all (packages extraits par CUE4Parse), out/jp_wem (médias japonais)
# Sortie : build/patched_all (uasset + ubulk patchés)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

python src/patch/inject_all.py | tee logs/inject.log
