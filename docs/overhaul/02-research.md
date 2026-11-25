# Recherche moteurs TTS — comparaison factuelle (vérifiée à la source, 24/11)

Chaque fait ci-dessous vient du README/LICENCE officiel du projet, récupéré le
24/11, ou d'une mesure locale. Les claims non vérifiables sont signalés.

Contrainte matérielle mesurée : **RTX 3080, 10 Go VRAM (9,4 Go libres), 32 Go
RAM, `E:` 82 Go libres, Python 3.14** (attention : certains dépôts TTS veulent
un Python ≤ 3.12 — à prévoir avec un venv dédié).

## Candidats

### Fish Audio Drama 3 — fishaudio/fish-speech
- Taille : **35B-A3B MoE** (3B actifs/token). fp16 ≈ 70 Go de poids → **ne tient
  pas dans 10 Go** ; même en int4 (~18-20 Go), non. Local : exclu sur cette
  machine. Une API existe (fish.audio) — payante, à chiffrer avant tout usage.
- Atouts mesurés dans le README : multi-locuteurs, émotions non écrasées par la
  référence (« laughter, crying, whispers and dramatic emotion »), édition
  locale d'une réplique, révision multi-tours — exactement nos deux manques.
- **Licence vérifiée** (LICENSE, v1.0 13/10/2026) : libre pour recherche et
  usage non-commercial ; commercial OK sous 500 k$ de revenu annuel ; les
  poids **S2-Pro restent sous Research License** (plus stricte). Un mod
  personnel gratuit entre dans le cadre non-commercial.
- S2-Pro : 4B → fp16 ≈ 8 Go → **tient** sur la 3080, serré. Génération
  précédente, moins expressive que Drama 3 selon leurs propres benchmarks.

### Fun-CosyVoice 3 — QwenAudio/CosyVoice
- Taille : **0.5B** → **tient très largement** (2-4 Go VRAM).
- Japonais natif (9 langues), zero-shot cross-lingual (une référence chinoise
  peut parler japonais — utile : nous avons les voix chinoises du jeu comme
  références de timbre).
- **Instruct natif vérifié** : « languages, dialects, **emotions**, speed,
  volume » — la direction artistique est possible par réplique.
- **Licence vérifiée : Apache 2.0**. Aucune restriction pour nous.
- Windows : officieux (dépôt pensé Linux) ; installation à tenter en venv
  Python ≤ 3.12 sur `E:`.

### GPT-SoVITS — RVC-Boss/GPT-SoVITS
- **Licence vérifiée : MIT**.
- Japonais supporté, cross-lingual, **fine-tuning par voix** avec quelques
  échantillons : le candidat le plus stable pour un timbre fixé par
  personnage ; v2 = coût matériel faible.
- Limite : pas d'instruction d'émotion par réplique comme CosyVoice ; le
  naturel dépend beaucoup de la référence ; fine-tuner 437 personnages est
  irréaliste — envisageable pour les ~40 principaux.
- Installation Windows bien rodée (le dépôt cible Windows en premier).

### Autres (repérés dans le benchmark CosyVoice3, à auditer si besoin)
Index-TTS2 (1.5B, bon WER), VibeVoice-1.5B, Spark-TTS 0.5B, FireRedTTS2. Aucun
n'est documenté avec un contrôle émotionnel par instruction aussi direct que
CosyVoice 3 ; à garder en réserve.

### VOICEVOX (existant)
- Libre, installé, rapide, **mais** : prosodie plate sur la durée, pas
  d'émotion par réplique, 44 voix anime-jeunes pour 437 personnages.

## Pré-évaluation honnête

| critère | VOICEVOX | CosyVoice 3 | GPT-SoVITS | Fish S2-Pro (local) | Drama 3 |
|---|---|---|---|---|---|
| naturel japonais | faible-moyen | bon (attendu) | bon si fine-tuné | bon | très bon |
| émotion par réplique | non | **oui (instruct)** | non (via référence) | partiel | **oui (langage naturel)** |
| timbre par personnage | 44 fixés | clonage zero-shot | fine-tune | clonage | clonage |
| VRAM | CPU | ~2-4 Go | ~4-6 Go | ~8 Go serré | **>10 Go : non** |
| licence | libriste | Apache 2.0 | MIT | research/non-comm | non-comm OK (mod) |
| risque d'intégration | nul | moyen (Windows) | moyen-faible | moyen | élevé (API payante) |

## Décision d'expérimentation (benchmark §11 du brief)

Ordre de test, justifié :
1. **VOICEVOX optimisé** (base A, gratuite, déjà là) — prosodie améliorée via
   ponctuation/pauses/`pitchScale`/`intonationScale`/par-prise.
2. **CosyVoice 3 zero-shot** (base B) — référence = extrait propre du média
   chinois du personnage ; instructions d'émotion par réplique. Candidat
   principal pour la généralisation à 437 personnages.
3. **GPT-SoVITS fine-tuné** (base C) — sur 10-15 personnages principaux
   seulement, pour comparer un timbre très fidèle.
4. Fish S2-Pro local si la VRAM le permet, Drama 3 via API seulement si le
   benchmark 2/3 échoue et après chiffrage du coût (~4 000 répliques).

Le choix final se fait sur les 30-50 répliques du benchmark, à l'oreille, pas
sur les benchmarks des éditeurs.
