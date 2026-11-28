# 07 — Production GPT-SoVITS fine-tuné (2026-11-27/28)

## Verdict utilisateur
Blind test dédié 魂 (13 lignes, prises QC-validées) : **GPT-SoVITS fine-tuné 12/12**
— « pas photo », nettement meilleur (voix, ton, émotions). VOICEVOX/CosyVoice battus.

## Ce qui est en place
- **157 personnages fine-tunés** (SoVITS v2, epochs 8 si ≥10 répliques, 4 si 5-9) :
  `E:/TTS_Lab/GSV/GPT-SoVITS-v3lora-20250228/SoVITS_weights_v2/*.pth` (13 Go)
  → **3590/4252 répliques (85 %)** couvertes par le timbre original du personnage.
  Journal reconstruit depuis le disque : `data/gsv_weights.json` (ne plus écraser à la main).
- Pipeline : `src/tts/gsv_batch.py` (décodage + prep + train par personnage, resumable,
  skip si poids existants, purge des logs d'entraînement ~1.2 Go/perso après succès).
- Génération : `src/tts/generate_gsv.py` — poids chargés dans api_v2 (port 9891) via
  `/set_sovits_weights` à chaque changement de personnage, référence chinoise du
  personnage choisie par profil (durée ×3 + f0, `data/cn_voice_profiles.json`),
  4 refs candidates, QC (f0 dans [0.4×f0c ; 2.5×f0c], durée ≤ max(3.5 s, 1.9×durée_cn)),
  repli VOICEVOX si 4 échecs. Sortie : `out/jp_events_gsv/` (WAV 32 kHz).
- Sorties parallélisées : `--shard 0 --nshard 2 --port 9891` et `--shard 1 --nshard 2 --port 9892`.

## État à la pause (2026-11-28)
- Prises fines-tunées : **2468/3590 faites** (dont ~1200 régénérées après suppression
  des prises VOICEVOX de repli détectées par fréquence 24 kHz vs 32 kHz).
- Reste : **1122 répliques fine-tunées** (~1 h 30-2 h GPU, 2 workers) PUIS **1784
  répliques** des ~280 petits personnages (<5 répliques chinoises ; zéro-shot GSV ou
  repli VOICEVOX — stratégie à décider).
- **Disque E: plein** (0 libre) a causé les derniers échecs ; 35 Go libres après
  suppression de CosyVoice (9.1 Go, re-téléchargeable si besoin via snapshot_download
  FunAudioLLM/Fun-CosyVoice3-0.5B-2512). À surveiller : 13 Go de poids + datasets.
- Prises 24 kHz restantes dans out/jp_events_gsv = prises VOICEVOX de repli à
  régénérer (script de purge : wave.getframerate() != 32000 → delete + rerun).

## Pièges rencontrés (à relire avant de relancer)
- `gsv_weights.json` : les processus orphelins l'écrasaient entre eux → TOUJOURS
  reconstruire depuis `os.listdir(SoVITS_weights_v2)` (nom = `f.split('_e')[0]`).
- Deux serveurs api_v2 simultanés = « paging file too small » sous 32 Go RAM quand
  les serveurs VOICEVOX tournent aussi → 1 worker GSV + 1 VOICEVOX si RAM juste.
- Les workers Python (et serveurs) survivent aux timeouts bash → identifier les
  process avec `wmic process where "name='python.exe' and commandline like
  '%%generate_gsv%%'"` ; dans Git Bash, taskkill s'écrit `//F //PID`.
- grep -cv "CommandLine" sur wmic compte aussi les lignes d'en-tête (2 = zéro process).
- Le service VOICEVOX `run.exe` (2 instances) mange ~1.8 Go chacun.

## Prochaines étapes
1. Finir les 1122 répliques fine-tunées (workers shards, serveur 9891).
2. Purger/régénérer les prises 24 kHz restantes.
3. Petits personnages (1784 répliques) : zero-shot GSV (réf = réplique du perso,
   boucle QC, sinon VOICEVOX) — à coder dans generate_gsv (branche `weights` absente).
4. Normalisation/pacing (benchmark_norm, alignement sur durées chinoises),
   test à l'aveugle échantillon pour validation utilisateur.
5. Réencodage Wwise + rebuild conteneur + install.
