# État d'avancement

Dernière mise à jour : 20 novembre 2026.

## Vue d'ensemble

| # | Étape | État | Détail |
|---|-------|-------|--------|
| 1 | Traduction zh → ja | ✅ terminé | 4 252 / 4 252 lignes (modèle local `opus-mt-zh-ja`) |
| 2 | TTS japonais (VOICEVOX) | ✅ terminé | 4 253 WAV dans `out/jp_events/` |
| 3 | Alignement des durées | ✅ terminé | 4 167 lignes avec son chinois, **0 hors tolérance (≤ 5 %)** |
| 4 | Encodage Wwise | ✅ terminé | 4 167 `.wem` dans `out/jp_wem/` |
| 5 | Extraction des packages | ✅ terminé | 4 167 `.uasset` + 3 929 `.ubulk` |
| 6 | Injection du média | ✅ terminé | **4 167 / 4 167** (les 238 « sans `.ubulk` » sont dans la bibliothèque Wwise) |
| 7 | Durées japonaises dans la table | ✅ terminé | **4 167 lignes** réécrites **en place** dans `Duration_Chinese` (la colonne que le moteur lit, cf. plus bas) |
| 8 | Packaging | ✅ | conteneur IoStore construit (7 851 chunks, 3 925 packages) — installé dans le jeu, **7 851 / 7 851 chunk ids résolus par le moteur** |
| 9 | Test en jeu | 🟡 | le jeu démarre avec le mod ; **l'audio reste à écouter** |

## Découverte majeure : le jeu est un conteneur IoStore

`ProjectPBZ/Content/Paks/` ne contient pas de `.pak` de contenu : les 141 Go de
jeu sont dans `ProjectPBZ-Windows.ucas` + 65 partitions, décrits par
`ProjectPBZ-Windows.utoc`, compressés en Oodle.

Conséquence : **un `.pak` ne peut pas remplacer les voix** (les paquets d'un jeu
IoStore sont résolus par identifiant de package, pas par chemin de fichier ; testé,
le `.pak` de 1,15 Go est simplement ignoré). Le mod est donc construit comme un
**vrai conteneur IoStore** avec `retoc` (patché pour écrire le *package store*,
sans quoi le moteur ne résout aucun paquet) : voir `docs/PIPELINE.md` § 7.

## Les 243 échecs d'injection — résolus

| Cause | Nombre | Résolution |
|-------|--------|------------|
| `no .ubulk` | 238 | le média est dans la bibliothèque Wwise `VO_CN` (`PackagingStrategy = External`) : patché en place (243 blocs remplacés, 234 ok / 9 écart de durée ± 0,06 s) |
| `expected at most 2 media blocks, found 4` | 3–4 | idem |
| `no media block` | 1 | idem |
| table de bulk-data incohérente | 1 | idem |

## Le jeu n'a pas de banque voix japonaise

Rappel structurant : le jeu ne contient **que deux** banques de voix, chinoise
et anglaise. Le japonais qui y figure est du **texte** (la localisation
`ja/Game.locres`), pas de la voix.

Le mod installe donc l'audio japonais **à la place** du contenu de la banque
chinoise (le jeu continue de jouer la banque CN), et c'est la colonne
**`Duration_Chinese`** que le moteur consulte pendant la lecture : c'est elle
qui porte désormais la durée du média japonais réellement joué. Les colonnes
`Duration_Japanese` et `Duration_German` sont nulles dans ce build et ne sont
jamais lues — les remplir n'aurait aucun effet.

La réécriture se fait **en place** (le float32 existe déjà) : la taille du
fichier reste à 574 841 octets, aucun résumé de paquet ni offset de conteneur
n'est à recalculer. 4 167 lignes patchées, 0 octet de différence de taille.

Vérification : `tools/csharp/dtcheck` relit la table à travers les conteneurs
montés du jeu et retrouve la durée japonaise sur les 4 167 lignes.

## Deuxième cause des voix restées chinoises : le conteneur n'était pas montable

Le correctif d'endianness (§ suivant) était nécessaire mais **pas suffisant**.
`scripts/container.sh` définissait `RETOC` sans l'exporter, donc
`src/patch/build_container.py` utilisait son propre défaut : le retoc **stock**,
qui n'écrit pas le chunk d'en-tête de conteneur.

| binaire retoc | chunks écrits | dont en-tête (type 6) |
|---------------|---------------|-----------------------|
| stock (`C:\tools\retoc`) | 1 | **0** |
| patché (`E:\cargo_target\release`) | 2 | **1** |

Un conteneur sans en-tête est monté sans erreur visible mais **aucun paquet
n'est résolu** : le jeu joue le contenu d'origine. C'est ce que montre
CUE4Parse sur l'ancien conteneur :

```
Couldn't find chunk 0xEE8F834DFDF5AAB9 | 6 in IoStore PBZJapaneseVoice_9_P.utoc
```

Le script exporte désormais `RETOC`, et le conteneur reconstruit est bien
montable (le `dtcheck` le relit).

## Réserves connues

- **Voix par personnage** : heuristique sur le préfixe de l'événement (`data/voice_map.json`).
  La source fiable — la colonne `Speaker` de `DT_LocTable` (codes `Character_PZ_76`,
  `Character_LJC_26`…, 4 277 lignes) — **n'a pas encore été exploitée** : plusieurs
  personnages partagent donc la même voix.
- **Traduction** : `japanese_text_tts` est propre (0 ligne vide), mais 136 lignes
  conservent des balises `<Bold>` dans la colonne `japanese_text` (colonne source).
- 8 traductions dégradées restent listées dans `data/still_truncated.json`.
- La Table `DT_WwiseVoiceDuration` porte désormais la durée japonaise sur ses
  4 167 lignes dans la colonne `Duration_Chinese` (voir plus haut).

## Cause racine des voix restées chinoises — ordre des octets du package id

Le conteneur du mod était **correctement monté** par le moteur, mais aucun de ses
chunks n'était résolu : les voix jouées restaient celles du conteneur du jeu.

Le chunk id d'un paquet est fait de l'identifiant de package (8 octets), de
l'index de chunk (2 octets), d'un octet de bourrage et du type de chunk
(1 octet). Le moteur écrit l'identifiant de package **en ordre natif, donc
little-endian** :

```cpp
// Runtime/Core/Public/IO/IoChunkId.h
*reinterpret_cast<uint64*>(&Data[0]) = ChunkId;   // little-endian sur x86-64
```

L'outil `tools/csharp/chunkids` l'écrivait en **big-endian**. Les identifiants
produits ne correspondaient donc à aucun chunk du jeu :

| Ordre | Chunk ids du mod présents dans le TOC du jeu |
|-------|-----------------------------------------------|
| big-endian | **0 / 7 851** |
| little-endian | **7 850 / 7 851** |

(le 7 851ᵉ est l'en-tête de conteneur, absent du TOC du jeu par construction).

Démonstration : `tools/csharp/idprobe` recalcule les ids de tous les fichiers
vrais et les cherche dans la table de chunk ids brute du `.utoc` du jeu.

Le correctif est une ligne dans `tools/csharp/chunkids/Program.cs` :

```csharp
// avant : id[i] = (byte)(packageId.id >> (56 - 8 * i));   // big-endian
for (int i = 0; i < 8; i++) id[i] = (byte)(packageId.id >> (8 * i));  // little-endian
```

## Les 243 échecs d'injection — résolus

1. **Écouter le jeu** : le conteneur du mod est installé
   (`ProjectPBZ/Content/Paks/PBZJapaneseVoice_9_P.{pak,ucas,utoc}`), le jeu
   démarre ; vérifier que les voix sont bien japonaises (et non chinoises).
2. **Corriger l'écart de durée de 9 médias** de la bibliothèque Wwise (± 0,06 s).
3. **Mapping `Character_*` → personnage → voix VOICEVOX**, en priorité 左殇 / 魂
   (ZuoShang), qui porte 207 lignes.
4. **Nettoyage** : balises dans `japanese_text`, 8 lignes dégradées.
5. **Durées** : l'étape est faite ; le lip-sync s'appuie sur `Duration_Chinese`,
   qui porte la durée du média japonais.

## Décisions à trancher

- Voix : garder l'heuristique actuelle pour livrer vite, ou faire le mapping
  `DT_LocTable` avant le packaging ?
- `retoc` patché : le correctif doit être rejoué à chaque mise à jour de l'outil
  (le patch est décrit dans `docs/PIPELINE.md` § 7) ; on peut aussi proposer le correctif
  à l'auteur upstream.

## Journal

- **16/11** — extraction du jeu, traduction, premier passage TTS. (`docs/CHECKPOINT.md`)
- **17/11** — ré-écriture des `.wem` au format exact du jeu, premier patch binaire.
- **18/11** — campagne d'alignement des durées, encodage des 4 167 médias, injection
  de 3 924 packages, nettoyage du dépôt et mise en place du dépôt Git
  (`github.com/Shura2jZ/JapBladeZero`, remote en SSH).
- **19/11** — cause racine des 238 échecs (média dans la bibliothèque Wwise
  `VO_CN`) ; abandon du `.pak` au profit d'un conteneur IoStore construit avec
  `retoc` patché ; conteneur du mod installé dans le jeu.
- **20/11** — cause racine des voix restées chinoises : **ordre des octets du
  package id** dans le chunk id (big-endian au lieu de little-endian) ; 0 chunk
  résolu avant, 7 850 / 7 851 après. Conteneur reconstruit et réinstallé.
  Déplacement des artefacts lourds (`build/`, `out/`) vers `E:` via jonctions.
- **21/11** — deuxième cause des voix restées chinoises : le conteneur était
  construit avec le **retoc stock**, sans chunk d'en-tête, donc non montable.
  `RETOC` est désormais exporté par le script. Durées japonaises écrites **en
  place** dans `Duration_Chinese` (4 167 lignes), la DataTable patchée est
  ajoutée au conteneur, et `tools/csharp/dtcheck` relit la table à travers le
  montage du jeu pour confirmer.
