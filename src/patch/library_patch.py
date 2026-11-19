"""Replaces the Chinese media of the Wwise library (VO_CN) with the Japanese ones.

Why the library
---------------
Most voice events keep their media in their own package. A few hundred are packaged
differently: their media lives in the Wwise asset library
`ProjectPBZ/Content/Wwise/VO_CN`, and those events have no .ubulk of their own.

How the library is organised
----------------------------
`VO_CN.uasset` holds the bulk data table of the package: one 32 byte entry per block,
    [-1, -1, SizeOnDisk, 0, Flags, 0, EndOffset, 0]
`VO_CN.ubulk` holds the blocks themselves, in the order of that table. Four kinds:

    media    a complete RIFF/WAVE file: the media of a sound
    preview  a truncated copy of a media, so the engine can start playing early
    header   the Wwise event header (BKHD + HIRC) of an event
    padding  filler

The `PackagedFiles` array of the library (read from the cooked data) lists the files
in the same order as the media and header blocks of the .ubulk, and each of them
carries the Wwise hash of the file. That is how the runtime finds a media: hash ->
PackagedFiles index -> block. The very same mapping is used here, so the replacement
lands exactly on the media the game plays.

Replacing a media
-----------------
The new media has a different size, so the .ubulk is rebuilt: every block is copied
at its new offset, the preview of a replaced media is rewritten (its RIFF header
declares the size of the media it previews), and the bulk data table of the .uasset is
updated with the new sizes and offsets.

Usage:
    python src/patch/library_patch.py
"""
import argparse, json, os, struct, sys
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE, build, out
TABLE_STRIDE = 32
TABLE_MARKER = -1
TABLE_FLAGS = 66817
TABLE_SIZE_POS = 8
TABLE_END_POS = 24


def find_table(uasset):
    """(base, count) of the bulk data table of a package."""
    best = None
    for base in range(0, len(uasset) - TABLE_STRIDE, 4):
        if struct.unpack_from('<ii', uasset, base) != (TABLE_MARKER, TABLE_MARKER):
            continue
        count = 0
        for k in range(20000):
            o = base + k * TABLE_STRIDE
            if o + TABLE_STRIDE > len(uasset):
                break
            if struct.unpack_from('<ii', uasset, o) != (TABLE_MARKER, TABLE_MARKER):
                break
            if struct.unpack_from('<I', uasset, o + 16)[0] != TABLE_FLAGS:
                break
            size = struct.unpack_from('<I', uasset, o + 8)[0]
            if size < 0:
                break
            count += 1
        if count >= 2 and (best is None or count > best[1]):
            best = (base, count)
    if best is None:
        raise ValueError('bulk data table not found')
    return best


def read_blocks(uasset, ubulk):
    """[(offset, size)] of every block, in the order of the table."""
    base, count = find_table(uasset)
    blocks, offset = [], 0
    for k in range(count):
        o = base + k * TABLE_STRIDE
        size = struct.unpack_from('<I', uasset, o + TABLE_SIZE_POS)[0]
        blocks.append((offset, size))
        offset += size
    if offset != len(ubulk):
        raise ValueError(f'blocks cover {offset} bytes, the .ubulk is {len(ubulk)}')
    return blocks


def is_media(blob, size):
    if blob[:4] != b'RIFF' or blob[8:12] != b'WAVE':
        return False
    return struct.unpack_from('<I', blob, 4)[0] + 8 == size


def is_preview(blob, size):
    if blob[:4] != b'RIFF' or blob[8:12] != b'WAVE':
        return False
    return struct.unpack_from('<I', blob, 4)[0] + 8 > size


def rewrite_riff_size(blob, new_size):
    """The RIFF header of a preview declares the size of the media it previews."""
    out = bytearray(blob)
    struct.pack_into('<I', out, 4, new_size - 8)
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lib', default=build('libs'), help='VO_CN.uasset + .ubulk')
    ap.add_argument('--wem', default=out('jp_wem'))
    ap.add_argument('--refs', default=os.path.join(BASE, 'data', 'external_media_refs.tsv'))
    ap.add_argument('--packaged', default=os.path.join(BASE, 'data', 'library_packaged_files.tsv'))
    ap.add_argument('--out', default=build('patched_lib'))
    args = ap.parse_args()

    uasset = bytearray(open(os.path.join(args.lib, 'VO_CN.uasset'), 'rb').read())
    ubulk = open(os.path.join(args.lib, 'VO_CN.ubulk'), 'rb').read()
    blocks = read_blocks(uasset, ubulk)
    print(f'{len(blocks)} blocks')

    # the packaged files of the library, in the order of the media and header blocks
    packaged = []
    for line in open(args.packaged, encoding='utf-8').read().splitlines()[1:]:
        p = line.split('\t')
        if len(p) >= 2 and p[1].isdigit():
            packaged.append(int(p[1]))
    print(f'{len(packaged)} packaged files')

    content = []          # media and header blocks, in file order
    for i, (off, size) in enumerate(blocks):
        blob = ubulk[off:off + size]
        if is_media(blob, size) or is_preview(blob, size) or blob[:4] == b'BKHD':
            if not is_preview(blob, size):
                content.append(i)
    print(f'{len(content)} content blocks')

    hash2content = {}
    for i, h in enumerate(packaged):
        if i < len(content):
            hash2content[h] = content[i]

    # the events to replace
    targets = []
    for line in open(args.refs, encoding='utf-8').read().splitlines()[1:]:
        p = line.split('\t')
        if len(p) < 6 or p[1] != 'Chinese':
            continue
        ev, h = p[0], int(p[3])
        blk = hash2content.get(h)
        if blk is None:
            print(f'! {ev}: hash {h} not in the library')
            continue
        wem = os.path.join(args.wem, ev + '.wem')
        if not os.path.exists(wem):
            print(f'! {ev}: no japanese media')
            continue
        targets.append((ev, blk, wem))
    print(f'{len(targets)} media to replace')

    # the preview of a media declares its size: that is how they are paired
    replacements = {}
    for ev, blk, wem in targets:
        replacements[blk] = (ev, open(wem, 'rb').read())
    old_sizes = {blk: blocks[blk][1] for blk in replacements}

    new_ubulk = bytearray()
    new_sizes = []
    for i, (off, size) in enumerate(blocks):
        blob = ubulk[off:off + size]
        if i in replacements:
            ev, data = replacements[i]
            new_ubulk += data
            new_sizes.append(len(data))
            continue
        # a preview of a media that has just been replaced
        #
        # The size of the block must not change: the runtime identifies the blocks by
        # their order (the PackagedFiles array of the library follows that order), so a
        # preview that would turn into a complete copy of the media would shift every
        # index. The block keeps its size, its content becomes the beginning of the
        # new media (zero padded if the new media is shorter), and the RIFF header
        # declares the new size of the media.
        if is_preview(blob, size):
            declared = struct.unpack_from('<I', blob, 4)[0] + 8
            for blk, old in old_sizes.items():
                if old != declared:
                    continue
                data = replacements[blk][1]
                head = rewrite_riff_size(blob[:12], len(data))
                keep = min(size, len(data))
                new_ubulk += head + data[12:keep] + b'\0' * (size - keep)
                new_sizes.append(size)
                break
            else:
                new_ubulk += blob
                new_sizes.append(size)
            continue
        new_ubulk += blob
        new_sizes.append(size)

    # rewrite the bulk data table of the .uasset
    base, count = find_table(uasset)
    if count != len(new_sizes):
        raise ValueError(f'table has {count} entries, {len(new_sizes)} blocks')
    offset = 0
    for k, size in enumerate(new_sizes):
        o = base + k * TABLE_STRIDE
        struct.pack_into('<I', uasset, o + TABLE_SIZE_POS, size)
        if k < len(new_sizes) - 1:
            offset += size
            struct.pack_into('<I', uasset, o + TABLE_END_POS, offset)
        offset += size

    # the table describes the blocks; check that it still tiles the .ubulk
    check = read_blocks(bytes(uasset), bytes(new_ubulk))
    if len(check) != len(new_sizes):
        raise ValueError('the rewritten table does not describe the new .ubulk')

    os.makedirs(args.out, exist_ok=True)
    open(os.path.join(args.out, 'VO_CN.uasset'), 'wb').write(bytes(uasset))
    open(os.path.join(args.out, 'VO_CN.ubulk'), 'wb').write(bytes(new_ubulk))
    print(f'written {args.out}: uasset {len(uasset)} bytes, ubulk {len(ubulk)} -> {len(new_ubulk)} bytes')

    report = {ev: dict(block=blk, old_size=old_sizes[blk], new_size=len(replacements[blk][1]))
              for ev, blk, _ in targets}
    json.dump(report, open(os.path.join(args.out, 'replaced.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
