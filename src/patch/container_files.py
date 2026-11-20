"""Lists the files to pack in the IoStore container of the mod.

The list is a TSV: "game path<TAB>local file", with the game path relative to
the content root of the project (ProjectPBZ/Content/...).

Usage:
    python src/patch/container_files.py            -> data/container_files.tsv
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE, build

PATCHED = build('patched_all')
LIBRARY = build('patched_lib')
DATATABLE = build('patched_dt')
PATHS = os.path.join(BASE, 'data', 'event_paths.tsv')
OUT = os.path.join(BASE, 'data', 'container_files.tsv')

# The table of the voice durations. The game has no Japanese voice bank (only
# Chinese and English), so the Japanese audio is installed in the Chinese one
# and the engine keeps reading Duration_Chinese: it carries the Japanese
# duration of the media that is actually played.
DATATABLE_PATH = 'ProjectPBZ/Content/PBZContent/DataTable/Audio/DT_WwiseVoiceDuration.uasset'


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

    local = os.path.join(DATATABLE, 'DT_WwiseVoiceDuration.uasset')
    if os.path.exists(local):
        rows.append((DATATABLE_PATH, local))
    else:
        print(f'! {local} absent : la table des durees ne sera pas remplacee')

    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        for path, local in rows:
            f.write(f'{path}\t{local}\n')
    print(f'{len(rows)} files -> {OUT}')


if __name__ == '__main__':
    main()
