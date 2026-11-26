"""CosyVoice 3 takes for the Main_1 dedicated benchmark (run inside venv-cv3).

    E:/TTS_Lab/venv-cv3/Scripts/python.exe <repo>/src/tts/bench_main1_cv3.py
"""
import csv, json, os, sys, wave

BASE = r'C:/Users/marou/.deepai-code/scratch/2026-11-16-wsh-claude-fable-cd7797cc'
sys.path.insert(0, os.path.join(BASE, 'src'))
sys.path.insert(0, os.path.join(BASE, 'src', 'tts'))
os.chdir(BASE)

from tts.engines.cosyvoice3 import Engine

LINES = json.load(open(os.path.join(BASE, 'data', 'bench_main1.json'), encoding='utf-8'))
refs_manifest = json.load(open(os.path.join(BASE, 'data', 'bench_main1_refs.json'), encoding='utf-8'))
rows = {r['event_name']: r for r in csv.DictReader(
    open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8'))}

eng = Engine()
outdir = os.path.join(BASE, 'out', 'benchmark', 'cosyvoice3')
refs = os.path.join(BASE, 'out', 'benchmark', 'refs')
ok = fail = 0
for ev in LINES:
    p = os.path.join(outdir, ev + '.wav')
    if os.path.exists(p) and os.path.getsize(p) > 1000:
        ok += 1; continue
    text = (rows[ev].get('japanese_text_tts') or rows[ev]['japanese_text']).strip()
    ref = os.path.join(refs, ev + '.cn.multi.wav')
    if not os.path.exists(ref):
        print('ERR', ev, 'ref multi absente', flush=True); fail += 1; continue
    pieces = refs_manifest[ev]['multi']
    transcript = ''.join((rows.get(pe, {}).get('chinese_text') or '').strip() for pe in pieces)
    try:
        res = eng.synthesize(text, {'bucket': 'long'}, reference_wav=ref)
        wav, sr = res
        with wave.open(p, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
            w.writeframes(wav)
        ok += 1
        print('ok', ev, flush=True)
    except Exception as e:
        print('ERR', ev, repr(e)[:140], flush=True); fail += 1
print(f'cosyvoice3: {ok}/{len(LINES)}')
