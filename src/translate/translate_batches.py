import csv, json, os, re, sys, glob
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANIFEST = os.path.join(BASE, 'data', 'manifest_jp.csv')
MODEL_DIR = os.path.join(BASE, 'models', 'opus-mt-zh-ja')
OUT = os.path.join(BASE, 'data', 'batches', 'out_mt.json')

tok = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_DIR)
model.eval()

rows = list(csv.DictReader(open(MANIFEST, encoding='utf-8')))
done = {r['event_name']: r['japanese_text'] for r in rows if r['japanese_text'].strip()}

# translate unique source strings once
uniq = []
seen = set()
for r in rows:
    t = r['chinese_text'].strip()
    if t and t not in seen:
        seen.add(t)
        uniq.append(t)

existing = {}
if os.path.exists(OUT):
    existing = json.load(open(OUT, encoding='utf-8'))
need = [t for t in uniq if t not in existing]
print('unique', len(uniq), 'already', len(uniq) - len(need), 'to do', len(need), flush=True)

B = 32
for i in range(0, len(need), B):
    chunk = need[i:i + B]
    b = tok(chunk, return_tensors='pt', padding=True, truncation=True, max_length=256)
    with torch.inference_mode():
        gen = model.generate(**b, max_new_tokens=180, num_beams=4, early_stopping=True)
    for src, out in zip(chunk, tok.batch_decode(gen, skip_special_tokens=True)):
        existing[src] = out.strip()
    if (i // B) % 5 == 0:
        print(i, '/', len(need), flush=True)
        json.dump(existing, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(existing, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('done', len(existing))
