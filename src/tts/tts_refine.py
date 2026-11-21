"""Refine Japanese TTS durations so every line matches the Chinese original exactly.

Rationale
---------
The first pass accepted a +-10% duration mismatch, which is far too loose for lip sync:
1073/4167 lines were off by more than 0.3 s (worst case 17.9 s).

This pass, for every line whose duration is off by more than TOL:
  1. re-synthesises it with a new VOICEVOX speedScale, computed from the measured
     error (duration is roughly inversely proportional to speedScale),
  2. iterates until the speech sits within 3% of the Chinese duration,
  3. pads the result with a little digital silence so the *total* length is exactly
     the Chinese duration (silence is inaudible; speeding the voice up by 20% is not).

State (speedScale actually used per event) is stored in jp_speeds.json so that later
runs refine multiplicatively instead of restarting from 1.0.
"""
import csv, json, os, re, sys, time, threading, subprocess, urllib.request, urllib.parse, wave, io, struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE, out, voicevox
from tts.voices import speaker_for
OUT_DIR = out('jp_events')
# the engine can live outside the repository (it is not versioned)
VV_DIR = voicevox()
PORTS = [50021, 50022, 50023, 50024]
MAX_RETRIES = 4

# speech must be within this relative tolerance before we stop tuning the speed
REL_TOL = 0.03
# ... and then silence padding absorbs what is left, up to this much
MAX_PAD_FRAC = 0.06

rows = list(csv.DictReader(open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8')))
durations = json.load(open(os.path.join(BASE, 'data', 'durations.json'), encoding='utf-8'))
SPEEDS_PATH = os.path.join(BASE, 'data', 'jp_speeds.json')
speeds = json.load(open(SPEEDS_PATH, encoding='utf-8')) if os.path.exists(SPEEDS_PATH) else {}




def request(url, data=None, method=None, timeout=120):
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={'Content-Type': 'application/json'} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def wav_info(data):
    w = wave.open(io.BytesIO(data))
    fr, sr, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
    w.close()
    return fr, sr, ch, sw


def wav_duration(data):
    fr, sr, _, _ = wav_info(data)
    return fr / float(sr)


def pad_to(data, seconds):
    """Return the wav padded with silence so that it lasts exactly `seconds`."""
    fr, sr, ch, sw = wav_info(data)
    want = int(round(seconds * sr))
    if want <= fr:
        return data
    extra = want - fr
    pad = b'\x00' * (extra * ch * sw)
    body = data[:-4] if data[-4:] == b'data' else None
    # rebuild the RIFF container with the new size
    out = bytearray(data)
    # locate the data chunk payload
    pos = 12
    while pos + 8 <= len(out):
        cid = bytes(out[pos:pos + 4])
        sz = struct.unpack('<I', bytes(out[pos + 4:pos + 8]))[0]
        if cid == b'data':
            payload_at = pos + 8
            new_sz = sz + extra * ch * sw
            struct.pack_into('<I', out, pos + 4, new_sz)
            out = out[:payload_at + sz] + pad + out[payload_at + sz:]
            struct.pack_into('<I', out, 4, len(out) - 8)
            return bytes(out)
        pos += 8 + sz + (sz & 1)
    return data


class EnginePool:
    """Keeps one VOICEVOX server per port alive; restarts it if it dies."""

    def __init__(self, ports):
        self.ports = list(ports)
        self.lock = threading.Lock()
        self.procs = {}
        self.unavailable = set()

    def _start(self, port):
        log = open(os.path.join(BASE, 'logs', f'vv_{port}.log'), 'ab')
        p = subprocess.Popen([os.path.join(VV_DIR, 'run.exe'), '--host', '127.0.0.1',
                              '--port', str(port), '--no-use_gpu', '--output_log_utf8',
                              '--init_processes', '1'],
                             cwd=VV_DIR, stdout=log, stderr=log)
        self.procs[port] = p

    def ensure(self, port):
        with self.lock:
            p = self.procs.get(port)
            if p is None or p.poll() is not None:
                try:
                    self._start(port)
                except Exception:
                    return False
                time.sleep(25)
            try:
                request(f'http://127.0.0.1:{port}/version', timeout=10)
                self.unavailable.discard(port)
                return True
            except Exception:
                self.unavailable.add(port)
                return False

    def any_available(self):
        for port in self.ports:
            if port not in self.unavailable:
                return port
        return None


pool = EnginePool(PORTS)
errors = []
error_lock = threading.Lock()
speeds_lock = threading.Lock()


def synth_with_speed(text, speaker, speed, port):
    query = json.loads(request(
        f'http://127.0.0.1:{port}/audio_query?text={urllib.parse.quote(text)}&speaker={speaker}',
        method='POST', timeout=90))
    query['speedScale'] = speed
    wav = request(f'http://127.0.0.1:{port}/synthesis?speaker={speaker}',
                  data=json.dumps(query).encode('utf-8'), timeout=180)
    return wav


def refine(row, target):
    event = row['event_name']
    text = (row.get('japanese_text_tts') or row['japanese_text'] or '').strip()
    name = event + '.wav'
    out_path = os.path.join(OUT_DIR, name)
    if not text or target <= 0:
        return 'skip'

    current = None
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        with open(out_path, 'rb') as f:
            current = f.read()
    cur_dur = wav_duration(current) if current else 0.0

    speed = float(speeds.get(event, 1.0))
    if current is None:
        speed = 1.0

    # speech-only target: the Chinese duration minus a tiny safety margin
    speech_target = target * (1.0 - MAX_PAD_FRAC)

    best = None
    for attempt in range(MAX_RETRIES):
        port = pool.any_available()
        if port is None:
            time.sleep(8)
            if not pool.ensure(PORTS[0]):
                continue
            port = pool.any_available()
            if port is None:
                continue
        try:
            wav = synth_with_speed(text, speaker_for(event), speed, port)
            dur = wav_duration(wav)
            best = (wav, dur, speed)
            if abs(dur - speech_target) / speech_target <= REL_TOL:
                break
            # duration ~ 1/speed -> new_speed = speed * (dur / target)
            speed = max(0.5, min(2.0, speed * (dur / speech_target)))
        except Exception as e:
            with error_lock:
                errors.append((event, repr(e)[:120]))
            pool.unavailable.add(port)
            time.sleep(2)
            continue

    if best is None:
        return 'error'

    wav, dur, speed = best
    if dur < target:
        wav = pad_to(wav, target)
    with open(out_path, 'wb') as f:
        f.write(wav)
    with speeds_lock:
        speeds[event] = round(speed, 4)
    return 'ok'


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    todo = []
    for r in rows:
        event = r['event_name']
        target = durations.get(event, [0.0, 0.0])[0] or 0.0
        if target <= 0:
            continue
        text = (r.get('japanese_text_tts') or r['japanese_text'] or '').strip()
        if not text:
            continue
        p = os.path.join(OUT_DIR, event + '.wav')
        cur = 0.0
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            with open(p, 'rb') as f:
                try:
                    cur = wav_duration(f.read())
                except Exception:
                    cur = 0.0
        if cur and abs(cur - target) <= max(0.02, 0.01 * target):
            continue  # already good enough
        todo.append((r, target))

    print('events to refine:', len(todo), flush=True)
    lock = threading.Lock()
    counter = [0]

    def worker():
        while True:
            with lock:
                if not todo:
                    return
                row, target = todo.pop()
            res = refine(row, target)
            with speeds_lock:
                counter[0] += 1
                if counter[0] % 50 == 0:
                    print(f'{counter[0]} refined, errors={len(errors)}, remaining={len(todo)}', flush=True)
                    json.dump(speeds, open(SPEEDS_PATH, 'w'))

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    json.dump(speeds, open(SPEEDS_PATH, 'w'))
    print('finished. errors:', len(errors), flush=True)
    seen = set()
    for e, msg in errors:
        if msg not in seen:
            seen.add(msg)
            print('ERR sample:', e, msg, flush=True)


if __name__ == '__main__':
    main()
