"""Builds multi-line Chinese voice references per character.

A 1.8 s prompt makes zero-shot cloning unstable (measured: CosyVoice spoke a
12-char line 4x too slowly). The fix is the classic one: concatenate several
short lines of the SAME character into one reference of ~15-20 s, with small
silences between lines. The reference is written next to the single-line one:

    out/benchmark/refs/<event>.cn.multi.wav   (reference of <event>'s character)

    python src/tts/benchmark_refs.py --multi
"""
import argparse, json, os, sys, wave, csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'audio'))
from paths import BASE

bench = json.load(open(os.path.join(BASE, 'data', 'benchmark_set.json'), encoding='utf-8'))
speakers = json.load(open(os.path.join(BASE, 'data', 'event_speaker.json'), encoding='utf-8'))
OUT = os.path.join(BASE, 'out', 'benchmark', 'refs')
TARGET_SEC = 18.0
GAP_SEC = 0.35


def decode(event):
    import pyvgmstream
    from cn_media import chinese_media
    from wavio import read_wav
    blob = chinese_media(event)
    if blob is None:
        return None, None
    wav = pyvgmstream.decode_buffer_to_wav_bytes(blob, filename_hint=event + '.wem')
    return read_wav(wav)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    # index: character -> [events], from the full manifest
    import csv
    rows = list(csv.DictReader(open(os.path.join(BASE, 'data', 'manifest_jp.csv'),
                                    encoding='utf-8')))
    by_char = {}
    for r in rows:
        sp = speakers.get(r['event_name'])
        if sp:
            by_char.setdefault(sp, []).append(r['event_name'])

    os.makedirs(OUT, exist_ok=True)
    items = list(bench.items())
    if args.limit:
        items = items[:args.limit]
    manifest = {}
    rows_by_event = {r['event_name']: r for r in rows}
    ok = short = 0
    for event, meta in items:
        p = os.path.join(OUT, event + '.cn.multi.wav')
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            ok += 1
            continue
        char = speakers.get(event)
        candidates = [e for e in by_char.get(char, []) if e != event]
        pieces, rate, total = [], None, 0.0
        pieces_events = []
        # the event's own line first, then the character's other lines
        for e in [event] + candidates:
            samples, rate = decode(e)
            if samples is None:
                continue
            n = int(min(8.0, len(samples) / rate) * rate)
            if n < rate * 0.6:
                continue
            pieces.append(samples[:n])
            pieces_events.append(e)
            total += n / rate
            if total >= TARGET_SEC:
                break
        if total < 4.0:
            short += 1
            continue
        manifest[event] = pieces_events
        import numpy as np
        gap = np.zeros(int(GAP_SEC * rate), dtype=samples.dtype)
        full = np.concatenate([gap if i else None for i in range(0)] or
                              np.array([]), axis=None) if False else None
        parts = []
        for i, seg in enumerate(pieces):
            if i:
                parts.append(gap)
            parts.append(seg)
        full = np.concatenate(parts)[:int(TARGET_SEC * rate)]
        with wave.open(p, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes((full * 32767).astype('<i2').tobytes())
        ok += 1
    json.dump(manifest, open(os.path.join(BASE, 'data', 'benchmark_refs.json'), 'w'),
              ensure_ascii=False, indent=1)
    print(f'{ok} references multi-lignes ({short} personnages sans assez d\'audio)')


if __name__ == '__main__':
    main()
