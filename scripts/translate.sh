#!/usr/bin/env bash
# Traduction zh -> ja (modèle local MarianMT) puis normalisation du texte.
#   1. translate_batches.py : traduit les chaînes chinoises unique -> data/batches/out_mt.json
#   2. merge_jp.py          : fusionne la traduction dans data/manifest_jp.csv
#   3. clean_text.py        : nettoie balises et ponctuation -> colonne japanese_text_tts
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

python src/translate/translate_batches.py > logs/translate.log 2>&1
python src/translate/merge_jp.py     >> logs/translate.log 2>&1
python src/translate/clean_text.py   >> logs/translate.log 2>&1
tail -n 20 logs/translate.log
