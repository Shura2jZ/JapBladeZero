"""Parse a compiled UE localization resource (.locres) and dump its entries.

The file is the FTextLocalizationResource written by the cooker
(Runtime/Core/Private/Internationalization/TextLocalizationResource.cpp):

    FGuid   magic (16 o)
    uint8   version              (3 = Optimized_CityHash64_UTF16)
    int64   offset of the string table
    uint32  number of entries
    uint32  number of namespaces
    for each namespace:
        key    (hash + string)
        uint32 key count
        for each key:
            key            (hash + string)
            uint32         hash of the source string
            int32          index in the string table
    [string table]  int32 count, then (string, int32 refcount) per entry

The strings are UTF-16 when the length is negative, UTF-8 otherwise.

Usage:
    python src/translate/parse_locres.py <file.locres> [--out out.json]
"""
import argparse, json, struct, sys


def read_key(buf, pos):
    """Reads a key: uint32 hash then a string (int32 length, negative = UTF-16)."""
    _, pos = struct.unpack_from('<I', buf, pos)
    save_num, pos = struct.unpack_from('<i', buf, pos)
    if save_num < 0:
        n = -save_num
        text = buf[pos:pos + n * 2].decode('utf-16-le', 'replace')
        pos += n * 2
    else:
        text = buf[pos:pos + save_num].decode('utf-8', 'replace')
        pos += save_num
    return text, pos


def read_string(buf, pos):
    """Reads a string of the string table (int32 length, negative = UTF-16)."""
    save_num, pos = struct.unpack_from('<i', buf, pos)
    if save_num < 0:
        n = -save_num
        text = buf[pos:pos + n * 2].decode('utf-16-le', 'replace')
        pos += n * 2
    else:
        text = buf[pos:pos + save_num].decode('utf-8', 'replace')
        pos += save_num
    return text, pos


def parse(path):
    buf = open(path, 'rb').read()
    magic = bytes.fromhex('0e147475674a03fc4a15909dc3377f1b')
    if buf[:16] != magic:
        raise SystemExit(f'{path}: bad magic {buf[:16].hex()}')
    version = buf[16]
    pos = 17
    table_offset = struct.unpack_from('<q', buf, pos)[0]
    pos += 8
    entries_count = struct.unpack_from('<I', buf, pos)[0]
    pos += 4
    namespace_count = struct.unpack_from('<I', buf, pos)[0]
    pos += 4

    # first pass: keys and their index in the string table
    refs = []
    for _ in range(namespace_count):
        namespace, pos = read_key(buf, pos)
        key_count = struct.unpack_from('<I', buf, pos)[0]
        pos += 4
        for _ in range(key_count):
            key, pos = read_key(buf, pos)
            pos += 4                                          # source string hash
            index = struct.unpack_from('<i', buf, pos)[0]
            pos += 4
            refs.append((namespace, key, index))

    # second pass: the string table
    strings = []
    if table_offset >= 0:
        pos = table_offset
        count = struct.unpack_from('<i', buf, pos)[0]
        pos += 4
        for _ in range(count):
            text, pos = read_string(buf, pos)
            refcount = struct.unpack_from('<i', buf, pos)[0]
            pos += 4
            strings.append(text)

    out = {}
    for namespace, key, index in refs:
        if 0 <= index < len(strings):
            out[f'{namespace}:{key}'] = strings[index]
    return version, entries_count, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--out')
    a = ap.parse_args()

    version, entries_count, entries = parse(a.file)
    print(f'version {version}, {entries_count} entries, {len(entries)} avec texte')
    dlg = {k: v for k, v in entries.items() if ':Dlg_' in k}
    ui = {k: v for k, v in entries.items() if ':UI_' in k}
    print(f'  Dlg_*: {len(dlg)}   UI_*: {len(ui)}')
    for k in list(dlg)[:8]:
        print(f'  {k} -> {dlg[k][:60]}')
    if a.out:
        json.dump(entries, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'-> {a.out}')


if __name__ == '__main__':
    main()
