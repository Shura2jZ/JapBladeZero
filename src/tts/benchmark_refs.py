"""Dumps clean Chinese reference audio for the benchmark events.

The reference is the first 8 seconds of the decoded Chinese media: a zero-shot
voice-cloning engine uses it as the timbre/prompt. Written to
out/benchmark/refs/<event>.cn.wav (16 kHz mono, what the engines expect).

    python src/tts/benchmark_refs.py [--limit N]
"""
import argparse, json, os, sys, wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'audio'))

bench = json.load(open(os.path.join(BASE, 'data', 'benchmark_set.json'), encoding='utf-8'))
OUT = os.path.join(BASE, 'out', 'benchmark', 'refs')
MAX_SEC = 8.0


def dump(event):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, event + '.cn.wav')
    if os.path.exists(p) and os.path.getsize(p) > 1000:
        return 'skip'
    import pyvgmstream
    from cn_media import chinese_media
    from wavio import read_wav

    blob = chinese_media(event)
    if blob is None:
        return 'nomedia'
    wav = pyvgmstream.decode_buffer_to_wav_bytes(blob, filename_hint=event + '.wem')
    samples, rate = read_wav(wav)          # mono float32 ("-1..1")
    n = int(min(MAX_SEC, len(samples) / rate) * rate)
    if n < rate:
        return 'too_short'
    mono = samples[:n]
    with wave.open(p, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((mono * 32767).astype('<i2').tobytes())
    return 'ok'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    items = list(bench.items())
    if args.limit:
        items = items[:args.limit]
    import collections
    stats = collections.Counter()
    for event, meta in items:
        stats[dump(event)] += 1
    print(dict(stats), '->', OUT)


if __name__ == '__main__':
    main()
