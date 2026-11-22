#!/bin/bash
# Suit la regeneration des voix et lance la construction quand elle est finie.
#
#   bash scripts/wait_tts.sh
#
# Les etapes : TTS (generation), alignement, encodage, injection, conteneur.
# Le build ne peut pas demarrer sans espace sur le disque de travail.
BASE="C:/Users/marou/.deepai-code/scratch/2026-11-16-wsh-claude-fable-cd7797cc"
cd "$BASE"
while true; do
  if [ -f logs/tts_chain.done ]; then break; fi
  sleep 60
done
cat logs/tts_chain.done
if grep -q "ALIGN OK" logs/tts_align.log; then
  echo "TTS fini, lancement du build"
  bash scripts/build.sh E:/PBZ_Mod > logs/build3.log 2>&1 && echo "BUILD OK" || echo "BUILD KO"
else
  echo "TTS incomplet, build non lance"
fi
