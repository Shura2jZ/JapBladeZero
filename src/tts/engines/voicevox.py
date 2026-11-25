"""VOICEVOX engine — the production baseline (A in the benchmark).

Local HTTP servers started by scripts/voicevox.sh. The performance knobs are
the engine's own: speedScale, pitchScale, intonationScale, volumeScale, plus
pre/post phoneme lengths. No emotion tags: VOICEVOX has none, so a « direction
» is expressed through intonation and pauses in the query.
"""
import json, urllib.parse, urllib.request


class Engine:
    name = 'voicevox'

    def __init__(self, ports=None):
        self.ports = ports or [50021, 50022, 50023, 50024]
        self._i = 0

    def available(self):
        try:
            self.request(f'http://127.0.0.1:{self.ports[0]}/version')
            return True
        except Exception:
            return False

    def request(self, url, data=None, method=None, timeout=120):
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={'Content-Type': 'application/json'} if data else {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()

    def _port(self):
        for _ in self.ports:
            self._i = (self._i + 1) % len(self.ports)
            p = self.ports[self._i]
            try:
                self.request(f'http://127.0.0.1:{p}/version', timeout=10)
                return p
            except Exception:
                continue
        return None

    def synthesize(self, text, opts=None, speaker=11):
        """opts: speed, pitch (semitone-like ratio), intonation, volume."""
        port = self._port()
        if port is None:
            return None
        o = opts or {}
        q = self.request(
            f'http://127.0.0.1:{port}/audio_query?text={urllib.parse.quote(text)}&speaker={speaker}',
            method='POST', timeout=90)
        query = json.loads(q)
        query['speedScale'] = 1.0 * o.get('speed', 1.0)
        query['pitchScale'] = o.get('pitch', 0.0)
        query['intonationScale'] = o.get('intonation', 1.0)
        query['volumeScale'] = o.get('volume', 1.0)
        wav = self.request(f'http://127.0.0.1:{port}/synthesis?speaker={speaker}',
                           data=json.dumps(query).encode('utf-8'), timeout=180)
        return wav, 24000
