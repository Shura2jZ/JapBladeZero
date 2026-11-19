"""Builds the IoStore container of the mod.

The game does not ship loose packages: its content lives in an IoStore container
(ProjectPBZ-Windows.pak/.ucas/.utoc), compressed with Oodle and encrypted. A loose
.pak cannot override it, the packages are resolved through the container.

The container is therefore rebuilt with retoc (https://github.com/trumank/retoc):
the patched files are written as raw chunks, named after their chunk id, and the
manifest gives the path of every chunk.

Usage:
    python src/patch/build_container.py --files <list> [--out <dir>] [--limit N]
"""
import argparse, json, os, shutil, subprocess, sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RETOC = os.environ.get('RETOC', r'C:\tools\retoc\retoc.exe')
CHUNKIDS = os.path.join(BASE, 'tools', 'csharp', 'chunkids', 'bin', 'Release', 'net10.0', 'chunkids.exe')
TOC_VERSION = 'ReplaceIoChunkHashWithIoHash'
MOUNT_POINT = '../../../'


def chunk_ids(paths, work):
    """Computes the chunk id of every path with the CUE4Parse helper."""
    listing = os.path.join(work, 'paths.txt')
    with open(listing, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(paths) + '\n')
    out = subprocess.run([CHUNKIDS, listing], capture_output=True, text=True, check=True).stdout
    result = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        path, chunk_id, _pkg = line.split('\t')
        result[path] = chunk_id
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--files', required=True, help='list of "game path<TAB>local file"')
    ap.add_argument('--out', default=r'E:\PBZ_Mod')
    ap.add_argument('--name', default='PBZJapaneseVoice_9_P')
    ap.add_argument('--work', default=os.path.join(BASE, 'build', 'container'))
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    entries = []
    for line in open(args.files, encoding='utf-8'):
        if not line.strip():
            continue
        path, local = line.rstrip('\n').split('\t')[:2]
        entries.append((path, local))
    if args.limit:
        entries = entries[:args.limit]
    print(f'{len(entries)} files to pack')

    work = args.work
    if os.path.isdir(work):
        shutil.rmtree(work)
    chunks = os.path.join(work, 'chunks')
    os.makedirs(chunks)

    ids = chunk_ids([p for p, _ in entries], work)
    manifest_paths = {}
    total = 0
    for path, local in entries:
        chunk_id = ids.get(path)
        if chunk_id is None:
            print(f'! no chunk id for {path}')
            continue
        data = open(local, 'rb').read()
        with open(os.path.join(chunks, chunk_id), 'wb') as f:
            f.write(data)
        manifest_paths[chunk_id] = MOUNT_POINT + path
        total += len(data)
    print(f'{len(manifest_paths)} chunks, {total / 1e6:.0f} Mo')

    manifest = {'chunk_paths': manifest_paths, 'version': TOC_VERSION, 'mount_point': MOUNT_POINT}
    with open(os.path.join(work, 'manifest.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, indent=1)

    os.makedirs(args.out, exist_ok=True)
    utoc = os.path.join(args.out, args.name + '.utoc')
    cmd = [RETOC, 'pack-raw', work, utoc]
    print(' '.join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout[-2000:])
    if res.returncode != 0:
        print(res.stderr[-2000:])
        sys.exit(1)

    for ext in ('.utoc', '.ucas'):
        p = os.path.join(args.out, args.name + ext)
        if os.path.exists(p):
            print(f'{p}  {os.path.getsize(p) / 1e6:.0f} Mo')


if __name__ == '__main__':
    main()
