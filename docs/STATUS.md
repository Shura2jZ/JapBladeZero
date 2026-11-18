# État d'avancement

Dernière mise à jour : 18 novembre 2026.

## Vue d'ensemble

| # | Étape | État | Détail |
|---|-------|-------|--------|
| 1 | Traduction zh → ja | ✅ terminé | 4 252 / 4 252 lignes (modèle local `opus-mt-zh-ja`) |
| 2 | TTS japonais (VOICEVOX) | ✅ terminé | 4 253 WAV dans `out/jp_events/` |
| 3 | Alignement des durées | ✅ terminé | 4 167 lignes avec son chinois, **0 hors tolérance (≤ 5 %)** |
| 4 | Encodage Wwise | ✅ terminé | 4 167 `.wem` dans `out/jp_wem/` |
| 5 | Extraction des packages | ✅ terminé | 4 167 `.uasset` + 3 929 `.ubulk` dans `build/raw_all/` |
| 6 | Injection du média | 🟡 94,2 % | 3 924 événements patchés, **243 échecs** |
| 7 | Écriture `Duration_Japanese` | ❌ 0 % | `data/durations.json` contient encore `[zh, 0]` partout |
| 8 | Packaging IoStore (`~mods`) | ❌ 0 % | projet UE `F:\Games\UnrealProjects\PBZ_JP_Dub` vide |
| 9 | Test en jeu | ❌ | jamais lancé |

## Les 243 échecs d'injection

| Cause | Nombre | Exemple |
|-------|--------|---------|
| `no .ubulk` (le média n'est pas stocké à part) | 238 | `Vo_Plot_DDSD_GM_GM_25` |
| `expected at most 2 media blocks, found 4` | 3–4 | — |
| `no media block` | 1 | — |
| table de bulk-data incohérente (940 038 vs 1 104 265 o) | 1 | — |

Les 238 événements « sans `.ubulk` » ont un `.uasset` de 758 octets : le média doit
être stocké ailleurs (package partagé ou bulk inline). **Cause racine non traitée** →
environ 6 % du jeu garde sa voix chinoise.

## Réserves connues

- **Voix par personnage** : heuristique sur le préfixe de l'événement (`data/voice_map.json`).
  La source fiable — la colonne `Speaker` de `DT_LocTable` (codes `Character_PZ_76`,
  `Character_LJC_26`…, 4 277 lignes) — **n'a pas encore été exploitée** : plusieurs
  personnages partagent donc la même voix.
- **Traduction** : `japanese_text_tts` est propre (0 ligne vide), mais 136 lignes
  conservent des balises `<Bold>` dans la colonne `japanese_text` (colonne source).
- 8 traductions dégradées restent listées dans `data/still_truncated.json`.
- La Table `DT_WwiseVoiceDuration` n'a pas encore de durées japonaises : le lip-sync
  reposera sur la padding de silence tant que l'étape 7 n'est pas faite.

## Prochaines étapes, par priorité

1. **Traiter les 238 événements sans `.ubulk`** — chercher où le média est réellement
   stocké, ou confirmer qu'ils sont sans voix.
2. **Écrire `Duration_Japanese`** dans `DT_WwiseVoiceDuration` (CUE4Parse
   `TrySavePackage` a déjà été validé sur ce package).
3. **Assembler le mod** : injecter les 3 924 packages patchés + la DataTable dans le
   projet UE, cooker en IoStore, produire
   `ProjectPBZ/Content/Paks/~mods/PBZJapaneseVoice_9_P.{pak,ucas,utoc}`.
4. **Tester en jeu** (voix = chinois, sous-titres = japonais ou anglais) et vérifier
   que le conteneur `~mods` est bien prioritaire sur les fichiers du jeu.
5. **Mapping `Character_*` → personnage → voix VOICEVOX**, en priorité 左殇 / 魂
   (ZuoShang), qui porte 207 lignes.
6. **Nettoyage** : balises dans `japanese_text`, 8 lignes dégradées.

## Décisions à trancher

- Voix : garder l'heuristique actuelle pour livrer vite, ou faire le mapping
  `DT_LocTable` avant le packaging ?
- Format : `.pak` simple (plus simple à vérifier) ou conteneur IoStore segmenté
  (cohérent avec le jeu, vérification plus pénille) ?
- Investir sur les 238 échecs maintenant, ou livrer d'abord un mod fonctionnel à 94 % ?

## Journal

- **16/11** — extraction du jeu, traduction, premier passage TTS. (`docs/CHECKPOINT.md`)
- **17/11** — ré-écriture des `.wem` au format exact du jeu, premier patch binaire.
- **18/11** — campagne d'alignement des durées, encodage des 4 167 médias, injection
  de 3 924 packages, nettoyage du dépôt et mise en place du dépôt Git.
