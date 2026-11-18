"""Build the Wwise Vorbis .wem for every Japanese line (parallel).

Pipeline per event:
    out/jp_events/<event>.wav   24 kHz mono, VOICEVOX, duration aligned to the Chinese
      -> ffmpeg                48 kHz mono 16-bit PCM (the rate the game uses)
      -> tools/encode.exe      PCM WAV -> Ogg Vorbis (aoTuV b6.03, VBR)
      -> tools/wem.py          Ogg Vorbis -> Wwise Vorbis .wem (RIFF tag 0xFFFF)

The .wem gets its channel mask patched to 0x4101 afterwards, so it matches the
layout of the media the game ships byte for byte.

Usage: python wem_batch.py [--workers N] [--quality Q]
"""
import argparse, csv, json, os, shutil, struct, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WAV_DIR = os.path.join(BASE, 'out', 'jp_events')
OUT_DIR = os.path.join(BASE, 'out', 'jp_wem')
TOOLS = os.path.join(BASE, 'tools')
ENCODE = os.path.join(TOOLS, 'encode.exe')
WEMPY = os.path.join(TOOLS, 'wem.py')
MANIFEST = os.path.join(BASE, 'data', 'manifest_jp.csv')
GAME_CHANNEL_MASK = 0x4101


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        for c in ('ffmpeg', 'ffmpeg.exe'):
            p = shutil.which(c)
            if p:
                return p
        raise SystemExit('ffmpeg introuvable')


def patch_mask(path, mask=GAME_CHANNEL_MASK):
    with open(path, 'rb') as f:
        b = bytearray(f.read())
    if b[0:4] != b'RIFF':
        return False
    pos = 12
    while pos + 8 <= len(b):
        cid = bytes(b[pos:pos + 4])
        sz = int.from_bytes(b[pos + 4:pos + 8], 'little')
        if cid == b'fmt ':
            p = pos + 8
            cb = int.from_bytes(b[p + 16:p + 18], 'little')
            if cb >= 48:
                b[p + 20:p + 24] = mask.to_bytes(4, 'little')
            break
        pos += 8 + sz + (sz & 1)
    with open(path, 'wb') as f:
        f.write(bytes(b))
    return True


def build(event, ff, quality, tmpdir, lock):
    out = os.path.join(OUT_DIR, event + '.wem')
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        return 'skip'
    wav = os.path.join(WAV_DIR, event + '.wav')
    if not os.path.exists(wav):
        return 'missing'
    raw = os.path.join(tmpdir, event + '.48k.wav')
    ogg = os.path.join(tmpdir, event + '.ogg')
    try:
        r = subprocess.run([ff, '-hide_banner', '-loglevel', 'error', '-y', '-i', wav,
                            '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', '-f', 'wav', raw],
                           capture_output=True)
        if r.returncode != 0:
            return 'ffmpeg:' + r.stderr.decode('utf-8', 'replace')[:120]
        r = subprocess.run([ENCODE, raw, ogg, str(quality)], capture_output=True)
        if r.returncode != 0:
            return 'encode:' + r.stderr.decode('utf-8', 'replace')[:120]
        r = subprocess.run([sys.executable, WEMPY, ogg, out], capture_output=True)
        if r.returncode != 0:
            return 'wem:' + r.stderr.decode('utf-8', 'replace')[:120]
        patch_mask(out)
        return 'ok'
    finally:
        for f in (raw, ogg):
            try:
                os.remove(f)
            except OSError:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--quality', type=int, default=9)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    ff = ffmpeg_exe()
    rows = list(csv.DictReader(open(MANIFEST, encoding='utf-8')))
    names = [r['event_name'] for r in rows if r['status'] == 'ok']
    if args.limit:
        names = names[:args.limit]

    tmpdir = tempfile.mkdtemp(prefix='wembatch_')
    counts = {}
    done = [0]

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(build, n, ff, args.quality, tmpdir, None) for n in names]
        for f in futs:
            st = f.result()
            key = 'ok' if st in ('ok', 'skip') else st.split(':')[0]
            counts[key] = counts.get(key, 0) + 1
            done[0] += 1
            if done[0] % 100 == 0:
                print(f'{done[0]}/{len(names)} {counts}', flush=True)

    shutil.rmtree(tmpdir, ignore_errors=True)
    print('done', counts, flush=True)
    for f in os.listdir(OUT_DIR):
        if f.endswith('.wem'):
            os.replace(os.path.join(OUT_DIR, f), os.path.join(OUT_DIR, f))
    total = len(os.listdir(OUT_DIR))
    print('wem in output dir:', total)


if __name__ == '__main__':
    main()
