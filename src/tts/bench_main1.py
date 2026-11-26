"""Builds the dedicated Main_1 (Hun) A/B/C benchmark: 16 lines x 3 engines.

The fine-tuned GPT-SoVITS SoVITS weights must be loaded in the api_v2 server
(/set_sovits_weights?weights_path=.../SoVITS_weights_v2/Main_1_e8_s160.pth).
VOICEVOX servers must be running (2 ports suffice).

    python src/tts/bench_main1.py
"""
import csv, json, os, sys, wave, shutil, random, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'audio'))
from paths import BASE

random.seed(20261127)
speakers = json.load(open(os.path.join(BASE, 'data', 'event_speaker.json'), encoding='utf-8'))
durations = json.load(open(os.path.join(BASE, 'data', 'durations.json'), encoding='utf-8'))
profiles = json.load(open(os.path.join(BASE, 'data', 'cn_voice_profiles.json'), encoding='utf-8'))['events']
rows = {r['event_name']: r for r in csv.DictReader(
    open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8'))}

# --- 1. choisir 16 lignes de Main_1 (2-12 s, textes varies) ---------------
cands = [r for r in csv.DictReader(open(os.path.join(BASE, 'data', 'manifest_jp.csv'),
                                        encoding='utf-8'))
         if speakers.get(r['event_name']) == 'Character_Main_1'
         and (r.get('japanese_text_tts') or r.get('japanese_text') or '').strip()
         and 2.0 <= ((durations.get(r['event_name'], [0, 0]) or [0, 0])[0]) <= 12.0]
random.shuffle(cands)
LINES = [r['event_name'] for r in cands[:16]]
json.dump(LINES, open(os.path.join(BASE, 'data', 'bench_main1.json'), 'w'),
          ensure_ascii=False, indent=1)
print('lignes:', len(LINES))

# --- 2. references chinoises --------------------------------------------
REFS = os.path.join(BASE, 'out', 'benchmark', 'refs')
os.makedirs(REFS, exist_ok=True)
import pyvgmstream
from cn_media import chinese_media
from wavio import read_wav


def dump_single(ev):
    p = os.path.join(REFS, ev + '.cn.wav')
    if not os.path.exists(p):
        blob = chinese_media(ev)
        if blob is None:
            return None
        wav = pyvgmstream.decode_buffer_to_wav_bytes(blob, filename_hint=ev + '.wem')
        samples, rate = read_wav(wav)
        with wave.open(p, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
            w.writeframes((samples * 32767).astype('<i2').tobytes())
    return p


# refs mono (3-10 s, hors ligne cible) + multi (~18 s) pour chaque ligne
by_char = {}
for r in csv.DictReader(open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8')):
    if speakers.get(r['event_name']) == 'Character_Main_1':
        by_char.setdefault('Main_1', []).append(r['event_name'])
cands_dur = {ev: (durations.get(ev, [0, 0]) or [0, 0])[0] for ev in by_char['Main_1']}

ref_manifest = {}
for ev in LINES:
    others = [e for e in by_char['Main_1'] if e != ev and 3.0 <= cands_dur.get(e, 0) <= 10.0]
    others.sort(key=lambda e: abs(cands_dur[e] - cands_dur[ev]))
    ref_ev = others[0] if others else None
    ref_manifest[ev] = {'single': ref_ev, 'multi': []}
    pieces, total = [], 0.0
    for e in [ev] + [x for x in by_char['Main_1'] if x != ev]:
        d = cands_dur.get(e, 0)
        if d < 0.8 or d > 8.0:
            continue
        if dump_single(e) is None:
            continue
        pieces.append(e)
        total += d
        if total >= 18.0:
            break
    ref_manifest[ev]['multi'] = pieces
json.dump(ref_manifest, open(os.path.join(BASE, 'data', 'bench_main1_refs.json'), 'w'),
          ensure_ascii=False, indent=1)
print('refs manifestees')

# multi-refs: concatener les morceaux
import numpy as np
for ev, rm in ref_manifest.items():
    p = os.path.join(REFS, ev + '.cn.multi.wav')
    if os.path.exists(p) and os.path.getsize(p) > 1000:
        continue
    parts = []
    for i, e in enumerate(rm['multi']):
        with wave.open(os.path.join(REFS, e + '.cn.wav')) as w:
            rate = w.getframerate()
            v = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float32) / 32768
        parts.append((v, rate))
    rate = parts[0][1]
    gap = np.zeros(int(0.35 * rate))
    out = []
    for i, (v, _) in enumerate(parts):
        if i:
            out.append(gap)
        out.append(v)
    full = np.concatenate(out)[:int(18 * rate)]
    with wave.open(p, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes((full * 32767).astype('<i2').tobytes())
print('refs multi ecrites')

# --- 3. generation des trois moteurs -------------------------------------
OUTD = os.path.join(BASE, 'out', 'benchmark')

# voicevox
from tts.engines.voicevox import Engine
vv = Engine()
ok = fail = 0
os.makedirs(os.path.join(OUTD, 'voicevox'), exist_ok=True)
for ev in LINES:
    p = os.path.join(OUTD, 'voicevox', ev + '.wav')
    if os.path.exists(p) and os.path.getsize(p) > 1000:
        ok += 1; continue
    text = (rows[ev].get('japanese_text_tts') or rows[ev]['japanese_text']).strip()
    try:
        wav, sr = vv.synthesize(text, {'intonation': 1.1}, speaker=101)
        with wave.open(p, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
            w.writeframes(wav)
        ok += 1
    except Exception as e:
        print('VV ERR', ev, repr(e)[:80]); fail += 1
print(f'voicevox: {ok}/{len(LINES)}')

# cosyvoice3 (venv separe) — refs + runner
os.makedirs(os.path.join(OUTD, 'cosyvoice3'), exist_ok=True)

# gpt-sovits (api_v2 sur 9891, poids fine-tunes charges au prealable)
ok = fail = 0
os.makedirs(os.path.join(OUTD, 'gsv'), exist_ok=True)
for ev in LINES:
    p = os.path.join(OUTD, 'gsv', ev + '.wav')
    if os.path.exists(p) and os.path.getsize(p) > 1000:
        ok += 1; continue
    ref_ev = ref_manifest[ev]['single']
    if not ref_ev:
        fail += 1; print('GSV: pas de ref', ev); continue
    payload = {'text': (rows[ev].get('japanese_text_tts') or rows[ev]['japanese_text']).strip(),
               'text_lang': 'ja',
               'ref_audio_path': os.path.join(REFS, ref_ev + '.cn.wav').replace('/', '\\'),
               'prompt_text': (rows[ref_ev].get('chinese_text') or '').strip(),
               'prompt_lang': 'zh', 'speed_factor': 1.0, 'media_type': 'wav',
               'streaming_mode': False, 'text_split_method': 'cut0'}
    try:
        req = urllib.request.Request('http://127.0.0.1:9891/tts',
                                     data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
        data = urllib.request.urlopen(req, timeout=600).read()
        if data[:4] != b'RIFF':
            raise RuntimeError(data[:80])
        with open(p, 'wb') as f:
            f.write(data)
        ok += 1
    except Exception as e:
        print('GSV ERR', ev, repr(e)[:90]); fail += 1
print(f'gpt-sovits: {ok}/{len(LINES)}')
