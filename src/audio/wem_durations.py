"""Measures the decoded duration of every injected .wem.

The .wem files are Ogg Vorbis wrapped in a Wwise RIFF header: the duration the
engine hears is the decoded one, which can differ by a few milliseconds from
the duration of the source WAV. The DataTable must carry the duration of the
media that is actually played, so it is measured here rather than assumed.

Usage:
    python src/audio/wem_durations.py [--wem-dir DIR] [--out FILE]
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE, out

try:
    import pyvgmstream
except ImportError:
    pyvgmstream = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wem-dir', default=out('jp_wem'))
    ap.add_argument('--out', default=os.path.join(BASE, 'data', 'jp_wem_durations.json'))
    ap.add_argument('--compare', default=os.path.join(BASE, 'data', 'jp_media_durations.json'))
    args = ap.parse_args()

    if pyvgmstream is None:
        raise SystemExit('pyvgmstream is not installed')

    names = sorted(n for n in os.listdir(args.wem_dir) if n.endswith('.wem'))
    durations, failures = {}, []
    for i, name in enumerate(names, 1):
        event = name[:-4]
        try:
            info = pyvgmstream.probe(os.path.join(args.wem_dir, name))
            durations[event] = float(info.duration_seconds)
        except Exception as e:
            failures.append((event, repr(e)[:120]))
        if i % 500 == 0:
            print(f'{i}/{len(names)}', flush=True)

    print(f'measured {len(durations)}/{len(names)}, {len(failures)} failures')
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(durations, f, ensure_ascii=False, indent=1)
    print(f'written {args.out}')

    if failures:
        for ev, err in failures[:10]:
            print(f'  ! {ev}: {err}')

    if os.path.exists(args.compare):
        ref = json.load(open(args.compare, encoding='utf-8'))
        diffs = sorted(((abs(durations[e] - ref[e]), e) for e in durations if e in ref), reverse=True)
        if diffs:
            worst = diffs[0][0]
            over = [d for d, e in diffs if d > 0.001]
            print(f'compared with {args.name if hasattr(args, "name") else args.compare}: '
                  f'max {worst * 1000:.1f} ms, {len(over)} differ by more than 1 ms')
            for d, e in diffs[:10]:
                print(f'  {e[:50]:52} {durations[e]:.6f} vs {ref[e]:.6f} ({d * 1000:.1f} ms)')


if __name__ == '__main__':
    main()
