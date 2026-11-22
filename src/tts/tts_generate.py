"""Generate Japanese TTS for PBZ voice events using local VOICEVOX engines.

- One fixed voice per character prefix (voice_map.json).
- Target duration = Chinese original duration (DT_WwiseVoiceDuration), so the
  Japanese audio stays aligned with the original animation/subtitle timing.
- Resilient: engines may die or fail; the script restarts them and retries.
"""
import csv, json, os, re, sys, time, threading, queue, subprocess, urllib.request, urllib.parse, wave, io

#: regenerate the lines that already exist (the voice of a character may have
#: changed since they were synthesized)
FORCE = '--force' in sys.argv
sys.argv = [a for a in sys.argv if a != '--force']

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE, out, voicevox
from tts.voices import speaker_for
OUT_DIR = out('jp_events')
# the engine can live outside the repository (it is not versioned)
VV_DIR = voicevox()
PORTS = [50021, 50022, 50023, 50024, 50025, 50026, 50027, 50028]
MAX_RETRIES = 4

#: the voice assignment: a line synthesized before it was changed was made
#: with another voice, so it has to be made again
VOICES_PATH = os.path.join(BASE, 'data', 'character_voices.json')
VOICES_STAMP = os.path.getmtime(VOICES_PATH) if os.path.exists(VOICES_PATH) else 0

rows = list(csv.DictReader(open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8')))
durations = json.load(open(os.path.join(BASE, 'data', 'durations.json'), encoding='utf-8'))

def request(url, data=None, method=None, timeout=120):
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={'Content-Type': 'application/json'} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def wav_duration(data):
    w = wave.open(io.BytesIO(data))
    d = w.getnframes() / float(w.getframerate())
    w.close()
    return d

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
results = {}
results_lock = threading.Lock()
errors = []
error_lock = threading.Lock()


def synthesize(row):
    event = row['event_name']
    text = (row.get('japanese_text_tts') or row['japanese_text'] or '').strip()
    if not text:
        return None
    out_path = os.path.join(OUT_DIR, event + '.wav')
    if not FORCE and os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        # a line older than the voice assignment was made with another voice
        if os.path.getmtime(out_path) >= VOICES_STAMP:
            return 'skip'
    target = durations.get(event, [0.0, 0.0])[0] or 0.0
    speaker = speaker_for(event)

    for attempt in range(MAX_RETRIES):
        port = pool.any_available()
        if port is None:
            time.sleep(10)
            if not pool.ensure(PORTS[0]):
                continue
            port = pool.any_available()
            if port is None:
                continue
        try:
            query = json.loads(request(
                f'http://127.0.0.1:{port}/audio_query?text={urllib.parse.quote(text)}&speaker={speaker}',
                method='POST', timeout=90))
            speed = query.get('speedScale', 1.0)
            best = None
            for _ in range(MAX_RETRIES):
                query['speedScale'] = speed
                wav = request(f'http://127.0.0.1:{port}/synthesis?speaker={speaker}',
                              data=json.dumps(query).encode('utf-8'), timeout=180)
                dur = wav_duration(wav)
                best = (wav, dur)
                if target <= 0:
                    break
                ratio = dur / target
                if 0.9 <= ratio <= 1.1:
                    break
                speed = max(0.5, min(2.0, speed * ratio))
            wav, dur = best
            with open(out_path, 'wb') as f:
                f.write(wav)
            return dur
        except Exception as e:
            with error_lock:
                errors.append((event, repr(e)[:120]))
            pool.unavailable.add(port)
            time.sleep(2)
    return None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    todo = [r for r in rows if (r.get('japanese_text_tts') or r['japanese_text']).strip()]
    print('events to synthesize:', len(todo), flush=True)
    lock = threading.Lock()
    counter = [0]

    def worker():
        while True:
            with lock:
                if not todo:
                    return
                row = todo.pop()
            dur = synthesize(row)
            with results_lock:
                if dur is not None:
                    results[row['event_name']] = dur
                counter[0] += 1
                if counter[0] % 100 == 0:
                    print(f'{counter[0]} processed, errors={len(errors)}, remaining={len(todo)}', flush=True)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    json.dump(results, open(os.path.join(BASE, 'data', 'jp_durations.json'), 'w'))
    print('finished. errors:', len(errors), flush=True)
    seen = set()
    for e, msg in errors:
        if msg not in seen:
            seen.add(msg)
            print('ERR sample:', e, msg, flush=True)


if __name__ == '__main__':
    main()
