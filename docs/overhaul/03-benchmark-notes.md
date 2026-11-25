# Notes expérimentales — benchmark moteurs (24/11)

Tout est sur la branche `overhaul/voice-casting`. Le jeu installé n'a pas été
touché ; les expériences écrivent dans `out/benchmark/`.

## Setup

- **CosyVoice 3 (0.5B, Apache 2.0)** installé sur `E:/TTS_Lab` : venv Python
  3.12 (uv), torch 2.3.1+cu121, dépendances corrigées (grpcio non épinglé,
  pyworld non épinglé, Matcha-TTS en third_party), modèle
  `Fun-CosyVoice3-0.5B-2512` (9,1 Go). GPU OK, rtf ≈ 0,85 (temps réel ~1×).
- **Références de voix** : 40 extraits chinois du jeu décodés
  (`out/benchmark/refs/<event>.cn.wav`), puis version **multi-lignes** par
  personnage (~18 s concaténées, `*.cn.multi.wav`) — une ref de 1,8 s déstabilise
  le clonage.
- **Prise A (VOICEVOX)** : 40/40 générées avec directions par bucket
  (`src/tts/benchmark_generate.py`).
- **Prise B (CosyVoice 3)** : 40/40 générées en `instruct2` (instruction de jeu
  par bucket + voix chinoise du personnage) (`src/tts/benchmark_cosyvoice.py`).

## Mesures (40 lignes, ratio durée JP / durée chinoise)

| | médiane | p5 | p95 |
|---|---|---|---|
| VOICEVOX | 0,41* | 0,19 | 1,56 |
| CosyVoice 3 | 1,39 | 0,69 | 4,31 |

\* les ratios VOICEVOX/CosyVoice ne sont pas comparables ligne à ligne car les
durées chinoises de `durations.json` sont parfois incohérentes avec la ligne
(vérifié : ref décodée = json, mais certaines lignes « courtes » de 20
caractères durent 1,8 s en chinois — cri très bref). Les deux extrêmes
cosyvoice (5×, 4,3×) sont des lignes courtes : la synthèse part en
longueur (hallucination/pause finale) — la boucle QC la détectera.

## Conclusions d'écoute en attente

Les chiffres ne remplacent pas l'oreille : `out/benchmark/voicevox/` et
`out/benchmark/cosyvoice3/` contiennent les mêmes 40 lignes, prêtes pour
l'A/B à l'aveugle (à faire avec l'utilisateur).

## Ce qui marche / coince dans CosyVoice 3

✅ clonage de timbre depuis la voix chinoise du jeu (multi-lignes),
✅ instruction de performance en langage naturel (`inference_instruct2`),
✅ VRAM ~4 Go, temps réel, Apache 2.0,
⚠️ débit ~1,4-1,5× le chinois en médiane ; le paramètre `speed` natif ne
   s'applique pas de façon fiable (28,4→20,9 s à 1,35 sur une ligne, inchangé
   sur une autre) ;
⚠️ lignes très courtes : longueur prédite erratique (7 caractères → 7,6 s) ;
⚠️ `zero_shot` sans transcription du prompt → crash (passer par `instruct2`).

## Choix d'architecture qui en découle

La boucle de génération par ligne est **obligatoire** : générer → mesurer
(durée, silence final, clip) → corriger (`speed`, trims) → regénérer au besoin
→ sélectionner la prise. C'est exactement la §9 du brief ; `tts_align` reste
en dernier recours (padding ≤ 30 %, compression ≤ 15 %).

## Reste à faire (dans l'ordre)

1. A/B à l'aveugle utilisateur (VOICEVOX vs CosyVoice3, 40 lignes).
2. Boucle QC par ligne (génération multi-prises + corrections).
3. GPT-SoVITS sur les ~15 personnages principaux (fine-tune, Windows natif).
4. S2-Pro local (4B) si le benchmark CosyVoice convainc pas ; Drama 3 : API
   seulement (35B-A3B > 10 Go VRAM), coût à chiffrer avant.
5. Casting multi-critères (âge, texture, tempérament) sur le catalogue final.
