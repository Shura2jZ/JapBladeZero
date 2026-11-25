"""Benchmark runner for Fish Audio S2-Pro — must run inside the venv-fs.

    E:/TTS_Lab/venv-fs/Scripts/python.exe <repo>/src/tts/benchmark_s2pro.py [--limit N]
"""
import csv, json, os, sys, wave

BASE = r'C:/Users/marou/.deepai-code/scratch/2026-11-16-wsh-claude-fable-cd7797cc'
sys.path.insert(0, os.path.join(BASE, 'src'))
os.chdir(BASE)

from tts.engines.s2pro import Engine

bench = json.load(open(os.path.join(BASE, 'data', 'benchmark_set.json'), encoding='utf-8'))
refs_manifest = json.load(open(os.path.join(BASE, 'data', 'benchmark_refs.json'), encoding='utf-8'))
rows = {r['event_name']: r for r in csv.DictReader(
    open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8'))}

limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else 0

eng = Engine()
outdir = os.path.join(BASE, 'out', 'benchmark', 's2pro')
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
        print('ERR', event, 'ref manquante', flush=True)
        fail += 1
        continue
    # transcript chinois des morceaux concatennes dans la reference
    pieces = refs_manifest.get(event, [event])
    zh_rows = {rr['event_name']: rr for rr in csv.DictReader(
        open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8'))}
    transcript = ''.join((zh_rows.get(p, {}).get('chinese_text') or '').strip()
                         for p in pieces)
    try:
        res = eng.synthesize(text, {}, reference_wav=ref, transcript=transcript)
        if res is None:
            print('ERR', event, 'vide', flush=True)
            fail += 1
            continue
        wav, sr = res
        with open(os.path.join(outdir, event + '.wav'), 'wb') as f:
            f.write(wav)
        ok += 1
        print('ok', event, flush=True)
    except Exception as e:
        print('ERR', event, repr(e)[:160], flush=True)
        fail += 1
print(f's2pro: {ok} prises, {fail} echecs -> {outdir}')
