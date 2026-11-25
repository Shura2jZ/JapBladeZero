# Décision : Fish Audio S2 rejeté (25/11)

## Ce qui a été testé

| voie | verdict |
|---|---|
| S2-Pro local GPU | ❌ ≥24 Go VRAM requis, RTX 3080 = 10 Go (OOM mesuré, fp16 et bf16) |
| S2-Pro local CPU | ❌ >50 min sans finir une ligne (4B bf16 sur CPU) |
| S2.1-Pro API (tier gratuit) | 1 seule prise avant épuisement du fair-use du compte |
| **S2.1-Pro API (démo/playground + licence)** | ❌ **rejeté à l'oreille par l'utilisateur** — pas impressionnant, refus de payer |

Coût si payant : 15 $/M octets (~8 $ pour le jeu complet) — non retenu sur la
qualité, pas sur le prix. Drama 3 (48 Go VRAM, 50 $/M) : hors de portée.

## Conséquences

- les poids S2-Pro locaux (11 Go) sont supprimés ; le moteur API
  (`src/tts/engines/s2pro.py`, runner `benchmark_s2api.py`) reste versionné
  pour une éventuelle reprise ;
- le pipeline API a été validé jusqu'au bout techniquement (auth, clonage
  inline, réponse audio) — seuls 402 bloquent désormais.

## Ce qui reste du benchmark

- **VOICEVOX** : propre mais plat — 62 % de l'A/B ;
- **CosyVoice 3** : émotion mieux restituée mais timbre synthétique — 38 % ;
- votre remarque pivote : ni l'un ni l'autre ne gagne, chacun perd sur un axe.

## Candidat restant (gratuit, local, Windows)

**GPT-SoVITS** (MIT) : fine-tuning par personnage sur les répliques chinoises
du jeu (centaines de lignes disponibles pour les principaux), timbre stable et
fidèle, japonais propre. Pas d'émotion par balise — mais la **sélection de la
référence par réplique** (choisir parmi les lignes chinoises du personnage
celle dont le profil mesuré — pitch, énergie, débit — correspond à l'émotion
de la ligne japonaise) peut transférer le jeu d'acteur. À tester sur le même
échantillon de 40 lignes avant tout.
