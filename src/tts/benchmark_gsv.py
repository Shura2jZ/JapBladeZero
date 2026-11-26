"""Benchmark runner for GPT-SoVITS (api_v2 HTTP server, port 9891).

    python src/tts/benchmark_gsv.py [--limit N]

The prompt is a single line (3-10 s) of the SAME character, chosen by
ref_select.py on the measured vocal profile. The prompt transcript is that
line's Chinese text.
"""
import argparse, csv, json, os, sys, urllib.request, urllib.error

BASE = r'C:/Users/marou/.deepai-code/scratch/2026-11-16-wsh-claude-fable-cd7797cc'
os.chdir(BASE)

GSV_URL = os.environ.get('GSV_URL', 'http://127.0.0.1:9891/tts')
REFS = os.path.join(BASE, 'out', 'benchmark', 'refs')

bench = json.load(open(os.path.join(BASE, 'data', 'benchmark_set.json'), encoding='utf-8'))
choice = json.load(open(os.path.join(BASE, 'data', 'benchmark_refchoice.json'), encoding='utf-8'))
rows = {r['event_name']: r for r in csv.DictReader(
    open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8'))}

ap = argparse.ArgumentParser()
ap.add_argument('--limit', type=int, default=0)
args = ap.parse_args()

outdir = os.path.join(BASE, 'out', 'benchmark', 'gsv')
os.makedirs(outdir, exist_ok=True)

ok = fail = 0
items = list(bench.items())
if args.limit:
    items = items[:args.limit]
for event, meta in items:
    outp = os.path.join(outdir, event + '.wav')
    if os.path.exists(outp) and os.path.getsize(outp) > 1000:
        ok += 1
        continue
    sel = choice.get(event)
    r = rows.get(event)
    if not sel or not r:
        print('ERR', event, 'pas de reference', flush=True)
        fail += 1
        continue
    ref_event = sel['ref_event']
    ref_path = os.path.join(REFS, ref_event + '.cn.wav').replace('/', '\\')
    if not os.path.exists(ref_path):
        print('ERR', event, 'audio de reference absent', flush=True)
        fail += 1
        continue
    payload = {
        'text': (r.get('japanese_text_tts') or r['japanese_text']).strip(),
        'text_lang': 'ja',
        'ref_audio_path': ref_path,
        'prompt_text': (rows[ref_event].get('chinese_text') or '').strip(),
        'prompt_lang': 'zh',
        'speed_factor': 1.0,
        'media_type': 'wav',
        'streaming_mode': False,
        'text_split_method': 'cut0',
    }
    try:
        req = urllib.request.Request(GSV_URL, data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=600)
        data = resp.read()
        if data[:4] != b'RIFF' or len(data) < 1000:
            raise RuntimeError(f'reponse invalide: {data[:80]}')
        with open(outp, 'wb') as f:
            f.write(data)
        ok += 1
        print('ok', event, f'(ref={ref_event})', flush=True)
    except urllib.error.HTTPError as e:
        print('ERR', event, e.read().decode('utf-8', 'replace')[:120], flush=True)
        fail += 1
    except Exception as e:
        print('ERR', event, repr(e)[:140], flush=True)
        fail += 1
print(f'gpt-sovits: {ok} prises, {fail} echecs -> {outdir}')
