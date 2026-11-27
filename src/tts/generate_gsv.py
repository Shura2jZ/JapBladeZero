"""Generates the Japanese dub with per-character fine-tuned GPT-SoVITS.

For each line of a character with fine-tuned SoVITS weights:
  1. load weights in the running api_v2 server (127.0.0.1:9891)
  2. choose a Chinese reference line of the SAME character whose measured
     profile (f0, duration) matches the target line (emotion proxy)
  3. POST /tts (ja text, zh reference) -> WAV
  4. QC: f0 in range + duration sane; retry with next-best reference
  5. fallback: VOICEVOX with the F0-matched voice

    python src/tts/generate_gsv.py [--limit N] [--chars Re,Re2]
"""
import csv, json, os, sys, time, struct, wave, urllib.request, urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'src'))
sys.path.insert(0, os.path.join(REPO, 'src', 'audio'))
API = 'http://127.0.0.1:9891'

speakers = json.load(open(REPO + r'/data/event_speaker.json', encoding='utf-8'))
durations = json.load(open(REPO + r'/data/durations.json', encoding='utf-8'))
profiles = json.load(open(REPO + r'/data/cn_voice_profiles.json', encoding='utf-8'))
weights = json.load(open(REPO + r'/data/gsv_weights.json', encoding='utf-8'))
rows = {r['event_name']: r for r in csv.DictReader(
    open(REPO + r'/data/manifest_jp.csv', encoding='utf-8'))}
DATASET = r'E:/TTS_Lab/GSV_dataset'

from tts.engines.voicevox import Engine
import shutil


def f0_robust(p):
    with wave.open(p) as w:
        r, n = w.getframerate(), w.getnframes()
        v = [x / 32768 for x in struct.unpack(f'<{n}h', w.readframes(n))]
    if n < 8000:
        return 0, n / r
    W = 4000
    best_i, be = 0, -1
    for i in range(0, max(1, len(v) - W), 2000):
        e = sum(x * x for x in v[i:i + W])
        if e > be:
            be, best_i = e, i
    seg = v[best_i:best_i + min(8000, len(v) - best_i - 1)]
    best, bl = None, -1e9
    for lag in range(40, min(int(r / 60), len(seg) - 1)):
        s = sum(seg[i] * seg[i + lag] for i in range(0, len(seg) - lag - 1, 2))
        if s > bl:
            bl, best = s, lag
    return r / best, n / r


def read_wav_bytes(p):
    with wave.open(p) as w:
        return w.getframerate(), w.getnframes()


def set_weights(char, path):
    try:
        urllib.request.urlopen(
            f'{API}/set_sovits_weights?weights_path={urllib.parse.quote(path)}', timeout=120)
        time.sleep(2)
        return True
    except Exception as e:
        print('set_weights ERR', char, repr(e)[:80], flush=True)
        return False


def tts(ev, ref_path, prompt_text):
    payload = {'text': (rows[ev].get('japanese_text_tts') or rows[ev].get('japanese_text') or '').strip(),
               'text_lang': 'ja',
               'ref_audio_path': ref_path,
               'prompt_text': prompt_text,
               'prompt_lang': 'zh', 'speed_factor': 1.0, 'media_type': 'wav',
               'streaming_mode': False, 'text_split_method': 'cut0'}
    req = urllib.request.Request(f'{API}/tts', data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    data = urllib.request.urlopen(req, timeout=300).read()
    if data[:4] != b'RIFF':
        raise RuntimeError(data[:80])
    return data


def choose_refs(char, ev, k=4):
    """Chinese reference lines of the same character, ranked by profile match."""
    evs = [e for e, sp in speakers.items() if sp == char]
    refdir = os.path.join(DATASET, char + '_wav')
    dt = (durations.get(ev, [0, 0]) or [0, 0])[0]
    pf = profiles['events'].get(ev, {})
    f0t = pf.get('f0_median') or 100
    scored = []
    for e in evs:
        if e == ev:
            continue
        p = os.path.join(refdir, e + '.wav')
        if not os.path.exists(p):
            continue
        try:
            r, nf = read_wav_bytes(p)
            d = nf / r
        except Exception:
            continue
        if not (3.0 <= d <= 10.0):
            continue
        pf2 = profiles['events'].get(e, {})
        f02 = pf2.get('f0_median') or 100
        # duration distance 3:1 + f0 distance (emotion proxy)
        scored.append((abs(d - dt) * 3 + abs(f02 - f0t), e))
    scored.sort()
    return [os.path.join(refdir, e + '.wav').replace('/', '\\')
            for _, e in scored[:k]]


def main():
    import urllib.parse
    limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else 0
    chars_filter = sys.argv[sys.argv.index('--chars') + 1].split(',') if '--chars' in sys.argv else None

    vv = Engine()
    outd = REPO + r'/out/jp_events_gsv'
    os.makedirs(outd, exist_ok=True)

    todo = []
    for r in csv.DictReader(open(REPO + r'/data/manifest_jp.csv', encoding='utf-8')):
        ev = r['event_name']
        ch = speakers.get(ev)
        if not ch or ch not in weights or not (r.get('japanese_text_tts') or r.get('japanese_text') or '').strip():
            continue
        if chars_filter and ch not in chars_filter:
            continue
        todo.append(ev)
    print(f'{len(todo)} lignes couvertes par GSV fine-tune ({len(weights)} personnages)', flush=True)
    if limit:
        todo = todo[:limit]

    current = None
    ok = fail = fb = 0
    for n, ev in enumerate(todo, 1):
        ch = speakers[ev]
        outp = os.path.join(outd, ev + '.wav')
        if os.path.exists(outp) and os.path.getsize(outp) > 1000:
            continue
        if current != ch:
            set_weights(ch, weights[ch])
            current = ch
        dzh = (durations.get(ev, [0, 0]) or [0, 0])[0]
        done = False
        for i, ref in enumerate(choose_refs(ch, ev)):
            prompt_text = (rows[os.path.splitext(os.path.basename(ref))[0]]
                           .get('chinese_text') or '').strip()
            try:
                data = tts(ev, ref, prompt_text)
                with open(outp, 'wb') as f:
                    f.write(data)
                f0, d = f0_robust(outp)
                f0c = (profiles.get('characters', {}).get(ch, {}) or {}).get('f0_median') or 100
                lo, hi = max(35, 0.5 * f0c), 1.8 * f0c
                if lo <= f0 <= hi and d <= max(3.5, dzh * 1.9) and d > 0.5:
                    ok += 1
                    done = True
                    break
                os.remove(outp)
            except Exception as e:
                print('ERR', ev, repr(e)[:90], flush=True)
        if not done:
            # fallback VOICEVOX (F0-matched voice, from event_speaker mapping)
            try:
                from tts.voices import speaker_for
                spid = speaker_for(ev)
                text = (rows[ev].get('japanese_text_tts') or rows[ev].get('japanese_text')).strip()
                wav, sr = vv.synthesize(text, {'intonation': 1.1}, speaker=spid)
                with wave.open(outp, 'wb') as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
                    w.writeframes(wav)
                fb += 1
                print('FALLBACK', ev, flush=True)
            except Exception as e:
                fail += 1
                print('FAIL TOTAL', ev, repr(e)[:80], flush=True)
        if n % 25 == 0:
            print(f'  ... {n}/{len(todo)} (ok={ok} fallback={fb} fail={fail})', flush=True)
    print(f'termine: ok={ok} fallback={fb} fail={fail}', flush=True)


if __name__ == '__main__':
    main()
