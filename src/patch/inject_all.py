"""Patches the Chinese media of every voice event with its Japanese .wem.

Reads the raw packages extracted by the C# tool (inject/out_raw_all) and writes the
patched ones to inject/out_patched_all. The layout of the .ubulk and of the record
table of the .uasset is described in inject_bin.py.

Usage: python inject_all.py [--raw DIR] [--out DIR] [--events FILE]
"""
import argparse, json, os, sys, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from inject_bin import patch, BASE

MAIN = os.path.join(BASE, 'tools', 'csharp', 'inject', 'Program.cs')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', default=os.path.join(BASE, 'build', 'raw_all'))
    ap.add_argument('--out', default=os.path.join(BASE, 'build', 'patched_all'))
    ap.add_argument('--events', default=os.path.join(BASE, 'data', 'events_ok.txt'))
    ap.add_argument('--wem-dir', default=os.path.join(BASE, 'out', 'jp_wem'))
    args = ap.parse_args()

    events = [l.strip() for l in open(args.events, encoding='utf-8') if l.strip()]
    os.makedirs(args.out, exist_ok=True)

    ok, failed = 0, []
    total_old = total_new = 0
    for i, ev in enumerate(events, 1):
        wem = os.path.join(args.wem_dir, ev + '.wem')
        try:
            info = patch(ev, wem, args.out, args.raw)
            ok += 1
            total_old += info['old_ubulk']
            total_new += info['new_ubulk']
        except Exception as e:
            failed.append((ev, repr(e)[:160]))
        if i % 250 == 0:
            print(f'{i}/{len(events)}  patched={ok} failed={len(failed)}', flush=True)

    print(f'\npatched {ok}/{len(events)}   failed {len(failed)}')
    print(f'ubulk total: {total_old/1e6:.0f} Mo -> {total_new/1e6:.0f} Mo')
    if failed:
        print('\nfirst failures:')
        for ev, err in failed[:15]:
            print(f'  {ev}: {err}')
    with open(os.path.join(BASE, 'data', 'inject_failures.json'), 'w', encoding='utf-8') as f:
        json.dump(failed, f, indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
