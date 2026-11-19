"""Lists the files to pack in the IoStore container of the mod.

The list is a TSV: "game path<TAB>local file", with the game path relative to
the content root of the project (ProjectPBZ/Content/...).

Usage:
    python src/patch/container_files.py            -> data/container_files.tsv
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATCHED = os.path.join(BASE, 'build', 'patched_all')
LIBRARY = os.path.join(BASE, 'build', 'patched_lib')
PATHS = os.path.join(BASE, 'data', 'event_paths.tsv')
OUT = os.path.join(BASE, 'data', 'container_files.tsv')


def main():
    rows = []
    paths = {}
    for line in open(PATHS, encoding='utf-8'):
        if not line.strip():
            continue
        event, key = line.rstrip('\n').split('\t')[:2]
        paths.setdefault(event, []).append(key)

    for event, keys in paths.items():
        for key in keys:
            name = os.path.basename(key)
            local = os.path.join(PATCHED, name)
            if os.path.exists(local):
                rows.append((key, local))

    for name in ('VO_CN.uasset', 'VO_CN.ubulk'):
        local = os.path.join(LIBRARY, name)
        if os.path.exists(local):
            rows.append(('ProjectPBZ/Content/Wwise/' + name, local))

    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        for path, local in rows:
            f.write(f'{path}\t{local}\n')
    print(f'{len(rows)} files -> {OUT}')


if __name__ == '__main__':
    main()
