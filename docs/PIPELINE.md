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

- VOICEVOX Engine 0.26.2 **CPU**, 4 instances sur les ports 50021-50024
  (`bash scripts/voicevox.sh start 4`). Chaque moteur charge son modele et pèse
  sur le CPU : on n'en lance pas plus que nécessaire.
- Une ligne = un événement Wwise. Chaque événement a 2 variantes, `(Chinese)` et
  `(English(US))` : seule la variante chinoise est remplacée.
- **La voix de chaque personnage n'est pas choisie au hasard** : le jeu fournit
  une voix chinoise à chaque personnage, dont la hauteur (F0) est mesurée
  (`src/audio/voice_profile.py`), et les voix VOICEVOX sont profilées de la même
  façon (`src/audio/voicevox_profile.py`). `src/tts/voice_assign.py` donne à
  chaque personnage la voix la plus proche de la sienne (écart médian : 3 %).
- **Pourquoi aligner** : le lip-sync et les sous-titres suivent la durée de l'événement
  vocal. Si la ligne japonaise est plus courte ou plus longue, la voix dérive par
  rapport à l'animation.
- **Pourquoi on ne touche pas à la vitesse de la voix** : la ligne japonaise est
  une traduction, elle n'a pas la longueur de la ligne chinoise (mesuré : 60 % des
  lignes s'en écartent de plus de 20 %). Ajuster la `speedScale` pour que les
  deux durées coïncident demandait des vitesses de 0,5 à 2,0 : c'est-à-dire des
  voix ralenties de moitié ou doublées, audibles et laides. La version précédente
  se comportait encore plus mal : la passe finale coupait la fin des phrases
  quand la limite de vitesse était atteinte.
- **Algorithme** (`tts_refine.py`, puis `tts_align.py`) :
  1. synthèse à la vitesse naturelle du moteur (`speedScale = 1.0`) ;
  2. si la ligne dépasse son créneau chinois, elle est compressée, **au plus de
     15 %** ; au-delà, elle est laissée telle quelle ;
  3. si elle est plus courte, le reste du créneau est comblé par du silence
     numérique (≤ 30 % du créneau), placé **à la fin** : la ligne commence
     quand elle doit, et le créneau garde sa longueur ;
  4. la table des durées (`DT_WwiseVoiceDuration`) est ensuite écrite avec la
     longueur **réelle** du média japonais : le jeu sait donc combien de temps
     dure la ligne, et ne la coupe jamais en plein milieu.
- Les ports et le nombre de workers se règlent par l'environnement
  (`VOICEVOX_PORTS`, `VOICEVOX_WORKERS`).

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

### Quelle colonne écrire : `Duration_Chinese`

Le jeu n'a que **deux** banques de voix, chinoise et anglaise ; le japonais
qu'il contient est du **texte** (la localisation `ja/Game.locres`). Le mod
installe donc l'audio japonais **à la place** du contenu de la banque chinoise,
et le moteur continue de jouer cette banque : la durée qu'il consulte pendant
la lecture est `Duration_Chinese`. Les colonnes `Duration_Japanese` et
`Duration_German` sont nulles partout dans ce build et ne sont jamais lues.

Écrire `Duration_Japanese` n'aurait donc aucun effet, et coûterait cher : la
propriété n'existe pas encore dans le fichier, il faudrait **insérer** 4 octets
par ligne, donc modifier la taille de l'export `UDataTable` et du résumé du
paquet.

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

### Patch en place (`src/patch/patch_dt_durations.py`)

`tools/csharp/durations` sait lire et écrire la valeur en mémoire, mais
`TrySavePackage` ne persiste pas la modification (fichier identique à l'octet
près) → il faut passer par un patch binaire.

La bonne nouvelle : réécrire `Duration_Chinese` **en place** ne change **pas** la
taille du fichier (le float32 existe déjà dans les 4 632 lignes concernées), donc
ni la taille de l'export, ni le résumé du package, ni les offsets du conteneur ne
sont à recalculer.

Le script ne se fie pas au layout : pour chaque ligne, il cherche la séquence
exacte

```
nom + "\0" + float32(durée chinoise actuelle)
```

et n'écrit que si elle est trouvée — la valeur relue est donc bien une valeur
que le moteur stockait. La taille du fichier est vérifiée identique avant et
après, et chaque ligne patchée est relue.

Résultat : **4 167 lignes** réécrites, 6 117 octets modifiés (tous dans des zones
de 3 octets au plus), **0 octet** de différence de taille.

Les 86 lignes restantes n'ont pas de durée chinoise : leur audio reste chinois,
leur durée doit donc rester chinoise.

### Quelle durée écrire : celle du média injecté

La durée écrite est celle du **média que le moteur joue**, c'est-à-dire le `.wem`
injecté, pas le WAV source. Les `.wem` sont des Ogg Vorbis enveloppés dans un
en-tête Wwise : leur durée décodée est mesurée par `src/audio/wem_durations.py`
(`pyvgmstream`). Contrôle : les 4 167 durées mesurées sont **identiques au bit
près** (0,0 ms d'écart) à celles des WAV sources, et la durée chinoise de la
table correspond bien à la durée décodée du média chinois d'origine — la
colonne porte donc bien la durée du média.

### Vérification

`tools/csharp/dtcheck` relit la table **à travers les conteneurs montés du jeu**
(donc comme le moteur) et compare chaque ligne :

```
rows=7972 rowStruct=WwiseVoiceDurationRow
rows with a Japanese duration : 4253
  Chinese column = Japanese duration : 4167
  Chinese column = original Chinese : 56
  other                            : 0
```

Écart JP vs CN mesuré avant patch : médiane 0,021 %, max 3,74 % (0,152 s).

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

> **Piège : il faut le retoc *patché*, pas le retoc stock.** Les deux binaires
> ont le même nom et le même rôle, mais le stock n'écrit pas le chunk
> d'en-tête de conteneur (type 6) :
>
> | binaire | chunks écrits | dont en-tête (type 6) |
> |---------|----------------|----------------------|
> | `C:\tools\retoc\retoc.exe` (stock) | 1 | **0** |
> | `E:\cargo_target\release\retoc.exe` (patché) | 2 | **1** |
>
> Un conteneur sans en-tête est monté sans erreur apparente mais **aucun paquet
> n'est résolu** : le jeu joue alors le contenu d'origine. C'est exactement ce
> que montre CUE4Parse :
>
> ```
> Couldn't find chunk 0xEE8F834DFDF5AAB9 | 6 in IoStore PBZJapaneseVoice_9_P.utoc
> ```
>
> `scripts/container.sh` doit donc **exporter** `RETOC`, sinon
> `src/patch/build_container.py` utilise son propre défaut (le retoc stock) :
>
> ```bash
> export RETOC="${RETOC:-E:/cargo_target/release/retoc.exe}"
> ```

### Le nom du pak détermine qui gagne (cause de l'audio original)

Le moteur monte les paks de `ProjectPBZ/Content/Paks/` et leur donne un
**ordre** (`FPakPlatformFile::GetPakOrderFromPakFilePath`) :

| condition (chemin relatif au répertoire du projet) | ordre |
|---|---|
| `Paks/ProjectPBZ-…` | **4** |
| `Paks/…` (autre) | 3 |
| `Engine/Content/…` | 2 |
| `Saved/…` | 1 |

Le nom de pak du jeu est `ProjectPBZ-Windows.pak` : il obtient l'ordre **4**.
Un pak du mod nommé autrement (par exemple `PBZJapaneseVoice_9_P.pak`)
n'obtient que l'ordre **3**.

Or les conteneurs IoStore sont triés par ordre **décroissant** et le premier
conteneur qui contient le chunk gagne (`FFileIoStore::GetChunkInfo`,
`FileIoDispatcherBackend.cpp`) : avec l'ordre 3, le conteneur du **jeu** passe
devant, le mod est monté sans erreur… et le jeu joue le contenu d'origine.

Deux conditions à réunir pour que le mod gagne :

1. **même ordre que le jeu** → le nom doit commencer par `ProjectPBZ-` ;
2. **monté après le jeu** → les paks sont montés dans l'ordre *décroissant* du
   nom, donc le nom du mod doit être **plus petit** que `ProjectPBZ-Windows`.

D'où le nom retenu : `ProjectPBZ-JapaneseVoice`. La garde-fou de
`scripts/container.sh` vérifie les deux conditions avant de construire quoi que
ce soit.

### Chaîne de fabrication du mod

```bash
python src/patch/build_container.py --files data/container_files.tsv --out E:/PBZ_Mod
# -> E:/PBZ_Mod/ProjectPBZ-JapaneseVoice.{ucas,utoc}
# + un .pak vide (le moteur monte le conteneur de même nom)
UnrealPak.exe ProjectPBZ-JapaneseVoice.pak -Create=<liste vide> -MountPoint="../../../"
```

Installation :

```
ProjectPBZ/Content/Paks/ProjectPBZ-JapaneseVoice.pak    (vide, 339 o)
ProjectPBZ/Content/Paks/ProjectPBZ-JapaneseVoice.ucas   (1 155 Mo)
ProjectPBZ/Content/Paks/ProjectPBZ-JapaneseVoice.utoc   (1,1 Mo)
```

Contrôle : CUE4Parse relit le conteneur du mod et renvoie bien la version
japonaise (`.ubulk` de 96 477 o au lieu de 114 920 o).

## 8. Le texte japonais officiel du jeu

Le jeu ne fournit pas de voix japonaise, mais il fournit **le texte japonais**.
La culture `ja` est compilée dans le conteneur :

```
ProjectPBZ/Content/Localization/Game/ja/Game.locres
```

C'est un `FTextLocalizationResource` : 11 142 entrées, dont **5 076 lignes de
dialogue** (`Dlg_*`) et les chaînes d'interface. Le jeu sait donc déjà
afficher ses propres sous-titres japonais (réglage « テキスト言語 »).

Conséquence majeure : **notre traduction automatique du chinois était
inutile, et fausse**. Traduisant de la 2ᵉ à la 3ᵉ langue à travers le
chinois, elle massacrait les noms propres (`左殇` → « 左利き », c'est-à-dire
« gaucher »). Les 4 167 lignes patchées ont un texte officiel, et 4 154
diffèrent de notre version.

### Extraction

Le `.locres` n'est pas un paquet : il vit dans le `.pak` chiffré du jeu.

| étape | comment |
|-------|---------|
| extraction | `tools/csharp/locres` — monte les conteneurs du jeu, lit `ja/Game.locres` et le sérialise en JSON (`TrySaveAsset` + `CUE4Parse.UE4.Localization.FTextLocalizationResource`) |
| format | magic `7574140E-FC034A67-9D90154A-1B7F37C3`, version 3 (`Optimized_CityHash64_UTF16`), table de chaînes à l'offset 16 |
| injection | `src/translate/official_text.py` — joint sur la clé `Dlg_*` du manifeste et remplace `japanese_text` / `japanese_text_tts` (balises `<Bold>` retirées) |

Résultat : **4 252 / 4 252 lignes** ont un texte officiel, 0 manquant.

### API

```
dotnet tools/csharp/locres/bin/Release/net10.0/locres.dll --culture ja
python src/translate/official_text.py --locres E:/PBZ_Build/build/locres/ja_Game.json
```

## 9. Qui parle : l'identité officielle des personnages

`DT_LocTable` porte, à côté de la clé de dialogue, deux colonnes :

| colonne | contenu |
|---------|---------|
| `Audio` | nom de l'événement Wwise (`Vo_Plot_2D_Animation5_MuTianMiao_1`) |
| `Speaker` | code du personnage (`Character_Main_1`, `Character_Imp_18`, ...) |

C'est la **seule source officielle** de l'identité d'un locuteur : le nom de
l'événement ne fait qu'y faire allusion. La jointure couvre **99,7 %** des
événements patchés (`data/event_speaker.json`).

Le genre se déduit du texte japonais de ses répliques (pronoms de première
personne : 俺/僕 masculins, 私/あたし féminins). Le chinois ne permet rien :
他 et 她 se prononcent pareil.

Le mapping final (`src/tts/voice_assign.py` → `data/character_voices.json`)
affecte **440 personnages** sur **125 styles** VOICEVOX (le moteur expose 44
voies et 128 styles ; le paramètre `speaker` de l'API est un *style*, et ces
ids changent d'une version à l'autre, ils sont donc résolus par le couple
(voix, style)).

Les trois scripts de synthèse (`tts_generate`, `tts_refine`, `tts_align`)
passent par `src/tts/voices.py`, qui lit ce mapping et retombe sur l'ancien
mapping par préfixe quand le personnage est inconnu.

## 10. Emplacement des fichiers de travail

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
