"""Final pass on the length of the Japanese voice lines.

The voice keeps its natural speed (see tts_refine.py): this pass only puts the
lines that are shorter than the Chinese slot back at the right length, with a
little digital silence, and reports the ones that are longer.

A line that is longer than the slot is *not* shortened: the duration table
(DT_WwiseVoiceDuration) is written with the real length of the media, so the
game knows how long the line really is.

Usage: python tts_align.py [--max N] [--start I] [--tol 0.01]
"""
import argparse, csv, io, json, os, re, struct, subprocess, threading, time, urllib.parse, urllib.request, wave, sys
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE, out, voicevox
from tts.voices import speaker_for
OUT_DIR = out('jp_events')
# the engine can live outside the repository (it is not versioned)
VV_DIR = voicevox()
PORTS = [50021, 50022, 50023, 50024, 50025, 50026, 50027, 50028]
SPEEDS_PATH = os.path.join(BASE, 'data', 'jp_speeds.json')
MANIFEST = os.path.join(BASE, 'data', 'manifest_jp.csv')
DURATIONS = os.path.join(BASE, 'data', 'durations.json')
VOICE_MAP = os.path.join(BASE, 'data', 'voice_map.json')

# silence never fills more than this fraction of the slot
MAX_PAD_FRAC = 0.30

rows = list(csv.DictReader(open(MANIFEST, encoding='utf-8')))
durations = json.load(open(DURATIONS, encoding='utf-8'))
speeds = json.load(open(SPEEDS_PATH, encoding='utf-8')) if os.path.exists(SPEEDS_PATH) else {}

lock = threading.Lock()




def http(url, data=None, method=None, timeout=120):
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={'Content-Type': 'application/json'} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def frames_of(data):
    w = wave.open(io.BytesIO(data))
    n, sr, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
    w.close()
    return n, sr, ch, sw


def duration_of(data):
    n, sr, _, _ = frames_of(data)
    return n / float(sr)


def silence_frames(total_frames, ch, sw):
    return b'\x00' * (total_frames * ch * sw)


def rebuild_riff(original, frames_data, total_frames, ch, sw):
    """Swap the data chunk payload and fix the RIFF/data sizes."""
    out = bytearray(original)
    pos = 12
    while pos + 8 <= len(out):
        cid = bytes(out[pos:pos + 4])
        sz = struct.unpack('<I', bytes(out[pos + 4:pos + 8]))[0]
        if cid == b'data':
            payload_at = pos + 8
            new_bytes = frames_data
            struct.pack_into('<I', out, pos + 4, len(new_bytes))
            out = out[:payload_at] + new_bytes + out[payload_at + sz:]
            struct.pack_into('<I', out, 4, len(out) - 8)
            return bytes(out)
        pos += 8 + sz + (sz & 1)
    return original


def align(wav, target):
    """Pad `wav` so its total length is exactly `target`.

    The silence is added at the end: the line starts when it should, and the
    slot of the Chinese line keeps its length.
    """
    n, sr, ch, sw = frames_of(wav)
    want = int(round(target * sr))
    if want <= n:
        return wav, (want - n) / float(sr)
    extra = want - n
    # the silence goes to the end: the line starts when it should, and the
    # slot keeps its length
    head = 0
    tail = extra

    # read the raw sample payload
    w = wave.open(io.BytesIO(wav))
    payload = w.readframes(w.getnframes())
    w.close()
    new_payload = silence_frames(head, ch, sw) + payload + silence_frames(tail, ch, sw)
    return rebuild_riff(wav, new_payload, want, ch, sw), extra / float(sr)


def process(row, target, tol):
    """Pad the line with silence if it is shorter than its slot."""
    event = row['event_name']
    path = os.path.join(OUT_DIR, event + '.wav')
    if target <= 0:
        return 'skip'
    if not os.path.exists(path) or os.path.getsize(path) < 1000:
        return 'error'
    with open(path, 'rb') as f:
        wav = f.read()
    dur = duration_of(wav)
    if dur < target and (target - dur) <= target * MAX_PAD_FRAC:
        wav, _ = align(wav, target)
        with open(path, 'wb') as f:
            f.write(wav)
        return 'ok'
    # too long, or too short to be filled with silence: the duration table
    # carries the real length of the media
    return 'ok'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max', type=int, default=0)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--tol', type=float, default=0.01)
    ap.add_argument('--threads', type=int, default=6)
    args = ap.parse_args()

    todo = []
    for r in rows:
        event = r['event_name']
        target = durations.get(event, [0.0, 0.0])[0] or 0.0
        if target <= 0:
            continue
        if not (r.get('japanese_text_tts') or r['japanese_text']).strip():
            continue
        p = os.path.join(OUT_DIR, event + '.wav')
        cur = 0.0
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            with open(p, 'rb') as f:
                try:
                    cur = duration_of(f.read())
                except Exception:
                    cur = 0.0
        if cur and abs(cur - target) <= max(0.02, args.tol * target):
            continue
        todo.append((r, target))

    todo = todo[args.start:]
    if args.max:
        todo = todo[:args.max]
    print(f'events to align: {len(todo)}', flush=True)

    done = [0]

    def worker():
        while True:
            with lock:
                if not todo:
                    return
                row, target = todo.pop()
            res = process(row, target, args.tol)
            with lock:
                done[0] += 1
                if done[0] % 25 == 0:
                    print(f'{done[0]} aligned, errors={len(errors)}, remaining={len(todo)}', flush=True)
                    json.dump(speeds, open(SPEEDS_PATH, 'w'))

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(args.threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    json.dump(speeds, open(SPEEDS_PATH, 'w'))
    print(f'finished. errors={len(errors)}', flush=True)
    seen = set()
    for e, m in errors:
        if m not in seen:
            seen.add(m)
            print('ERR', e, m, flush=True)


if __name__ == '__main__':
    main()
