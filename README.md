# JapBladeZero

**Full japanese dub mod for Phantom Blade Zero** — un mod qui remplace la voix chinoise
du jeu par une voix japonaise synthétisée, en conservant le lip-sync et les sous-titres
d'origine.

> Le jeu (UE 5.7.4, Steam build 26367565) n'a pas de version japonaise : la colonne
> `Duration_Japanese` de la DataTable `DT_WwiseVoiceDuration` est à 0 partout. Ce mod
> comble ce trou en réinjectant de l'audio japonais à la place de l'audio chinois.

---

## État actuel

| Étape | État | Note |
|-------|-------|------|
| Traduction zh → ja | ✅ terminé | 4 252 / 4 252 lignes |
| Synthèse vocale (VOICEVOX) | ✅ terminé | 4 253 WAV |
| Alignement sur la durée chinoise | ✅ terminé | 4 167 / 4 167 lignes à ≤ 5 % |
| Encodage Wwise (`.wem`) | ✅ terminé | 4 167 médias |
| Extraction des packages du jeu | ✅ terminé | 4 167 `.uasset` + 3 929 `.ubulk` |
| Injection binaire du média | 🟡 94 % | 3 924 événements patchés, 243 échecs |
| Écriture de `Duration_Japanese` | ❌ à faire | 0 / 4 252 |
| Packaging IoStore (`~mods`) | ❌ à faire | |
| Test en jeu | ❌ à faire | |

Le détail (blocages, décisions en attente) est dans [`docs/STATUS.md`](docs/STATUS.md).

---

## Comment le mod est fabriqué

```
manifest du jeu (4230+ événements)
   │
   ├─ 1. traduction      zh → ja, modèle local MarianMT ......... src/translate/
   ├─ 2. TTS             VOICEVOX, 1 voix par personnage ........ src/tts/
   ├─ 3. alignement      speedScale itératif + silence padding .. src/tts/tts_align.py
   ├─ 4. encodage        WAV 24 kHz → .wem Wwise Vorbis 48 kHz ... src/audio/
   ├─ 5. extraction      packages du jeu via CUE4Parse .......... tools/csharp/
   ├─ 6. injection       patch binaire du .ubulk + table ....... src/patch/
   └─ 7. packaging       DataTable durées + cook IoStore → ~mods
```

Chaque étape est un script indépendant : le pipeline est relanceable étape par étape,
et les scripts ne font que ce qu'ils savent faire.

Les détails techniques (formats, offsets dans le `.ubulk`, pièges UE/Wwise) sont dans
[`docs/PIPELINE.md`](docs/PIPELINE.md).

---

## Organisation du dépôt

```
src/translate/    traduction et nettoyage du texte
src/tts/          synthèse vocale et alignement des durées
src/audio/        encodage des médias Wwise
src/patch/        injection binaire dans les packages du jeu
tools/csharp/     outils C# (CUE4Parse) : extraction et inspection
tools/            encodeur aoTuV + convertisseur .wem
data/             manifest, traductions, durées, tables de correspondance
docs/             documentation technique et état d'avancement
scripts/          raccourcis pour relancer une étape
build/, out/      artefacts générés (ignorés par git)
```

---

## Reprendre le travail

```bash
git clone https://github.com/Shura2jZ/JapBladeZero.git
cd JapBladeZero
cp pbz_paths.example.txt pbz_paths.txt   # puis compléter les chemins locaux
```

Dépendances : Python 3.10+, `imageio-ffmpeg`,
[VOICEVOX Engine 0.26](https://github.com/VOICEVOX/voicevox_engine) (CPU suffit),
et .NET 10 pour les outils C#.

```bash
# le texte japonais vient du jeu lui-même (localisation "ja")
dotnet tools/csharp/locres/bin/Release/net10.0/locres.dll --culture ja
python src/translate/official_text.py --locres E:/PBZ_Build/build/locres/ja_Game.json

# une voix par personnage, résolue par la colonne "Speaker" de DT_LocTable
python src/tts/voicevox_styles.py      # styles du moteur (ids valides)
python src/tts/voice_assign.py         # personnage -> style

bash scripts/tts.sh         # voix + alignement
bash scripts/wem.sh         # encodage .wem
bash scripts/patch.sh       # injection
bash scripts/container.sh E:/PBZ_Mod   # conteneur IoStore du mod
```

> Le moteur VOICEVOX est un dossier de 2 Go : il est extrait dans `E:/PBZ_Build/voicevox`
> (ou `voicevox/windows-cpu` dans le dépôt), et n'est pas versionné. Les
> identifiants de style utilisés par `voice_map.json` dépendent de la version du
> moteur : `src/tts/voicevox_styles.py` les résout par le couple (voix, style).

> Les modèles, le moteur VOICEVOX et les médias générés ne sont pas versionnés :
> ils sont reconstruits par les scripts ci-dessus.

---

## Outils et crédits

- **[CUE4Parse](https://github.com/FabianFG/CUE4Parse)** — lecture des assets UE5
- **[VOICEVOX](https://github.com/VOICEVOX/voicevox_engine)** — synthèse vocale japonaise
- **Wwise** — format média du jeu (Vorbis, `wFormatTag=0xFFFF`, 48 kHz mono)

> Le texte japonais des répliques n'est pas traduit : il est extrait de la
> localisation `ja` du jeu lui-même, qui est plus fidèle qu'une traduction
> automatique.

## Avertissement

Ce mod est un projet de fan, non affilié à S-GAME / Blade Entertainment. Il ne
distribue aucun contenu du jeu : il ne contient que les voix japonaises synthétisées
et les outils nécessaires pour les injecter. Les fichiers du jeu ne doivent être
extraits que par les personnes qui en possèdent une copie.
