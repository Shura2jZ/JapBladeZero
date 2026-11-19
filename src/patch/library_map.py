"""Maps the media of the Wwise library (VO_CN) to the events that use them.

Background
----------
Most voice events keep their media in their own package: the .uasset describes the
event and the .ubulk holds the media. A few hundred events are packaged differently:
their media lives in the Wwise asset library `ProjectPBZ/Content/Wwise/VO_CN`
(PackagingStrategy = External), and those events have no .ubulk at all.

The library package is a plain chunk container:

    VO_CN.uasset   bulk data table: one 32 byte entry per block
    VO_CN.ubulk    the blocks, in the order of that table

The blocks are of four kinds:
    header   the Wwise event header of an event (BKHD + HIRC), it mentions the
             Wwise media id of the event
    media    a complete RIFF/WAVE file, the media itself
    preview  a truncated copy of a media, so the engine can start playing early
    other    padding

The event header of an event holds the id of its media, so the header can be matched
with an event. This script does that, and lists the candidate media for every event
by duration (the duration of the Chinese media is known from DT_WwiseVoiceDuration).

Usage:
    python src/patch/library_map.py [--lib build/libs/VO_CN] [--out data/library_map.json]
"""
import argparse, collections, json, os, struct

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAMPLE_RATE = 48000


def parse_blocks(uasset, ubulk):
    """[(offset, size)] of the blocks, read from the bulk data table of the .uasset.

    The table is a list of 32 byte entries, each of them
    [-1, -1, SizeOnDisk, 0, Flags, 0, EndOffset, 0]. Its position is not fixed, so it
    is located by the longest run of valid entries, and the run must tile the .ubulk
    exactly.
    """
    best = None
    for base in range(0, len(uasset) - 32, 4):
        if struct.unpack_from('<ii', uasset, base) != (-1, -1):
            continue
        sizes = []
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
            sizes.append(size)
        if len(sizes) >= 2 and (best is None or len(sizes) > len(best)):
            best = sizes
        if sum(sizes) == len(ubulk):
            best = sizes
            break
    if best is None:
        raise ValueError('bulk data table not found')
    blocks, offset = [], 0
    for size in best:
        blocks.append((offset, size))
        offset += size
    if offset != len(ubulk):
        raise ValueError(f'blocks cover {offset} bytes, the .ubulk is {len(ubulk)}')
    return blocks


def wem_info(blob):
    """(samples, duration) of a Wwise Vorbis .wem, or None if it is not one."""
    if blob[:4] != b'RIFF' or blob[8:12] != b'WAVE':
        return None
    i = blob.find(b'fmt ')
    if i < 0:
        return None
    size = struct.unpack_from('<I', blob, i + 4)[0]
    data = blob[i + 8:i + 8 + size]
    if struct.unpack_from('<H', data, 0)[0] != 0xFFFF:
        return None
    samples = struct.unpack_from('<I', data, 24)[0]
    rate = struct.unpack_from('<I', data, 4)[0]
    return samples, samples / float(rate or SAMPLE_RATE)


def load_library(lib_dir):
    uasset = open(os.path.join(lib_dir, 'VO_CN.uasset'), 'rb').read()
    ubulk = open(os.path.join(lib_dir, 'VO_CN.ubulk'), 'rb').read()
    blocks = parse_blocks(uasset, ubulk)
    media, headers, previews, other = [], [], [], []
    for i, (off, size) in enumerate(blocks):
        blob = ubulk[off:off + size]
        if blob[:4] == b'RIFF' and blob[8:12] == b'WAVE':
            declared = struct.unpack_from('<I', blob, 4)[0] + 8
            info = wem_info(blob)
            if declared == size and info:
                media.append(dict(block=i, off=off, size=size, samples=info[0], dur=info[1]))
            else:
                previews.append(dict(block=i, off=off, size=size))
        elif blob[:4] == b'BKHD':
            headers.append(dict(block=i, off=off, size=size, data=blob))
        else:
            other.append(dict(block=i, off=off, size=size))
    return ubulk, blocks, media, headers, previews, other


def load_refs(path):
    refs = collections.defaultdict(dict)
    for line in open(path, encoding='utf-8').read().splitlines()[1:]:
        p = line.split('\t')
        if len(p) < 6:
            continue
        refs[p[0]][p[1]] = dict(id=int(p[2]), hash=int(p[3]), strategy=p[4], debug=p[6] if len(p) > 6 else '')
    return refs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lib', default=os.path.join(BASE, 'build', 'libs'))
    ap.add_argument('--refs', default=os.path.join(BASE, 'data', 'external_media_refs.tsv'))
    ap.add_argument('--durations', default=os.path.join(BASE, 'data', 'durations.json'))
    ap.add_argument('--out', default=os.path.join(BASE, 'data', 'library_map.json'))
    ap.add_argument('--tol', type=float, default=0.003, help='duration tolerance, seconds')
    args = ap.parse_args()

    ubulk, blocks, media, headers, previews, other = load_library(args.lib)
    print(f'blocks={len(blocks)} media={len(media)} headers={len(headers)} '
          f'previews={len(previews)} other={len(other)}')

    durations = json.load(open(args.durations, encoding='utf-8'))
    refs = load_refs(args.refs)

    by_dur = collections.defaultdict(list)
    for i, m in enumerate(media):
        by_dur[round(m['dur'], 4)].append(i)

    result = {}
    stats = collections.Counter()
    for ev, langs in refs.items():
        cn = langs.get('Chinese')
        if not cn:
            continue
        pat = struct.pack('<I', cn['id'])
        hits = [i for i, h in enumerate(headers) if pat in h['data']]
        zh = durations.get(ev, [0.0, 0.0])[0]
        cands = []
        if zh > 0:
            for key, lst in by_dur.items():
                if abs(key - zh) <= args.tol:
                    cands += lst
        result[ev] = dict(media_id=cn['id'], headers=hits, duration=zh,
                          candidates=[dict(block=media[i]['block'], size=media[i]['size'],
                                           dur=media[i]['dur']) for i in cands])
        stats[(len(hits), len(cands))] += 1

    json.dump(result, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('written', args.out)
    print('(headers found, duration candidates) -> events')
    for k, v in sorted(stats.items()):
        print('  ', k, v)


if __name__ == '__main__':
    main()
