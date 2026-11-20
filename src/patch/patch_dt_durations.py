"""Rewrites the Chinese durations of DT_WwiseVoiceDuration with the Japanese ones.

Why the Chinese column
----------------------
The game ships only two voice banks, Chinese and English; the Japanese it
contains is only text (the `ja` localisation). The mod therefore installs the
generated Japanese audio *inside* the Chinese bank, and the engine keeps
playing that bank: the duration it looks up while playing it is
`Duration_Chinese`. The `Duration_Japanese` and `Duration_German` columns are
zero in this build and are never read, so they are left untouched.

How the patch works
-------------------
`DT_WwiseVoiceDuration.uasset` is the export bundle chunk of the package, a
plain byte stream. Each row is laid out as

    int32 nameLength          (length of the name, null terminator included)
    char  name[nameLength]    (ASCII, the last byte is the terminator)
    float durationChinese     (only when it is not zero)
    float durationEnglish     (only when it is not zero)
    ... 11 bytes of property tags

Rather than trusting that layout blindly, the script searches, for every row
that has a Chinese duration, the exact byte sequence

    name + "\\0" + float32(chinese duration)

and only overwrites the float when it is found: every patched value is
therefore a value the engine really stores. The size of the file never
changes, so no export size, no package summary and no container offset has to
be recomputed.

Usage:
    python src/patch/patch_dt_durations.py
"""
import argparse, json, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE, build

DURATIONS = os.path.join(BASE, 'data', 'durations.json')
JP_DURATIONS = os.path.join(BASE, 'data', 'jp_media_durations.json')
SOURCE = build('dt_orig', 'DT_WwiseVoiceDuration.uasset')
OUT = build('patched_dt', 'DT_WwiseVoiceDuration.uasset')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', default=SOURCE)
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--durations', default=DURATIONS)
    ap.add_argument('--jp', default=JP_DURATIONS)
    ap.add_argument('--report', default=os.path.join(BASE, 'data', 'dt_duration_patch.json'))
    args = ap.parse_args()

    cn = {ev: v[0] for ev, v in json.load(open(args.durations, encoding='utf-8')).items()}
    jp = json.load(open(args.jp, encoding='utf-8'))

    blob = bytearray(open(args.source, 'rb').read())
    print(f'source {args.source}: {len(blob)} bytes')

    patched, skipped, missing = [], [], []
    for ev, duration in sorted(jp.items()):
        old = cn.get(ev, 0.0)
        if old <= 0:
            # no Chinese duration in the table: the row stores no float at all,
            # inserting one would resize the chunk and every offset after it
            skipped.append(ev)
            continue
        needle = ev.encode('utf-8') + b'\x00' + struct.pack('<f', old)
        pos = blob.find(needle)
        if pos < 0:
            missing.append(ev)
            continue
        if blob.find(needle, pos + 1) >= 0:
            raise SystemExit(f'{ev}: the Chinese duration appears twice')
        at = pos + len(ev.encode('utf-8')) + 1
        struct.pack_into('<f', blob, at, float(duration))
        patched.append({'event': ev, 'chinese': old, 'japanese': duration})

    print(f'patched {len(patched)} rows, {len(skipped)} rows without a Chinese duration, '
          f'{len(missing)} not found')

    # verification: every patched row now holds the Japanese duration
    errors = 0
    for row in patched:
        needle = row['event'].encode('utf-8') + b'\x00' + struct.pack('<f', row['japanese'])
        if blob.find(needle) < 0:
            errors += 1
    print(f'verification: {len(patched) - errors}/{len(patched)} rows hold the Japanese duration')
    if errors:
        raise SystemExit('verification failed')

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    open(args.out, 'wb').write(bytes(blob))
    print(f'written {args.out}: {len(blob)} bytes')

    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    json.dump({'patched': patched, 'skipped': skipped, 'missing': missing},
              open(args.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'report {args.report}')


if __name__ == '__main__':
    main()
