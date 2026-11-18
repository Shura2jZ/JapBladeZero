"""Build the translation work list.

Reads the manifest extracted from the game (the raw `manifest.csv`), merges it with the
translations already done (`data/manifest_jp.csv`) and writes the Chinese lines that
still need a translation into `data/batches/in_XXX.json`, 150 lines per file.

Usage:
    python src/translate/prep.py --source C:/work/pbz_audio/manifest.csv
"""
import argparse, csv, json, os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANIFEST = os.path.join(BASE, 'data', 'manifest_jp.csv')
BATCHES = os.path.join(BASE, 'data', 'batches')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True,
                    help='the manifest.csv extracted from the game (raw dump)')
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.source, encoding='utf-8-sig')))
    old = {}
    if os.path.exists(MANIFEST):
        old = {r['event_name']: r['japanese_text']
               for r in csv.DictReader(open(MANIFEST, encoding='utf-8'))}
    for r in rows:
        r['japanese_text'] = old.get(r['event_name'], '')

    os.makedirs(BATCHES, exist_ok=True)
    with open(MANIFEST, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    todo = [r for r in rows if not r['japanese_text'] and r['chinese_text'].strip()]
    for i in range(0, len(todo), 150):
        path = os.path.join(BATCHES, f'in_{i // 150:03d}.json')
        json.dump({r['event_name']: r['chinese_text'] for r in todo[i:i + 150]},
                  open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(len(rows), 'rows', len(todo), 'to translate')


if __name__ == '__main__':
    main()
