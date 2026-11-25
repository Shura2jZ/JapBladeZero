"""Loudness-normalizes the benchmark takes for fair A/B listening.

Measured: VOICEVOX writes at RMS ~0.05 while CosyVoice 3 output peaks over
±1.0 (clipped to a monster-like distortion). Every take is scaled to the same
target RMS (-22 dBFS) with a hard peak guard at 0.97.

    python src/tts/benchmark_norm.py [outdir1 outdir2 ...]
"""
import json, os, sys, wave

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TARGET_RMS = 0.079   # -22 dBFS
PEAK_MAX = 0.97

def norm_path(p):
    with wave.open(p, 'rb') as w:
        n, r, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
        data = w.readframes(n)
    if sw != 2 or ch != 1:
        return 'skip'
    import struct
    v = list(struct.unpack(f'<{n}h', data))
    rms = (sum(x * x for x in v) / n) ** 0.5
    if rms == 0:
        return 'silence'
    peak = max(abs(x) for x in v) / 32768.0
    gain = min(TARGET_RMS / (rms / 32768.0), PEAK_MAX / max(peak, 1e-9))
    if abs(gain - 1.0) < 0.05:
        return 'ok'
    v = [max(-32767, min(32767, int(x * gain))) for x in v]
    with wave.open(p, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(r)
        w.writeframes(struct.pack(f'<{n}h', *v))
    return f'x{gain:.2f}'


def main():
    dirs = sys.argv[1:] or ['out/benchmark/voicevox', 'out/benchmark/cosyvoice3',
                            'out/benchmark/cosyvoice3_zero', 'out/benchmark/AB']
    import collections
    for d in dirs:
        full = os.path.join(BASE, d)
        stats = collections.Counter()
        for f in sorted(os.listdir(full)):
            if f.endswith('.wav') and not f.startswith('0'):
                stats[norm_path(os.path.join(full, f))] += 1
        print(d, dict(stats))
    # the AB files (01A.wav etc.) go through the same normalization
    ab = os.path.join(BASE, 'out/benchmark/AB')
    stats = collections.Counter()
    for f in sorted(os.listdir(ab)):
        if f.endswith('.wav'):
            stats[norm_path(os.path.join(ab, f))] += 1
    print('AB', dict(stats))


if __name__ == '__main__':
    main()
