"""Merge the per-batch translation outputs into the manifest.

Reads every `data/batches/out_*.json` and fills the `japanese_text` column of
`data/manifest_jp.csv` with the translation of the Chinese line, when there is one.
"""
import csv, glob, json, os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANIFEST = os.path.join(BASE, 'data', 'manifest_jp.csv')
BATCHES = os.path.join(BASE, 'data', 'batches')

rows = list(csv.DictReader(open(MANIFEST, encoding='utf-8')))
tr = {}
for p in glob.glob(os.path.join(BATCHES, 'out_*.json')):
    tr.update(json.load(open(p, encoding='utf-8')))
for r in rows:
    if tr.get(r['event_name'], '').strip():
        r['japanese_text'] = tr[r['event_name']]
with open(MANIFEST, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print('done', sum(1 for r in rows if r['japanese_text']), '/', len(rows))
