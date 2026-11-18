# Notes techniques du pipeline

Ce document décrit le fonctionnement interne de chaque étape, et surtout les
pièges rencontrés dans les formats UE5 / Wwise.

---

## 1. Traduction (`src/translate/`)

- Modèle : `shun89/opus-mt-zh-ja` (fork accessible de Helsinki-NLP ; le dépôt
  d'origine renvoie un 401).
- Le modèle local suffit pour une base jouable. Il décompose littéralement les
  phrases nominales chinoises et rates les interjections courtes : `可恶` devient
  `糞!`, `什么？` devient `何?`. `fix_truncated.py` repasse ces lignes avec
  plusieurs réglages de décodage et un lexique manuel.
- Nettoyage (`clean_text.py`) : balises `<Bold>`, `</>`, ponctuation chinoise
  (`，。` → `、。`), caractères chinois non prononçables.
- Colonnes du manifest `data/manifest_jp.csv` :

  | colonne | contenu |
  |---------|---------|
  | `event_name` | nom de l'événement Wwise, unique |
  | `dialogue_key` | clé de dialogue |
  | `chinese_text` | texte source |
  | `duration_zh` | durée du média chinois, en secondes |
  | `wem_file` | fichier média associé |
  | `status` | `ok` / `no_chinese_sound` / `no_file` |
  | `japanese_text` | traduction (source, peut contenir des balises) |
  | `japanese_text_tts` | traduction nettoyée, lue par le TTS |

## 2. Synthèse vocale et alignement (`src/tts/`)

- VOICEVOX Engine 0.26.2 **CPU**, 4 instances sur les ports 50021-50024.
- Une ligne = un événement Wwise. Chaque événement a 2 variantes, `(Chinese)` et
  `(English(US))` : seule la variante chinoise est remplacée.
- **Pourquoi aligner** : le lip-sync et les sous-titres suivent la durée de l'événement
  vocal. Si la ligne japonaise est plus courte ou plus longue, la voix dérive par
  rapport à l'animation.
- **Algorithme** (`tts_refine.py`, puis `tts_align.py`) :
  1. synthèse à `speedScale = 1.0` ;
  2. mesure de l'écart avec la durée chinoise ;
  3. nouvelle synthèse avec `speedScale` recalculé (durée ∝ 1/speedScale), itérée
     jusqu'à ≤ 3 % d'écart ;
  4. padding de silence numérique (≤ 6 à 10 % de la cible), réparti entre le début et
     la fin pour préserver l'attaque et l'extinction.
- Le `speedScale` réellement utilisé est mémorisé dans `data/jp_speeds.json` : une
  exécution ultérieure affine multiplicativement au lieu de repartir de 1.0.
- Résultat actuel : les **4 167 lignes** ayant un son chinois sont à ≤ 5 % de la durée
  chinoise.

## 3. Encodage Wwise (`src/audio/`)

```
WAV 24 kHz mono (VOICEVOX)
  → ffmpeg : 48 kHz mono PCM 16 bits (le taux du jeu)
  → tools/encode.exe : Ogg Vorbis (aoTuV b6.03, VBR)
  → tools/wem.py      : Ogg Vorbis → .wem (RIFF, tag 0xFFFF, bloc "vorb")
```

Points importants :

- Tous les médias chinois du jeu sont en **48 kHz mono** (champ rate `0xBB80`) : le
  ré-échantillonner au taux du jeu évite de sortir du chemin natif du décodeur Wwise.
- Le `.wem` du jeu utilise le **channel mask `0x4101`** pour un mono ; `encode.exe`
  produit `0x4`, il faut donc réécrire le masque après conversion (`patch_mask`).
- Le.setup packet est "stripped" : chaque codebook est remplacé par son index 10 bits
  dans la bibliothèque de codebooks statiques de Wwise
  (`tools/packed_codebooks_aoTuV_603.bin`, format aoTuV b6.03).

## 4. Extraction des packages (`tools/csharp/`)

- **CUE4Parse 1.2.2.202611** + oo2core + usmap + clé AES.
- Chaque événement Wwise est un `AkAudioEvent.uasset` **avec son propre `.ubulk`** :
  `ProjectPBZ/Content/Wwise/Events/VO/Plot/<...>/<event>.uasset` + `.ubulk`.
- Le média chinois est **dans le `.ubulk` de l'événement lui-même**, pas dans
  `VO_CN` / `VO_CN_Seq` : ces deux derniers sont des `UWwiseAssetLibrary` qui ne
  contiennent que des chunks numérotés (2 581 + 820 `.wem`), ils ne sont pas la cible.
- `provider.TrySavePackage(path, out dict)` fonctionne sur les packages cuits
  (vérifié sur `DT_WwiseVoiceDuration`). En revanche `SavePackage()` relit le package
  depuis le provider : toute modification en mémoire est perdue, d'où le patch
  binaire direct (étape 5).
- `GameFile` n'expose ni `GetStream()` ni `CreateReadStream()` sur cette version :
  passer par `TrySavePackage` pour récupérer les octets.

## 5. Injection binaire (`src/patch/`)

### Layout du `.ubulk`

Le `.ubulk` est une suite de blocs contigus. Pour chaque langue (chinoise, puis
anglais), trois blocs :

| bloc | contenu |
|------|---------|
| en-tête | chunks `BKHD` + `HIRC`, le bookmark Wwise de l'événement |
| preview | les premiers octets du média, pour démarrer la lecture avant la fin du fichier |
| média | le `.wem` lui-même |

Exemple (`Vo_Plot_2D_Animation1_Hun_10_1`) :

```
[0:703]        en-tête
[703:9251]     preview      (8 548 o)
[9251:61449]   média CN     (52 198 o)
[61449:62152]  en-tête
[62152:67890]  preview      (5 738 o)
[67890:114920] média EN     (47 030 o)
```

### Table de bulk-data

Le `.uasset` décrit ces blocs par une table d'entrées de 32 octets, à l'offset 384
pour cet asset : chaque entrée est `[-1, -1, SizeOnDisk, 0, Flags, 0, OffsetInFile, 0]`.
La taille du bloc *k* est donc lue à `384 + 32k + 8`, et les blocs se suivent sans
trou : l'offset du bloc suivant est le cumul des tailles.

Le remplacement d'un média de taille différente impose donc de :

1. écrire le nouveau média à la place de l'ancien ;
2. déplacer tous les blocs qui suivent ;
3. réécrire la taille du média chinois et les offsets des blocs suivants.

`inject_bin.py` localise la table par sa signature, **vérifie que les blocs pavent le
`.ubulk` sans trou et que les offsets stockés correspondent** avant d'écrire, puis
re-vérifie après écriture : un package au layout inattendu est refusé plutôt que
corrompu.

## 6. Durées (`DT_WwiseVoiceDuration`)

| fait | détail |
|------|--------|
| taille | 7 972 lignes |
| colonnes | `Duration_Chinese`, `Duration_English`, `Duration_German`, `Duration_Japanese` |
| durées chinoises non nulles | 4 632 lignes |
| durées japonaises | **0 partout** (le jeu n'a pas de voix japonaise) |
| cible de synchronisation | 4 167 événements (ceux qui ont un son chinois) |
| volume total de voix chinoise | ~25 085 s ≈ 7 h |

Piège : la première version du script lisait les flottants comme des chaînes et
obtenait 0. Il faut lire le tag avec `UnderlyingType = typeof(float)`.

## 7. Packaging (à faire)

- Injecter les 3 924 `.uasset` / `.ubulk` patchés + la DataTable de durées dans le
  projet UE `F:\Games\UnrealProjects\PBZ_JP_Dub` (UE 5.7.4).
- Cooker en IoStore, produire
  `ProjectPBZ/Content/Paks/~mods/PBZJapaneseVoice_9_P.{pak,ucas,utoc}`.
- Les conteneurs segmentés sont plus difficiles à vérifier avec `retoc` (il ne les lit
  pas) : un `.pak` simple peut être préféré pour la phase de test.
