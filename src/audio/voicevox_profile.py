"""Profiles the voices of the VOICEVOX engine: one height per voice.

To give a character a voice that looks like the original one, the height of
every available voice has to be known. Each voice is made to say a fixed
sentence, the result is measured the same way the Chinese voices are, and the
result is kept in data/voicvox_profiles.json.

Usage:
    python src/audio/voicevox_profile.py [--ports 50021-50028]
"""
import argparse
import io
import json
import os
import sys
import urllib.request
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import BASE

from pitch import describe
from wavio import read_wav

TEST_TEXT = 'こんにちは、世界。今日はいい天気ですね。'


def synth(port, text, style_id):
    """The WAV the engine returns, as bytes.

    The engine expects the query built by /audio_query, and it accepts a
    pitchScale: that is what lets a character keep the height of its original
    voice.
    """
    import urllib.parse
    url = ('http://127.0.0.1:%d/audio_query?text=%s&speaker=%d'
           % (port, urllib.parse.quote(text), style_id))
    req = urllib.request.Request(url, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r:
        query = json.loads(r.read())
    body = json.dumps(query).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:%d/synthesis?speaker=%d' % (port, style_id),
                                 data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ports', default='50021-50028')
    ap.add_argument('--out', default=os.path.join(BASE, 'data', 'voicevox_profiles.json'))
    args = ap.parse_args()

    lo, _, hi = args.ports.partition('-')
    ports = list(range(int(lo), int(hi) + 1))

    styles = json.load(open(os.path.join(BASE, 'data', 'voicevox_styles.json'), encoding='utf-8'))
    print(f'{len(styles)} styles to profile')

    out = {}
    for i, (sid, info) in enumerate(sorted(styles.items(), key=lambda kv: kv[1]['id']), 1):
        port = ports[i % len(ports)]
        try:
            wav = synth(port, TEST_TEXT, info['id'])
            samples, rate = read_wav(wav)
            d = describe(samples, rate)
        except Exception as e:
            d = {'error': repr(e)[:120]}
        out[sid] = dict(d or {}, voice=info['voice'], style=info['style'],
                        gender=info['gender'], style_id=info['id'])
        if i % 20 == 0:
            print(f'{i}/{len(styles)}', flush=True)

    json.dump(out, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    ok = [v for v in out.values() if 'f0_median' in v]
    print(f'profiled {len(ok)}/{len(styles)} styles')
    by_voice = {}
    for v in ok:
        by_voice.setdefault(v['voice'], []).append(v['f0_median'])
    for voice, f0s in sorted(by_voice.items()):
        print('   %-16s f0=%.0f Hz (%d styles)' % (voice, sum(f0s) / len(f0s), len(f0s)))
    print('->', args.out)


if __name__ == '__main__':
    main()
