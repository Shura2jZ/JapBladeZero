"""Benchmark runner for CosyVoice 3 — must run inside the cv3 venv (3.12).

    E:/TTS_Lab/venv-cv3/Scripts/python.exe <repo>/src/tts/benchmark_cosyvoice.py
"""
import csv, json, os, sys, wave, io

BASE = r'C:/Users/marou/.deepai-code/scratch/2026-11-16-wsh-claude-fable-cd7797cc'
sys.path.insert(0, os.path.join(BASE, 'src'))
sys.path.insert(0, os.path.join(BASE, 'src', 'tts'))
os.chdir(BASE)

from tts.engines.cosyvoice3 import Engine

bench = json.load(open(os.path.join(BASE, 'data', 'benchmark_set.json'), encoding='utf-8'))
rows = {r['event_name']: r for r in csv.DictReader(
    open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8'))}

limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else 0

eng = Engine()
if not eng.available():
    raise SystemExit('CUDA indisponible')

outdir = os.path.join(BASE, 'out', 'benchmark', 'cosyvoice3')
os.makedirs(outdir, exist_ok=True)
refs = os.path.join(BASE, 'out', 'benchmark', 'refs')

ok = fail = 0
items = list(bench.items())
if limit:
    items = items[:limit]
for event, meta in items:
    r = rows.get(event)
    if not r:
        continue
    text = (r.get('japanese_text_tts') or r.get('japanese_text') or '').strip()
    ref = os.path.join(refs, event + '.cn.multi.wav')
    if not os.path.exists(ref):
        ref = os.path.join(refs, event + '.cn.wav')
    if not os.path.exists(ref):
        print('ERR', event, 'ref manquante')
        fail += 1
        continue
    try:
        res = eng.synthesize(text, {'bucket': meta.get('bucket')}, reference_wav=ref)
        if res is None:
            print('ERR', event, 'vide')
            fail += 1
            continue
        wav, sr = res
        with open(os.path.join(outdir, event + '.wav'), 'wb') as f:
            f.write(wav)
        ok += 1
        print('ok', event, flush=True)
    except Exception as e:
        print('ERR', event, repr(e)[:150], flush=True)
        fail += 1
print(f'cosyvoice3: {ok} prises, {fail} echecs -> {outdir}')
