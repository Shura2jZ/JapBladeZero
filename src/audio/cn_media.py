"""Finds the Chinese media of a voice event in the game's packages.

The media of an event live in its own package (a `.uasset` holding the table of
the bulk data blocks and a `.ubulk` holding the blocks), or in the Wwise
library `VO_CN`. The blocks are found through the table of the `.uasset`: the
block whose RIFF header declares exactly its own size is the media, the one
that declares more is a truncated preview of it.

Usage:
    from cn_media import chinese_media
    blob = chinese_media('Vo_Plot_Prologue_04_GuanDao_LaoGenTou_1')
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE, build

TABLE_STRIDE = 32
TABLE_MARKER = -1
TABLE_FLAGS = 66817
TABLE_SIZE_POS = 8


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
            if struct.unpack_from('<i', uasset, o + TABLE_SIZE_POS)[0] < 0:
                break
            count += 1
        if count >= 2 and (best is None or count > best[1]):
            best = (base, count)
    if best is None:
        raise ValueError('bulk data table not found')
    return best


def blocks_of(uasset, ubulk_size=None):
    """[(offset, size)] of every block, in the order of the table."""
    base, count = find_table(uasset)
    blocks, offset = [], 0
    for k in range(count):
        size = struct.unpack_from('<I', uasset, base + k * TABLE_STRIDE + TABLE_SIZE_POS)[0]
        blocks.append((offset, size))
        offset += size
    if ubulk_size is not None and offset != ubulk_size:
        raise ValueError('blocks cover %d bytes, the .ubulk is %d' % (offset, ubulk_size))
    return blocks


def is_media(blob, size):
    return (blob[:4] == b'RIFF' and blob[8:12] == b'WAVE'
            and struct.unpack_from('<I', blob, 4)[0] + 8 == size)


def _library_blocks():
    """event -> block index of the library, for the media it holds."""
    path = os.path.join(BASE, 'data', 'library_map.json')
    if not os.path.exists(path):
        return {}
    raw = json.load(open(path, encoding='utf-8'))
    out = {}
    for ev, info in raw.items():
        cands = info.get('candidates') or []
        if cands:
            out[ev] = cands[0]['block']
    return out


def chinese_media(event, raw_dir=None, lib_dir=None):
    """The Chinese media of an event, or None when the event has none."""
    raw_dir = raw_dir or build('raw_all')
    up = os.path.join(raw_dir, event + '.uasset')
    bp = os.path.join(raw_dir, event + '.ubulk')
    if os.path.exists(up) and os.path.exists(bp):
        uasset = open(up, 'rb').read()
        ubulk = open(bp, 'rb').read()
        for off, size in blocks_of(uasset, len(ubulk)):
            blob = ubulk[off:off + size]
            if is_media(blob, size):
                return blob
        return None

    # the media lives in the Wwise library
    lib_dir = lib_dir or build('libs')
    block = _library_blocks().get(event)
    if block is None:
        return None
    uasset = open(os.path.join(lib_dir, 'VO_CN.uasset'), 'rb').read()
    ubulk = open(os.path.join(lib_dir, 'VO_CN.ubulk'), 'rb').read()
    blocks = blocks_of(uasset, len(ubulk))
    if block >= len(blocks):
        return None
    off, size = blocks[block]
    blob = ubulk[off:off + size]
    return blob if is_media(blob, size) else None
