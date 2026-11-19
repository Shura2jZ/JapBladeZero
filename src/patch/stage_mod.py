"""Stages the patched files with the paths they have in the game.

The mod is a pak file mounted in the game's Paks folder. Its content must be laid
out like the game:

    ProjectPBZ/Content/Wwise/Events/VO/Plot/<dossier>/<evenement>.uasset
    ProjectPBZ/Content/Wwise/Events/VO/Plot/<dossier>/<evenement>.ubulk
    ProjectPBZ/Content/Wwise/VO_CN.uasset
    ProjectPBZ/Content/Wwise/VO_CN.ubulk
    ProjectPBZ/Content/PBZContent/DataTable/Audio/DT_WwiseVoiceDuration.uasset

Usage:
    python src/patch/stage_mod.py
"""
import argparse, csv, json, os, shutil, sys
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE, build
GAME_ROOT = 'ProjectPBZ/Content'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--patched', default=build('patched_all'))
    ap.add_argument('--library', default=build('patched_lib'))
    ap.add_argument('--paths', default=os.path.join(BASE, 'data', 'event_paths.tsv'))
    ap.add_argument('--out', default=build('stage'))
    ap.add_argument('--datatable', default='', help='patched DT_WwiseVoiceDuration.uasset')
    args = ap.parse_args()

    if os.path.isdir(args.out):
        shutil.rmtree(args.out)
    os.makedirs(args.out)

    # the game path of every event
    paths = {}
    for line in open(args.paths, encoding='utf-8').read().splitlines():
        if not line.strip():
            continue
        ev, key = line.split('\t')[:2]
        paths.setdefault(ev, []).append(key)

    staged = 0

    def place(src, dst):
        """Copies a file, or hard links it when the file system allows it.

        The staging directory holds several gigabytes, the same files are already
        in build/patched_all: a hard link avoids duplicating them.
        """
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)

    for ev, keys in paths.items():
        for key in keys:
            name = os.path.basename(key)
            src = os.path.join(args.patched, name)
            if not os.path.exists(src):
                continue                      # not patched (external media, no change)
            place(src, os.path.join(args.out, key))
            staged += 1

    # the Wwise library, which holds the media of the external events
    for name in ('VO_CN.uasset', 'VO_CN.ubulk'):
        src = os.path.join(args.library, name)
        if not os.path.exists(src):
            continue
        place(src, os.path.join(args.out, GAME_ROOT, 'Wwise', name))
        staged += 1

    if args.datatable:
        src = os.path.join(args.datatable, 'DT_WwiseVoiceDuration.uasset')
        if os.path.exists(src):
            dst = os.path.join(args.out, GAME_ROOT, 'PBZContent', 'DataTable', 'Audio',
                               'DT_WwiseVoiceDuration.uasset')
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            staged += 1

    print(f'{staged} files staged in {args.out}')
    total = sum(os.path.getsize(os.path.join(r, f))
                for r, _, fs in os.walk(args.out) for f in fs)
    print(f'{total / 1e6:.0f} Mo')


if __name__ == '__main__':
    main()
