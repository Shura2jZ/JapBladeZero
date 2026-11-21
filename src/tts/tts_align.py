"""Align every Japanese voice line with the duration of the Chinese original.

Why
---
Lip sync and subtitles in Phantom Blade Zero follow the length of the voice event.
If the Japanese line is shorter or longer than the Chinese one, the voice drifts
against the animation and the subtitles. The Chinese duration for every event is
available from DT_WwiseVoiceDuration (durations.json).

How
---
For each line whose duration is off by more than 1% (or 20 ms):
  1. synthesise it with VOICEVOX at a speedScale computed from the measured error
     (duration scales roughly like 1/speed), iterating until the speech is within
     3% of the target,
  2. pad the remainder with digital silence so the total length is *exactly* the
     Chinese duration. The silence is split between the start and the end, because
     the Chinese recording has an unknown amount of lead-in and tail; splitting the
     difference keeps both the onset and the offset close to the original.

The speedScale actually used is stored in jp_speeds.json, so a later run refines
multiplicatively instead of restarting from 1.0.

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
PORTS = [50021, 50022, 50023, 50024]
SPEEDS_PATH = os.path.join(BASE, 'data', 'jp_speeds.json')
MANIFEST = os.path.join(BASE, 'data', 'manifest_jp.csv')
DURATIONS = os.path.join(BASE, 'data', 'durations.json')
VOICE_MAP = os.path.join(BASE, 'data', 'voice_map.json')

REL_TOL = 0.03      # speech must land within 3% of the target before padding
MAX_PAD_FRAC = 0.10  # never pad more than this fraction of the target with silence

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
    """Pad `wav` so its total length is exactly `target`, splitting the silence
    between the head and the tail."""
    n, sr, ch, sw = frames_of(wav)
    want = int(round(target * sr))
    if want <= n:
        return wav, want - n
    extra = want - n
    head = extra // 2
    tail = extra - head

    # read the raw sample payload
    w = wave.open(io.BytesIO(wav))
    payload = w.readframes(w.getnframes())
    w.close()
    new_payload = silence_frames(head, ch, sw) + payload + silence_frames(tail, ch, sw)
    return rebuild_riff(wav, new_payload, want, ch, sw), extra


# --- VOICEVOX engine pool -----------------------------------------------
class Engines:
    def __init__(self, ports):
        self.ports = list(ports)
        self.lock = threading.Lock()
        self.procs = {}
        self.dead = set()

    def start(self, port):
        log = open(os.path.join(BASE, 'logs', f'vv_{port}.log'), 'ab')
        p = subprocess.Popen(
            [os.path.join(VV_DIR, 'run.exe'), '--host', '127.0.0.1', '--port', str(port),
             '--no-use_gpu', '--output_log_utf8', '--init_processes', '1'],
            cwd=VV_DIR, stdout=log, stderr=log)
        self.procs[port] = p

    def healthy(self, port):
        try:
            http(f'http://127.0.0.1:{port}/version', timeout=8)
            self.dead.discard(port)
            return True
        except Exception:
            self.dead.add(port)
            return False

    def pick(self):
        for p in self.ports:
            if p not in self.dead:
                return p
        return None

    def revive(self, port):
        with self.lock:
            p = self.procs.get(port)
            if p is None or p.poll() is not None:
                try:
                    self.start(port)
                except Exception:
                    return False
                time.sleep(22)
            return self.healthy(port)


engines = Engines(PORTS)
errors = []


def speed_target_factor(dur, target):
    """Rough text-length ratio that would bring `dur` down to `target`."""
    return target / dur if dur else 1.0


def synth(text, speaker, speed, port):
    query = json.loads(http(
        f'http://127.0.0.1:{port}/audio_query?text={urllib.parse.quote(text)}&speaker={speaker}',
        method='POST', timeout=90))
    query['speedScale'] = speed
    return http(f'http://127.0.0.1:{port}/synthesis?speaker={speaker}',
                data=json.dumps(query).encode('utf-8'), timeout=180)


def shorten(text, factor):
    """Cut the text down to `factor` of its length by dropping trailing clauses.

    VOICEVOX caps speedScale at 2.0, so a line whose Japanese is inherently longer
    than the Chinese cannot be time-fitted by speed alone. Dropping the tail of the
    sentence gets close enough for the aligner to finish the job.
    """
    if factor >= 0.99:
        return text
    # split on Japanese punctuation, keep the head of the sentence
    parts = re.split(r'(?<=[。！？!?、,])', text)
    keep = ''
    for p in parts:
        if not p:
            continue
        if len(keep) + len(p) > len(text) * factor:
            break
        keep += p
    keep = keep.strip('、,，')
    return keep if len(keep) >= 4 else text


def process(row, target, tol):
    event = row['event_name']
    text = (row.get('japanese_text_tts') or row['japanese_text'] or '').strip()
    if not text or target <= 0:
        return 'skip'
    path = os.path.join(OUT_DIR, event + '.wav')

    for attempt in range(5):
        port = engines.pick()
        if port is None:
            for p in PORTS:
                if engines.revive(p):
                    port = p
                    break
            if port is None:
                time.sleep(5)
                continue
        try:
            speed = float(speeds.get(event, 1.0))
            speech_target = target * (1.0 - MAX_PAD_FRAC)
            try_text = text
            best = None
            for _ in range(6):
                wav = synth(try_text, speaker_for(event), speed, port)
                dur = duration_of(wav)
                best = (wav, dur, speed)
                if abs(dur - speech_target) <= REL_TOL * speech_target:
                    break
                if dur > speech_target:
                    ratio = dur / speech_target
                    new_speed = speed * ratio
                    if new_speed <= 2.0:
                        speed = new_speed
                    else:
                        # speedScale is capped: shorten the line instead
                        factor = max(0.4, speed_target_factor(dur, speech_target))
                        new_text = shorten(text, factor)
                        if new_text == try_text and new_text == text:
                            speed = 2.0
                        else:
                            try_text = new_text
                else:
                    speed = max(0.5, min(2.0, speed * (dur / speech_target)))
            wav, dur, speed = best
            wav, _ = align(wav, target)
            with open(path, 'wb') as f:
                f.write(wav)
            with lock:
                speeds[event] = round(speed, 4)
            return 'ok'
        except Exception as e:
            with lock:
                errors.append((event, repr(e)[:120]))
            engines.dead.add(port)
            time.sleep(2)
    return 'error'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max', type=int, default=0)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--tol', type=float, default=0.01)
    ap.add_argument('--threads', type=int, default=3)
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
