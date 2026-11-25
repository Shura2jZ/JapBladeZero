# Résultats de l'écoute à l'aveugle (40 paires, 40 réponses)

Écoute faite le 25/11 sur la version corrigée (niveaux calibrés à -22 dBFS,
plus de clipping, plus de bug float32/int16).

## Score global

| moteur | voix préférées |
|---|---|
| VOICEVOX | **25 (62 %)** |
| CosyVoice 3 | 15 (38 %) |

| catégorie | VOICEVOX | CosyVoice 3 |
|---|---|---|
| longue / émotion | 4/6 | 2/6 |
| homme âgé | 5/8 | 3/8 |
| femme | 6/8 | 2/8 |
| jeune homme | 5/8 | 3/8 |
| courte | 2/4 | 2/4 |
| cri / combat | 3/6 | 3/6 |

## Remarque décisive de l'auditeur

« À chaque fois que je choisis une option, l'autre a un avantage — souvent la
retranscription des émotions — mais je ne la choisis pas parce que l'autre
sonne beaucoup mieux et moins synthétique. »

Lecture : **CosyVoice 3 restitue mieux l'émotion et la prosodie**, mais son
rendu est jugé plus synthétique ; VOICEVOX sonne plus propre mais plat.
C'est exactement le compromis redouté par le brief : ni la propreté sans
direction d'acteur, ni l'expressivité avec un timbre artificiel.

## Interprétation technique

- le clonage zero-shot d'une voix **chinoise** vers du japonais (0.5B, refs
  décodées du jeu avec leurs artefacts de compression) donne un timbre
  irrégulier, instable entre les prises — d'où le « synthétique » ;
- les instructions de jeu (`instruct2`) fonctionnent : c'est l'émotion que
  l'auditeur a repérée comme avantage ;
- la femme / jeune homme (8/2, 5/3) : les voix clonées féminines dérivent
  davantage sur les longues lignes.

## Suites possibles (ordre proposé)

1. **S2-Pro local (4B)** — même famille que Drama 3, tient en 10 Go (serré) :
   qualité de synthèse nettement supérieure au 0.5B de CosyVoice, même
   contrôle émotionnel. Vérifier la Research License des poids avant.
2. **GPT-SoVITS fine-tuné** sur les personnages principaux (centaines de
   répliques chinoises disponibles) : timbre stable et fidèle, japonais
   propre — mais pas d'émotion par réplique.
3. **Améliorer CosyVoice 3** : prompts plus longs/propres, transcript du
   prompt (zero_shot au lieu d'instruct2 sur les lignes clés), retouches des
   instructions.
4. Hybride : VOICEVOX pour la masse, le meilleur moteur pour les ~40
   personnages principaux.

La décision reste à l'oreille : refaire un A/B avec S2-Pro/GPT-SoVITS sur les
mêmes 40 lignes avant d'intégrer quoi que ce soit.
