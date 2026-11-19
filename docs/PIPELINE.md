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

### Layout binaire (identifié par sondes)

Écriture d'une ligne (le nom est la clé de la table, les valeurs suivent) :

```
[FString nom (longueur + caractères + 0)]
[Duration_Chinese  float32]   <- seulement si non nul
[Duration_English float32]   <- seulement si non nul
[Duration_German  float32]   <- seulement si non nul
[Duration_Japanese float32]  <- seulement si non nul
[int32 X]  [int32 2]  [FName 4 o]  [3 o]
```

Les propriétés **à valeur nulle ne sont pas écrites** : la longueur de la ligne
vaut 23 octets si chinois et anglais sont non nuls, 19 si un seul l'est, 15 si
aucun ne l'est. Vérifié sur les 7 971 lignes (CN retrouvé à +0 dans 4 631/4 631
cas, EN à +4 dans 4 387/4 388).

Conséquence : écrire `Duration_Japanese` impose **d'insérer** 4 octets par ligne
(la propriété n'existe pas encore dans le fichier), donc de modifier la taille de
l'export `UDataTable` et du résumé du package. `tools/csharp/durations` sait lire
et écrire en mémoire, mais `TrySavePackage` ne persiste pas la modification
(fichier identique à l'octet près) → il faut passer par un patch binaire.

Méthode de vérification (sans CUE4Parse en écriture) : construire un petit
conteneur IoStore avec la DataTable modifiée (un seul chunk) et le relire avec
`tools/csharp/durations` — le conteneur du mod est prioritaire dans le lecteur.

Impact limité : la voix japonaise est alignée sur la durée chinoise (± 0,06 s),
donc le lip-sync reste correct tant que la table n'est pas mise à jour.

## 7. Packaging : le jeu est un conteneur IoStore (et non un `.pak`)

### Ce que contient l'installation

```
ProjectPBZ/Content/Paks/
  ProjectPBZ-Windows.pak      223 Mo     index « pak » (fichiers non empaquetés)
  ProjectPBZ-Windows.ucas     2,1 Go     données des chunks
  ProjectPBZ-Windows.utoc     47 Mo      table des chunks (TOC)
  ProjectPBZ-Windows_s1..s65.ucas        65 autres partitions (2 Go chacune)
```

Les 141 Go de contenu ne sont **pas** dans des `.pak` : ils sont dans un conteneur
IoStore. Chaque fichier (`.uasset`, `.ubulk`) est un *chunk* :

| fait | détail |
|------|--------|
| identifiant de chunk | 12 octets = id de package (8 o) + index (2 o) + padding (1 o) + type (1 o) |
| id de package | `FPackageId.FromName("/Game/<chemin sans extension>")`, écrit **en little-endian** (ordre natif) |
| type 1 | export bundle (le `.uasset`) |
| type 2 | bulk data (le `.ubulk`) |
| type 1 | export bundle (le `.uasset`) |
| type 2 | bulk data (le `.ubulk`) |
| compression | Oodle, blocs de 256 Ko, chiffrement AES |
| blocs | 1 360 361 blocs, offsets dans l'espace décompressé |
| version du TOC | `ReplaceIoChunkHashWithIoHash` |

Vérifié : `CHUNKID(VO_CN.uasset) = c3e3f641696cd69700000001`,
`CHUNKID(VO_CN.ubulk) = c3e3f641696cd69700000002` — les mêmes valeurs que dans le
TOC du jeu.

> **Piège : l'ordre des octets de l'id de package.** Le moteur écrit l'id de
> package en ordre natif (`*reinterpret_cast<uint64*>(&Data[0]) = ChunkId`),
> donc **little-endian** sur x86-64. Écrit en big-endian, l'id ne correspond à
> aucun chunk du jeu : le conteneur est monté mais **aucun chunk n'est résolu**,
> et le jeu joue alors les voix d'origine. C'est ce qui est arrivé ; le contrôle
> (`tools/csharp/idprobe`) consiste à recalculer les ids de tous les fichiers
> et à les chercher dans la table brute du `.utoc` du jeu :
>
> | Ordre | Chunk ids du mod présents dans le TOC du jeu |
> |-------|-----------------------------------------------|
> | big-endian | 0 / 7 851 |
> | little-endian | 7 850 / 7 851 |

### Pourquoi un `.pak` ne peut pas fonctionner

- Les paquets d'un jeu IoStore n'ont pas le *magic* legacy (`0x9E2A83C1`) : les
  fichiers extraits commencent par `00 00 00 00`, ils sont resolus **par id de
  package** via le *package store* du conteneur, pas par chemin de fichier.
- Testé : un `.pak` de 1,15 Go contenant les 7 850 fichiers patchés est ignoré par
  le jeu (démarrage normal, aucune erreur) ; un pak volontairement corrompu ne
  provoque pas non plus de crash → le moteur ne lit jamais ces fichiers.
- Le moteur ne scanne que `ProjectPBZ/Content/Paks/` (chaque `.pak` monte le
  conteneur de même nom) : il n'existe pas de dossier `~mods` dans cette version
  d'UE (5.7).

### La solution : construire un conteneur IoStore avec retoc

`retoc` (Rust, <https://github.com/trumank/retoc>) sait écrire un conteneur :

```
retoc pack-raw <dossier> <sortie.utoc>
```

où le dossier contient `chunks/<id de chunk 12 octets en hex>` et un
`manifest.json` :

```json
{ "chunk_paths": { "<id>": "../../../ProjectPBZ/Content/..." },
  "version": "ReplaceIoChunkHashWithIoHash", "mount_point": "../../../" }
```

**Patch nécessaire** : la commande `pack-raw` d'origine écrit le conteneur *sans*
en-tête de conteneur → `packages: 0` → le moteur ne peut résoudre aucun paquet.
Le correctif (dans `retoc_cli/src/main.rs`) passe une version d'en-tête au writer
et enregistre les chunks de type *export bundle* dans le *package store* :

```rust
let container_header_version = config.container_header_version_override
    .unwrap_or(EIoContainerHeaderVersion::SoftPackageReferencesOffset);
let mut writer = IoStoreWriter::new(args.utoc, manifest.version,
                                     Some(container_header_version),
                                     manifest.mount_point.into())?;
...
if chunk_id.get_chunk_type() == EIoChunkType::ExportBundleData {
    let store_entry = retoc::container_header::StoreEntry {
        export_bundles_size: data.len() as u64, load_order: 0,
        export_count: 0, export_bundle_count: 0,
        imported_packages: Vec::new(), shader_map_hashes: Vec::new() };
    writer.write_package_chunk(chunk_id, path, &data, &store_entry)?;
} else {
    writer.write_chunk_raw(chunk_id_raw, path, &data)?;
}
```

Compilation (GNU, il faut `E:\msys64\usr\bin` et `E:\msys64\ucrt64\bin` dans le
`PATH`, sinon `ld` sort en erreur 53) :

```bash
export CARGO_TARGET_DIR=E:/cargo_target
export PATH="$PATH:/e/msys64/usr/bin:/e/msys64/ucrt64/bin"
cargo build --release -p retoc_cli
```

### Chaîne de fabrication du mod

```bash
python src/patch/build_container.py --files data/container_files.tsv --out E:/PBZ_Mod
# -> E:/PBZ_Mod/PBZJapaneseVoice_9_P.{ucas,utoc}
# + un .pak vide (le moteur monte le conteneur de même nom)
UnrealPak.exe PBZJapaneseVoice_9_P.pak -Create=<liste vide> -MountPoint="../../../"
```

Installation :

```
ProjectPBZ/Content/Paks/PBZJapaneseVoice_9_P.pak    (vide, 339 o)
ProjectPBZ/Content/Paks/PBZJapaneseVoice_9_P.ucas   (1 155 Mo)
ProjectPBZ/Content/Paks/PBZJapaneseVoice_9_P.utoc   (1,1 Mo)
```

Contrôle : CUE4Parse relit le conteneur du mod et renvoie bien la version
japonaise (`.ubulk` de 96 477 o au lieu de 114 920 o).

## 8. Emplacement des fichiers de travail

Les artefacts lourds (paquets extraits et patchés, WAV et `.wem` générés) ne
sont pas versionnés et n'ont pas leur place sur le disque système. Par défaut
ils vivent sur `E:` ; le dépôt y accède par **jonctions de répertoire** :

```
C:\...\JapBladeZero\build  ->  E:\PBZ_Build\build     (2,7 Go)
C:\...\JapBladeZero\out    ->  E:\PBZ_Build\out       (1,6 Go)
```

Créées sous Windows avec :

```cmd
mklink /J build E:\PBZ_Build\build
mklink /J out   E:\PBZ_Build\out
```

Les chemins des scripts restent donc relatifs au dépôt : rien à changer après
un `git clone`. Le dossier de travail de la construction du conteneur est
précisé explicitement pour ne pas saturer le disque système :

```bash
python src/patch/build_container.py --files data/container_files.tsv \
    --out E:/PBZ_Mod --work E:/PBZ_Build/container
```
