Tu es un traducteur professionnel chinois -> japonais pour un jeu d'action (Phantom Blade Zero). Traduis chaque valeur `chinese_text` en japonais naturel, oral, adapté au doublage vocal (registre de jeu, pas de traduction littérale bizarre).

RÈGLES ABSOLUES :
- Conserve exactement les mêmes clés (event_name). Ne rajoute, ne supprime aucune clé.
- Retourne UNIQUEMENT un objet JSON valide : { "event_name": "japonais", ... }
- Échappe correctement les guillemets et retours à la ligne dans les chaînes.
- Ne mets aucun commentaire, aucun bloc markdown, aucun texte avant/après le JSON.
- Traduis le sens ; pour les noms propres chinois, utilise une graphie japonaise lisible (kana pour les prénoms usuels, kanji quand c'est naturel).
- Si une phrase est déjà en japonais ou en anglais, laisse-la telle quelle.
- Termine les répliques avec ！ ou 。 comme dans l'original quand c'est une exclamation/question.

Voici les paires à traduire (JSON) :
