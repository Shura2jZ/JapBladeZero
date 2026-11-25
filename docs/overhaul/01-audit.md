# Audit du pipeline de doublage — état réel au 24/11

Audit fait sur le code et les données, pas sur STATUS.md (dont les sections
historiques sont obsolètes). Branche : `overhaul/voice-casting`.

## 1. Ce qui tourne aujourd'hui

| maillon | implémentation | état |
|---|---|---|
| moteur TTS | VOICEVOX 0.26.2 local, CPU, 4 serveurs `run.exe` | opérationnel |
| identité du locuteur | `DT_LocTable.Speaker` → `data/event_speaker.json` (4172 lignes couvertes) → repli par préfixe `voice_map.json` → défaut | **déjà fiable** |
| voix par personnage | `data/character_voices.json` : 437 personnages, affectation mesurée sur le F0 de la voix chinoise d'origine (`cn_voice_profiles.json`) | opérationnel mais **F0 seul** |
| catalogue de voix | 44 voix distinctes / 128 styles (84 F, 40 M, styles neutres seuls utilisés) | **trop petit** |
| préparation du texte | `japanese_text_tts` (traduction éditable), passée brute à `audio_query` | aucune normalisation, aucun tag |
| émotion / prosodie | **aucune** : `audio_query` par défaut, `speedScale` intact (naturel), pas d'intonation, pas de pauses dirigées | cause n°2 |
| prises | 1 seule génération par ligne, acceptée si WAV valide | pas de QC |
| contrôle qualité | durées + intégrité seulement (refine/align, dtcheck) | pas de contrôle du rendu |
| alignement | compress ≤ 15 %, sinon silence de fin, durées réelles écrites dans la DataTable | sain, à préserver |
| injection | Wwise (paquets + banque `VO_CN` + DataTable durées) → conteneur IoStore `ProjectPBZ-JapaneseVoice` | sain, ne pas toucher |

## 2. Cause des deux problèmes

### P1 — les voix ne correspondent pas aux personnages

1. **Le F0 ne caractérise pas une voix.** L'affectation choisit la voix dont le
   F0 médian est le plus proche, pénalité de réutilisation plafonnée. Genre
   déduit du F0 et des pronoms (fragile sur les répliques courtes). Aucune
   notion d'âge, de texture, de grain, de débit, de tempérament.
2. **Catalogue trop pauvre.** 44 voix anime-voice pour 437 personnages (~10
   personnages/voix), majoritairement des voix jeunes et claires. Un vieil
   homme rugueux n'a quasiment pas de candidat : le meilleur F0 sera de toute
   façon jeune. Vérifié : `Character_EX_2` (grave, 101 Hz) assorti à une voix
   à 20 % d'écart, meilleure option disponible.
3. **Les personnages secondaires sont tous affectés.** Il n'y a pas de cas
   « identité incertaine » : tout le monde reçoit une voix, même quand la
   base (Speaker) est déduite du seul nom d'événement.

### P2 — rendu artificiel

1. **Prosodie VOICEVOX** : moteur conçu pour la lecture/doublage anime, plat
   sur des milliers de répliques ; l'oreille identifie la synthèse.
2. **Aucune direction** : pas d'émotion, pas d'instruction par scène, pas de
   variation de débit/intensité. Toutes les répliques d'un personnage sont
   uniformes.
3. **Une seule prise, acceptée d'office** : pas de comparaison, pas de
   détection de prononciation foireuse, de clip, de silence anormal.
4. **Texte brut** : la ponctuation est le seul signal prosodique.

## 3. Ce qui est réutilisable tel quel

- la chaîne identité (Speaker → personnage) ;
- les profils chinois mesurés (`cn_voice_profiles.json`, à enrichir : F0 min/max,
  variation, spectre, débit — les médias sont déjà extraits) ;
- refine/align + durées réelles + DataTable + injection + conteneur ;
- les WAV actuels (conservés, jamais écrasés : les nouvelles générations vont
  dans un dossier distinct).

## 4. Ce qui doit changer (architecture cible)

```
src/tts/
    engines/        voicevox.py (existant, adapté) + fish_audio.py, cosyvoice.py, gpt_sovits.py
    casting/        character_profiles.py (profils riches), voice_assign.py (multi-critères),
                    voice_reference.py (analyse des médias chinois)
    direction/      emotion_analyzer.py, dialogue_context.py, performance_tags.py
    generation/     generate.py (multi-prises), retry.py, cache
    quality/        audio_quality.py (clip, silence, artefacts), pronunciation.py,
                    take_selection.py
    alignment/      tts_align.py (inchangé)
```

Contrainte matérielle mesurée : RTX 3080 **10 Go VRAM** (~9,4 Go libres),
32 Go RAM, `E:` 82 Go libres. Tout modèle > 10 Go VRAM en fp16 est exclu en
local ; inference quantisée ou API à étudier.

## 5. Plan

1. Recherche moteurs (02-research.md) — licences et VRAM vérifiées à la source.
2. Prototype comparatif sur 30-50 répliques représentatives (03-benchmark).
3. Casting multi-critères + direction émotionnelle.
4. A/B à l'aveugle → intégration seulement après validation.
