"""Checks that the patched Wwise library really holds the Japanese media.

The check goes the way the game does: hash -> PackagedFiles index -> block of the
.ubulk, and compares the block with the Japanese .wem that was supposed to be
written there. The duration of the Japanese media is also compared with the
duration of the Chinese original (DT_WwiseVoiceDuration), because the Japanese
lines are padded to exactly that duration.

Usage: python src/patch/verify_library.py [--lib build/patched_lib]
"""
import argparse, collections, json, os, struct, sys
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE, build, out


def find_table(uasset):
    best = None
    for base in range(0, len(uasset) - 32, 4):
        if struct.unpack_from('<ii', uasset, base) != (-1, -1):
            continue
        count = 0
        for k in range(20000):
            o = base + k * 32
            if o + 32 > len(uasset):
                break
            if struct.unpack_from('<ii', uasset, o) != (-1, -1):
                break
            if struct.unpack_from('<I', uasset, o + 16)[0] != 66817:
                break
            size = struct.unpack_from('<I', uasset, o + 8)[0]
            if size < 0:
                break
            count += 1
        if count >= 2 and (best is None or count > best[1]):
            best = (base, count)
    return best


def blocks_of(uasset, ubulk_size):
    base, count = find_table(uasset)
    blocks, offset = [], 0
    for k in range(count):
        size = struct.unpack_from('<I', uasset, base + k * 32 + 8)[0]
        blocks.append((offset, size))
        offset += size
    assert offset == ubulk_size, f'blocks cover {offset}, file is {ubulk_size}'
    return blocks


def wem_duration(blob):
    if blob[:4] != b'RIFF' or blob[8:12] != b'WAVE':
        return None
    i = blob.find(b'fmt ')
    if i < 0:
        return None
    size = struct.unpack_from('<I', blob, i + 4)[0]
    d = blob[i + 8:i + 8 + size]
    samples = struct.unpack_from('<I', d, 24)[0]
    rate = struct.unpack_from('<I', d, 4)[0]
    return samples / float(rate or 48000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lib', default=build('patched_lib'))
    ap.add_argument('--wem', default=out('jp_wem'))
    ap.add_argument('--refs', default=os.path.join(BASE, 'data', 'external_media_refs.tsv'))
    ap.add_argument('--packaged', default=os.path.join(BASE, 'data', 'library_packaged_files.tsv'))
    ap.add_argument('--durations', default=os.path.join(BASE, 'data', 'durations.json'))
    args = ap.parse_args()

    uasset = open(os.path.join(args.lib, 'VO_CN.uasset'), 'rb').read()
    ubulk = open(os.path.join(args.lib, 'VO_CN.ubulk'), 'rb').read()
    blocks = blocks_of(uasset, len(ubulk))

    packaged = []
    for line in open(args.packaged, encoding='utf-8').read().splitlines()[1:]:
        p = line.split('\t')
        if len(p) >= 2 and p[1].isdigit():
            packaged.append(int(p[1]))

    content = []
    for i, (off, size) in enumerate(blocks):
        blob = ubulk[off:off + size]
        if blob[:4] == b'RIFF' and blob[8:12] == b'WAVE':
            if struct.unpack_from('<I', blob, 4)[0] + 8 == size:
                content.append(i)
        elif blob[:4] == b'BKHD':
            content.append(i)

    hash2content = {h: content[i] for i, h in enumerate(packaged) if i < len(content)}
    durations = json.load(open(args.durations, encoding='utf-8'))

    ok = mismatch = missing = 0
    problems = []
    for line in open(args.refs, encoding='utf-8').read().splitlines()[1:]:
        p = line.split('\t')
        if len(p) < 6 or p[1] != 'Chinese':
            continue
        ev, h = p[0], int(p[3])
        blk = hash2content.get(h)
        if blk is None:
            missing += 1
            problems.append((ev, 'not in the library'))
            continue
        off, size = blocks[blk]
        blob = ubulk[off:off + size]
        wem_path = os.path.join(args.wem, ev + '.wem')
        if not os.path.exists(wem_path):
            problems.append((ev, 'no japanese media'))
            mismatch += 1
            continue
        want = open(wem_path, 'rb').read()
        if blob != want:
            mismatch += 1
            problems.append((ev, 'block does not hold the japanese media'))
            continue
        dur = wem_duration(blob)
        zh = durations.get(ev, [0.0, 0.0])[0]
        if zh > 0 and dur is not None and abs(dur - zh) > 0.05:
            mismatch += 1
            problems.append((ev, f'duration {dur:.3f} != chinese {zh:.3f}'))
            continue
        ok += 1
    print(f'ok={ok} mismatch={mismatch} missing={missing}')
    for p in problems[:20]:
        print('   ', p)


if __name__ == '__main__':
    main()
