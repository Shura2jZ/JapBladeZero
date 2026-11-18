# PBZ Japanese AI Dub — Checkpoint

Date : 2026-11-16 (nuit)
Jeu : Phantom Blade Zero — E:\SteamLibrary\steamapps\common\PBZ (Steam build 26367565, UE 5.7.4)
Dossier de travail : `C:\Users\marou\.deepai-code\scratch\2026-11-16-wsh-claude-fable-cd7797cc`

---

## 1. Où en est chaque étape

| # | Étape | État |
|---|-------|-------|
| 1 | Traduction zh → ja | **TERMINÉ** — 4 252 / 4 252 lignes |
| 2 | TTS japonais VOICEVOX | **EN COURS** — ~2 125 / 4 252 WAV au checkpoint, 12 erreurs (reprise auto possible) |
| 3 | Normalisation des durées | **PARTIEL** — durées chinoises extraites ; durée JP par événement pas encore écrite dans la table |
| 4 | Reconstruction VO_CN / VO_CN_Seq | **ANALYSÉ** — architecture comprise, pas encore codé |
| 5 | Cook IoStore + pak `~mods` | **NON COMMENCÉ** |
| 6 | Test en jeu | **NON COMMENCÉ** |

---

## 2. Fichiers importants

Tous dans le dossier de travail sauf mention contraire.

| Fichier | Contenu |
|---------|---------|
| `manifest_jp.csv` | Table principale. Colonnes : `event_name, dialogue_key, chinese_text, duration_zh, wem_file, status, japanese_text, japanese_text_tts` |
| `batches/out_mt.json` | 4 217 chaînes chinoises uniques → japonaises (sortie brute du modèle MT) |
| `durations.json` | Durées par `EventName` : `[Duration_Chinese, Duration_Japanese]` |
| `durations_raw.csv` | Dump brut de la DataTable de durées (7 972 lignes) |
| `loc_raw.csv` | Dump brut de `DT_LocTable` (11 140 lignes) |
| `voice_map.json` | Mapping préfixe d'événement → speaker ID VOICEVOX |
| `out/jp_events/*.wav` | WAV japonais générés (24 kHz mono) |
| `samples/` | 16 échantillons + `echantillons.csv` (chinois, japonais, voix, durée) |
| `models/opus-mt-zh-ja/` | Modèle de traduction local (MarianMT zh→ja, 310 Mo) |
| `tts_generate.py` | Génération TTS (reprend les WAV manquants, relance les moteurs morts) |
| `clean_text.py` | Nettoyage balises + ponctuation, produit `japanese_text_tts` |
| `translate_batches.py` | Traduction MT par lots |
| `merge_jp.py` | Fusionne la sortie MT dans `manifest_jp.csv` |
| `probe/` | Programme C# CUE4Parse d'inspection du jeu |
| `refl/` | Programme C# de réflexion sur l'API CUE4Parse |

Outils utilisés :
- Modèle MT : `shun89/opus-mt-zh-ja` (fork accessible de Helsinki-NLP/opus-mt-zh-ja ; le repo d'origine renvoie 401)
- VOICEVOX Engine 0.26.2 CPU : `C:\Users\marou\AppData\Local\Temp\voicevox_x\windows-cpu` — lancé sur les ports 50021-50024
- CUE4Parse 1.2.2.202611 + oo2core + usmap (clé AES fournie)

---

## 3. Résultats techniques à ne pas refaire

### Traduction
- Le modèle MT local suffit pour une base jouable. Qualité correcte sur les répliques simples ; décomposition littérale sur les phrases nominales chinoises.
- Nettoyage appliqué : balises `<Bold>`, `</>`, ponctuation chinoise (`，。` → `、。`), caractères chinois résiduels non prononçables.
- **Réserve connue** : `japanese_text` (colonne source) conserve parfois les balises ; `japanese_text_tts` (colule lue par le TTS) est propre. Un passage de nettoyage sur `japanese_text` reste à faire.
- Cas limites : certaines répliques MT se vident ou se dégradent (ex. `Vo_Plot_Study_Conversation2_ZhongShu_3` → « . »). Détection : rapport durée JP / durée CN aberrant.

### Stockage audio — point cléettled
- Chaque événement Wwise est un `AkAudioEvent`.uasset **avec son propre .ubulk** : `ProjectPBZ/Content/Wwise/Events/VO/Plot/<...>/<event>.uasset` + `.ubulk`.
- Le média chinois est dans le .ubulk de l'événement lui-même. **Pas** dans VO_CN / VO_CN_Seq.
- `VO_CN.uasset` (274 847 o) et `VO_CN_Seq.uasset` (107 550 o) sont des `UWwiseAssetLibrary` ; ils ne contiennent que des chunks numérotés (2 581 + 820 .wem) et ne sont pas la cible du remplacement vocal.
- Chaque événement expose 2 variantes : `(Chinese)` et `(English(US))`. Remplacer la variante chinoise suffit.
- Format des médias : RIFF/WAVE, `wFormatTag=0xFFFF` (Vorbis Wwise), 48 kHz. Les fichiers extraits par CUE4Parse sont déjà décodés en PCM par l'outil, mais le .ubulk contient les données encodées.

### CUE4Parse — écriture
- `provider.TrySavePackage(path, out dict)` **fonctionne** sur les packages cuits. Vérifié sur `DT_WwiseVoiceDuration` (574 841 octets re-sérialisés, rechargé avec succès).
- C'est la brique qui rend le mod réalisable sans toucher aux fichiers d'origine.
- `provider.Files[]` donne la taille ; `GameFile` n'expose ni `GetStream()` ni `CreateReadStream()` sur cette version — passer par `TrySavePackage` pour récupérer les octets.

### Voix par personnage
- Mapping actuel : heuristique sur le préfixe de l'événement (`PZ`, `LJC`, `FJZL`, `XG`, `XiMeng`, `ZDDY`, `XSSL`, `DDSD`, `JHSY`, …) → speaker VOICEVOX.
- **Source fiable non encore exploitée** : `DT_LocTable` a une colonne `Speaker` avec des codes techniques (`Character_Main_1`, `Character_Imp_10`, `Character_PZ_76`, `Character_DDSD_2`, `Character_FJZL_17`, `Character_LJC_26`…). 4 277 lignes ont `Audio` + `Speaker`. Il faut établir la correspondance code → nom de personnage (probablement via un autre asset ou les BP de dialogue).
- Personnage principal : **左殇 / 魂 (ZuoShang, "Soul")** —207 lignes dont le nom apparaît dans l'ID d'événement (`ZuoShang`, `ZuoSahng` avec faute d'orthographe dans le jeu).

### Durées
- `DT_WwiseVoiceDuration` : 7 972 lignes, colonnes `Duration_Chinese`, `Duration_English`, `Duration_German`, `Duration_Japanese`.
- 4 632 lignes ont une durée chinoise non nulle ; `Duration_Japanese` est à 0 partout (jeu sans voix japonaise).
- 4 167 des 4 252 événements du manifest ont une durée chinoise → cible de synchronisation.
- Total voix chinoise : ~25 085 s ≈ 7 h.
- Attention : la première version du script lisait les floats comme des chaînes et obtenait 0. Il faut lire le tag avec `UnderlyingType` = `typeof(float)`.

---

## 4. À faire demain

1. **Relancer le TTS** si besoin :
   ```bash
   cd "C:/Users/marou/.deepai-code/scratch/2026-11-16-wsh-claude-fable-cd7797cc"
   bash run_tts.sh          # reprend les WAV manquants, relance les moteurs VOICEVOX morts
   ```
   Vérifier `tts.log` (format : `N processed, errors=X, remaining=Y`).
   Si les moteurs ne répondent plus, les relancer :
   ```bash
   cd "C:/Users/marou/AppData/Local/Temp/voicevox_x/windows-cpu"
   for p in 50021 50022 50023 50024; do (nohup ./run.exe --host 127.0.0.1 --port $p --no-use_gpu --output_log_utf8 --init_processes 1 > vv$p.log 2>&1 &); done
   ```

2. **Rétablir le mapping des locuteurs** : exploitier la colonne `Speaker` de `DT_LocTable` (codes `Character_*`) pour identifier les personnages réels et fixer une voix VOICEVOX par personnage, le héros 左殇/魂 en priorité.
   Pour l'instant la correspondance `event → Speaker` n'a pas été écrite sur disque : elle se recalcule à la volée depuis `loc_raw.csv` (colonne `rawprops`, format `Key=..;Speaker=..;Audio=..;lang_zh_Hans=..`).

3. **Mettre à jour `Duration_Japanese`** dans `DT_WwiseVoiceDuration` pour chaque événement, à partir de la durée réelle des WAV générés (voir `jp_durations.json`), et vérifier la cohérence avec `Duration_Chinese`.

4. **Implémenter le remplacement des médias** (le cœur du mod) :
   - pour chaque `event_name` du manifest, localiser le chunk `(Chinese)` dans le .ubulk de l'événement ;
   - y écrire les données du WAV japonais ;
   - réécrire le package via `provider.TrySavePackage` ;
   - vérifier que le format encodé attendu par Wwise est respecté (Wwise Vorbis `wFormatTag=0xFFFF` 48 kHz, ou format d'origine du chunk).

5. **Assembler le mod** : `ProjectPBZ/Content/Paks/~mods/PBZJapaneseVoice_9_P.{pak,ucas,utoc}` — cook IoStore depuis `F:\Games\UnrealProjects\PBZ_JP_Dub` (projet UE 5.7.4 à `F:\Epic\UE_5.7`).

6. **Tester en jeu** : voix = chinois, texte au choix.

---

## 5. Points bloquants à trancher avec l'utilisateur

- **Voix par personnage** : l'utilisateur peut fournir la liste des personnages → mapping `Character_*` → nom, et le vrai nom japonais des voix.
- **Qualité de traduction** : faire une seconde passe MT plus soignée sur les répliques longues, ou avancer tel quel sur le packaging ?
- **Format de sortie** : `.pak` simple ou conteneur IoStore segmenté (`.pak/.ucas/.utoc`) ? Le second est cohérent avec le plan initial, mais retoc ne lit pas les conteneurs segmentés, donc la vérification d'extraction finale sera plus difficile.
