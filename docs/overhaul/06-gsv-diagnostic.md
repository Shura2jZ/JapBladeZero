# GPT-SoVITS : diagnostic zéro-shot et plan de fine-tuning (26/11)

## Mesures

- **v2, zéro-shot cross-lingue** (prompt = une réplique chinoise du personnage) :
  **instable, ~50 % d'échec**. Quatre lignes testées : 2 saines (118 Hz, 86 Hz),
  2 en bip strident (1600 Hz, 1524 Hz). Le « monstre » entendu dans l'A/B
  correspond à ces échecs — la synthèse part dans les aigus, le fichier reste
  techniquement sain (32 kHz, crête normal).
- **v3 via api_v2** : impossible dans ce build (assert v1/v2 dans
  TTS_infer_pack/TTS.py) ; les poids v3 chargés en force produisent un bip pur
  (87 % de l'énergie en 4-9 kHz) — vocoder BigVGAN jamais branché par l'API.
  v3 n'est utilisable que par le webui de ce package.

## Ce qui est en place

- package intégré v3lora extrait sur `E:/TTS_Lab/GSV/`, serveur api_v2 (port
  9891, CUDA, fp16), ffmpeg dans le PATH du serveur, PYTHONUTF8=1 ;
- sélecteur de référence par profil (`src/tts/ref_select.py`, 39/40 lignes
  avec une réplique du même personnage de 3-10 s) ;
- runner `src/tts/benchmark_gsv.py` (39/40 prises en v2, à refaire après
  fine-tune) ;
- niveaux calibrés, test A/B/C en attente d'un GSV stable.

## Plan retenu : fine-tuning SoVITS v2 par personnage

Le zéro-shot est une loterie ; le workflow conçu de GPT-SoVITS est
l'entraînement sur les données du locuteur. Nos données : répliques chinoises
décodables à la demande + transcriptions officielles (manifest).

1. construire le dataset d'un personnage (LY, le vieux : ~100 lignes) :
   décodage → wavs + fichier `.list` (`chemin|nom|zh|texte`) ;
2. exécuter la chaîne de préparation du package (get-hubert-wav32k,
   get-semantic) sur ces données ;
3. fine-tune SoVITS v2 (s2_train.py, config écrite à la main, GPU) — quelques
   minutes sur la 3080 ;
4. inférence avec les poids fine-tunés + GPT de base (motif documenté :
   « ne fine-tuner que le SoVITS » pour la stabilité multilingue) ;
5. régénérer les 40 prises → A/B/C.

Si le fine-tune ne stabilise pas le japonais (langue croisée sur un modèle
fine-tuné en chinois), GSV sera écarté — et la marge de progression
reviendra à VOICEVOX (prosodie par ponctuation/intonation) + sélection
d'émotion par style.
