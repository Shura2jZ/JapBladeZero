"""Replaces the machine-translated Japanese text with the official one.

The game ships a compiled Japanese localization (``Localization/Game/ja/Game.locres``)
holding every dialogue line of the game. It is the reference text: the machine
translation we made from the Chinese script was both unnecessary and wrong
(character names were mangled: 左殇 became 左利き "left-handed").

The keys of the localization are the ``Dlg_*`` keys already present in the
manifest, so the join is direct.

Usage:
    python src/translate/official_text.py --locres <ja_Game.json> [--dry-run]
"""
import argparse, csv, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE

MANIFEST = os.path.join(BASE, 'data', 'manifest_jp.csv')

# the game marks a part of the line with <Bold> ... </> ; the tag must not be
# spoken, and a line break inside a sentence must not split it
BOLD = re.compile(r'<Bold>|</>')


def clean(text):
    """The text as it should be spoken: no markup, no line break."""
    text = BOLD.sub('', text)
    text = text.replace('\r\n', '').replace('\n', '').replace('\r', '')
    return text.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--locres', required=True, help='json file written by tools/csharp/locres')
    ap.add_argument('--manifest', default=MANIFEST)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    loc = json.load(open(a.locres, encoding='utf-8'))
    ja = {k.split(':', 1)[1]: v for k, v in loc.items() if ':Dlg_' in k}

    rows = list(csv.DictReader(open(a.manifest, encoding='utf-8')))
    fields = list(rows[0].keys())

    changed = 0
    missing = []
    empty = []
    for r in rows:
        official = ja.get(r['dialogue_key'])
        if official is None:
            missing.append(r['event_name'])
            continue
        spoken = clean(official)
        if not spoken:
            empty.append(r['event_name'])
            continue
        if r['japanese_text_tts'] != spoken:
            changed += 1
        r['japanese_text'] = official
        r['japanese_text_tts'] = spoken

    print(f'lignes du manifeste : {len(rows)}')
    print(f'  texte officiel trouvé : {len(rows) - len(missing) - len(empty)}')
    print(f'  clés absentes         : {len(missing)}')
    print(f'  texte vide            : {len(empty)}')
    print(f'  texte modifié         : {changed}')
    for k in missing[:10]:
        print(f'    absent : {k}')
    for k in empty[:10]:
        print(f'    vide   : {k}')

    if a.dry_run:
        return
    with open(a.manifest, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f'-> {a.manifest}')


if __name__ == '__main__':
    main()
