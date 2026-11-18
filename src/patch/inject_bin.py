"""Binary injector: replace the Chinese media of an AkAudioEvent with a Japanese .wem.

Why binary patching
-------------------
The voice media live in the .ubulk of the AkAudioEvent package. CUE4Parse can read that
layout but it cannot write a modified instance back: its SavePackage() re-reads the
package from the provider, so any change made to the in-memory objects is lost. The
files are therefore patched directly.

Layout of the .ubulk
--------------------
The .ubulk is a sequence of contiguous blocks. For each language (Chinese, then
English(US)) there are three of them:

    event header   BKHD + HIRC chunks, the Wwise bookmark of the event
    preview        the first bytes of the media, so the engine can start playing
                   before the whole file has been read
    media          the .wem itself

For Vo_Plot_2D_Animation1_Hun_10_1 the blocks are:

    [0:703]      event header
    [703:9251]   preview   (8548 bytes)
    [9251:61449] Chinese media (52198 bytes)
    [61449:62152] event header
    [62152:67890] preview  (5738 bytes)
    [67890:114920] English media (47030 bytes)

The .uasset holds the table that describes those blocks: six entries of 32 bytes, at
offset 384. Each entry is [-1, -1, SizeOnDisk, 0, Flags, 0, OffsetInFile, 0], so the
size of block k is at 384 + 32k + 8. The blocks tile the .ubulk without gaps, so their
offsets follow from their sizes: block k starts where block k-1 ends.

(Verified on Vo_Plot_2D_Animation1_Hun_10_1: 703 / 8548 / 52198 / 703 / 5738 / 47030
bytes, which add up to the exact 114920 bytes of the .ubulk.)

Replacing the Chinese media with a differently sized one therefore means:
  * writing the new media in place of the old one,
  * moving everything that follows it,
  * rewriting the size of the Chinese media and the offsets of the English blocks.

The blocks are located through the table, and the result is verified before it is
written, so a package with a different layout is refused instead of being corrupted.
"""
import argparse, json, os, struct

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEM_DIR = os.path.join(BASE, 'out', 'jp_wem')
RAW_DIR = os.path.join(BASE, 'build', 'raw')

# The bulk-data table of the .uasset: a list of 32-byte entries, each of them
# [-1, -1, SizeOnDisk, 0, Flags, 0, EndOffset, 0]. The blocks are contiguous, so the
# size of a block is enough to know where it starts; the recorded end offset is the
# sum of the sizes up to that block. Both the position of the table and the number of
# entries depend on the asset, so the table is located by its signature.
TABLE_STRIDE = 32
TABLE_MARKER = -1        # the two int32 that open every entry
TABLE_FLAGS = 66817      # the flags value that follows the size
TABLE_SIZE_POS = 8       # SizeOnDisk inside the entry
TABLE_END_POS = 24       # offset where the next block starts


def find_table(uasset):
    """Locate the bulk-data table and return (base, [sizes])."""
    for base in range(0, len(uasset) - TABLE_STRIDE, 4):
        if struct.unpack_from('<ii', uasset, base) != (TABLE_MARKER, TABLE_MARKER):
            continue
        sizes = []
        offset = 0
        for k in range(12):
            o = base + k * TABLE_STRIDE
            if o + 20 > len(uasset):
                break
            if struct.unpack_from('<ii', uasset, o) != (TABLE_MARKER, TABLE_MARKER):
                break
            if struct.unpack_from('<i', uasset, o + 16)[0] != TABLE_FLAGS:
                break
            size = struct.unpack_from('<i', uasset, o + TABLE_SIZE_POS)[0]
            if size < 0:
                break
            sizes.append(size)
            offset += size
        if len(sizes) >= 2:
            return base, sizes
    raise ValueError('bulk-data table not found')


def parse_table(uasset, ubulk_size=None):
    """[(size, offset)] of the blocks described by the .uasset."""
    base, sizes = find_table(uasset)
    blocks = []
    offset = 0
    for size in sizes:
        blocks.append((size, offset))
        offset += size
    return blocks


def check_layout(blocks, ubulk):
    """The blocks must tile the .ubulk without gaps or overlaps."""
    expected = 0
    for k, (size, off) in enumerate(blocks):
        if off != expected:
            raise ValueError(f'block {k} starts at {off}, expected {expected}')
        expected += size
    if expected != len(ubulk):
        raise ValueError(f'blocks cover {expected} bytes, the .ubulk is {len(ubulk)}')


def check_table(uasset, table_base, blocks, ubulk_size):
    """The end offsets recorded in the table must match the blocks."""
    expected = 0
    for k, (size, _off) in enumerate(blocks):
        expected += size
        if k == len(blocks) - 1:
            break                       # the last entry has no successor
        stored = struct.unpack_from('<i', uasset, table_base + k * TABLE_STRIDE + TABLE_END_POS)[0]
        if stored != expected:
            raise ValueError(f'table: block {k} ends at {stored}, expected {expected}')


def patch(event, wem_path, out_dir, raw_dir=RAW_DIR):
    with open(os.path.join(raw_dir, event + '.uasset'), 'rb') as f:
        uasset = bytearray(f.read())
    ubulk_path = os.path.join(raw_dir, event + '.ubulk')
    if not os.path.exists(ubulk_path):
        raise FileNotFoundError(f'{event}: no .ubulk (the media is not stored separately)')
    with open(ubulk_path, 'rb') as f:
        ubulk = bytearray(f.read())

    blocks = parse_table(uasset)
    check_layout(blocks, ubulk)
    table_base, _sizes = find_table(uasset)
    check_table(uasset, table_base, blocks, len(ubulk))

    # The blocks are, for each language, the event header (BKHD + HIRC), a preview
    # copy of the media and the media itself. Some events only have the Chinese
    # variant, so there can be four blocks instead of six.
    # The media blocks hold a complete RIFF/WAVE file; the previews also start with a
    # RIFF header but are truncated, so the size they declare inside the header is
    # larger than the block they occupy.
    media = [k for k, (size, off) in enumerate(blocks)
             if ubulk[off:off + 4] == b'RIFF' and ubulk[off + 8:off + 12] == b'WAVE'
             and struct.unpack_from('<I', ubulk, off + 4)[0] + 8 == size]
    if not media:
        raise ValueError(f'{event}: no media block')
    if len(media) > 2:
        raise ValueError(f'{event}: expected at most 2 media blocks, found {len(media)}')
    k_cn_media = media[0]
    k_en_media = media[1] if len(media) > 1 else None
    # each media is preceded by its preview copy
    k_cn_preview = k_cn_media - 1
    if k_cn_preview < 0:
        raise ValueError(f'{event}: missing preview block')

    cn_size, cn_off = blocks[k_cn_media]
    cn_preview_size, cn_preview_off = blocks[k_cn_preview]

    with open(wem_path, 'rb') as f:
        new_media = f.read()
    if new_media[:4] != b'RIFF' or new_media[8:12] != b'WAVE':
        raise ValueError(f'{event}: the replacement is not a RIFF/WAVE file')

    # the preview is a truncated copy of the media; it shrinks if the media does
    new_cn_preview_size = min(cn_preview_size, len(new_media))

    # --- new layout ------------------------------------------------------
    # the Chinese media keeps its place; everything that follows it moves
    # the blocks are rebuilt from their sizes, so the new offsets are the running
    # total of the new sizes
    new_sizes = [size for (size, _off) in blocks]
    new_sizes[k_cn_preview] = new_cn_preview_size
    new_sizes[k_cn_media] = len(new_media)

    new_blocks = []
    offset = 0
    for size in new_sizes:
        new_blocks.append((size, offset))
        offset += size

    new_ubulk = bytearray()
    for k, (size, off) in enumerate(new_blocks):
        if k == k_cn_preview:
            new_ubulk += new_media[:new_cn_preview_size]
        elif k == k_cn_media:
            new_ubulk += new_media
        else:
            # the other blocks keep their bytes, they only move
            old_size, old_off = blocks[k]
            new_ubulk += ubulk[old_off:old_off + old_size]

    # --- rewrite the table ------------------------------------------------
    # the table stores the size of every block and the offset where the next one
    # starts, so both the size of the Chinese media and the end offsets of the blocks
    # that follow it have to be rewritten
    def set_size(k, value):
        struct.pack_into('<i', uasset, table_base + k * TABLE_STRIDE + TABLE_SIZE_POS, value)

    def set_end(k, value):
        struct.pack_into('<i', uasset, table_base + k * TABLE_STRIDE + TABLE_END_POS, value)

    set_size(k_cn_media, len(new_media))
    set_size(k_cn_preview, new_cn_preview_size)
    # the end offsets of the blocks follow from the new sizes
    for k in range(len(new_blocks) - 1):
        set_end(k, new_blocks[k][1] + new_blocks[k][0])

    # --- verify -----------------------------------------------------------
    check_layout(new_blocks, new_ubulk)
    size, off = new_blocks[k_cn_media]
    if new_ubulk[off:off + size] != new_media:
        raise ValueError(f'{event}: the Chinese media does not match the replacement')

    # the table written back must describe the new layout
    relaid = parse_table(uasset)
    check_layout(relaid, new_ubulk)
    check_table(uasset, table_base, relaid, len(new_ubulk))
    if relaid[k_cn_media][0] != len(new_media):
        raise ValueError(f'{event}: the table was not updated')

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, event + '.uasset'), 'wb') as f:
        f.write(uasset)
    with open(os.path.join(out_dir, event + '.ubulk'), 'wb') as f:
        f.write(new_ubulk)

    return dict(event=event, old_cn_size=cn_size, new_cn_size=len(new_media),
                old_ubulk=len(ubulk), new_ubulk=len(new_ubulk),
                blocks=new_blocks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--event', required=True)
    ap.add_argument('--wem', default=None)
    ap.add_argument('--out', default=os.path.join(BASE, 'build', 'patched'))
    ap.add_argument('--raw', default=RAW_DIR)
    args = ap.parse_args()

    wem = args.wem or os.path.join(WEM_DIR, args.event + '.wem')
    info = patch(args.event, wem, args.out, args.raw)
    info.pop('blocks', None)
    print(json.dumps(info))


if __name__ == '__main__':
    main()
