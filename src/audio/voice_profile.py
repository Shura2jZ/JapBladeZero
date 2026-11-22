"""Profiles the Chinese voices of the game: one height per character.

The game already gives every character its own Chinese voice. That voice is
the reference of the Japanese one: a character that is played in Chinese by a
low male voice has to be played in Japanese by a low male voice, otherwise the
doubling does not look like the character anymore.

The height (F0) of every line is measured, then aggregated per character.

Usage:
    python src/audio/voice_profile.py [--workers 6] [--out data/cn_voice_profiles.json]
"""
import argparse
import collections
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import BASE

from concurrent.futures import ProcessPoolExecutor


def measure(event):
    """The height of the Chinese media of an event, or None."""
    try:
        import pyvgmstream
        from pitch import describe
        from wavio import read_wav
        from cn_media import chinese_media

        blob = chinese_media(event)
        if blob is None:
            return event, None
        wav = pyvgmstream.decode_buffer_to_wav_bytes(blob, filename_hint=event + '.wem')
        samples, rate = read_wav(wav)
        info = describe(samples, rate)
        if info is None:
            return event, None
        return event, info
    except Exception as e:            # a broken media must not stop the run
        return event, {'error': repr(e)[:120]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--out', default=os.path.join(BASE, 'data', 'cn_voice_profiles.json'))
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8')))
    events = [r['event_name'] for r in rows]
    if args.limit:
        events = events[:args.limit]
    print(f'{len(events)} events to measure')

    measured = {}
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for event, info in pool.map(measure, events, chunksize=8):
            done += 1
            if info and 'error' not in info:
                measured[event] = info
            if done % 250 == 0:
                print(f'{done}/{len(events)} measured {len(measured)}', flush=True)

    # aggregate per character
    ev2sp = json.load(open(os.path.join(BASE, 'data', 'event_speaker.json'), encoding='utf-8'))
    per_char = collections.defaultdict(list)
    for ev, info in measured.items():
        code = ev2sp.get(ev)
        if not code:
            continue
        per_char[code].append(info)

    out = {'events': measured, 'characters': {}}
    for code, infos in per_char.items():
        f0 = sorted(i['f0_median'] for i in infos)
        n = len(f0)
        median = f0[n // 2] if n % 2 else (f0[n // 2 - 1] + f0[n // 2]) / 2
        spreads = sorted(i['f0_std'] for i in infos)
        out['characters'][code] = {
            'lines': n,
            'f0_median': median,
            'f0_low': f0[max(0, n // 10)],
            'f0_high': f0[min(n - 1, n * 9 // 10)],
            'f0_std_median': spreads[n // 2],
        }
    json.dump(out, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'measured {len(measured)} events, {len(out["characters"])} characters')
    chars = sorted(out['characters'].items(), key=lambda kv: -kv[1]['lines'])
    for code, v in chars[:15]:
        print('   %-24s lignes=%-4d f0=%.0f Hz' % (code, v['lines'], v['f0_median']))
    print('->', args.out)


if __name__ == '__main__':
    main()
