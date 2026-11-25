"""Benchmark runner for Fish Audio S2.1-Pro via the official API (free tier).

    E:/TTS_Lab/venv-fs/Scripts/python.exe <repo>/src/tts/benchmark_s2api.py [--limit N]

The API key is read from FISH_API_KEY_FILE (never from the chat). The voice
reference is the character's multi-line Chinese audio with its transcript.
"""
import csv, json, os, sys, wave

BASE = r'C:/Users/marou/.deepai-code/scratch/2026-11-16-wsh-claude-fable-cd7797cc'
sys.path.insert(0, os.path.join(BASE, 'src'))
os.chdir(BASE)

from fish_audio_sdk import Session, TTSRequest, ReferenceAudio

MODEL = os.environ.get('FISH_MODEL', 's2.1-pro-free')
KEY_FILE = os.environ.get('FISH_API_KEY_FILE',
                          r'C:/Users/marou/.deepai-code/scratch/fish_api_key.txt')
key = open(KEY_FILE, encoding='utf-8').read().strip().split()[0]

bench = json.load(open(os.path.join(BASE, 'data', 'benchmark_set.json'), encoding='utf-8'))
refs_manifest = json.load(open(os.path.join(BASE, 'data', 'benchmark_refs.json'), encoding='utf-8'))
rows = {r['event_name']: r for r in csv.DictReader(
    open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8'))}
zh_rows = rows

limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else 0
outdir = os.path.join(BASE, 'out', 'benchmark', 's2api')
os.makedirs(outdir, exist_ok=True)
refs = os.path.join(BASE, 'out', 'benchmark', 'refs')
session = Session(key)

ok = fail = 0
items = list(bench.items())
if limit:
    items = items[:limit]
for event, meta in items:
    r = rows.get(event)
    if not r:
        continue
    outp = os.path.join(outdir, event + '.wav')
    if os.path.exists(outp) and os.path.getsize(outp) > 1000:
        ok += 1
        continue
    text = (r.get('japanese_text_tts') or r.get('japanese_text') or '').strip()
    ref_path = os.path.join(refs, event + '.cn.multi.wav')
    if not os.path.exists(ref_path):
        print('ERR', event, 'ref manquante', flush=True)
        fail += 1
        continue
    pieces = refs_manifest.get(event, [event])
    transcript = ''.join((zh_rows.get(p, {}).get('chinese_text') or '').strip()
                         for p in pieces)
    with open(ref_path, 'rb') as f:
        ref_audio = f.read()
    try:
        req = TTSRequest(
            text=text,
            references=[ReferenceAudio(audio=ref_audio, text=transcript)],
            format='wav',
            normalize=True,
            normalize_loudness=True,
            chunk_length=200,
        )
        call = session.tts(req)
        chunks = list(call) if hasattr(call, '__iter__') and not isinstance(call, bytes) else call
        data = b''.join(chunks) if isinstance(chunks, list) else chunks
        if len(data) < 1000:
            raise RuntimeError(f'reponse trop courte: {data[:80]}')
        with open(outp, 'wb') as f:
            f.write(data)
        ok += 1
        print('ok', event, flush=True)
    except Exception as e:
        print('ERR', event, repr(e)[:160], flush=True)
        fail += 1
print(f's2api ({MODEL}): {ok} prises, {fail} echecs -> {outdir}')
