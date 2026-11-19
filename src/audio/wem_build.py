"""Convert the Japanese WAVs into Wwise Vorbis .wem files, ready to be injected.

Pipeline per event:
    24 kHz mono WAV (VOICEVOX)
      -> ffmpeg: 48 kHz mono 16-bit PCM (the rate the game uses)
      -> encode.exe: PCM WAV -> Ogg Vorbis (aoTuV b6.03, VBR q4)
      -> wem.py:     Ogg Vorbis -> Wwise Vorbis .wem (RIFF/0xFFFF + vorb block)

Why 48 kHz: every Chinese media in the game is 48 kHz mono (rate field 0xBB80 in the
fmt chunk). Re-encoding at the game's rate keeps the Wwise decoder on its native path.

The resampling is done with ffmpeg (bundled with imageio_ffmpeg), which avoids
resampling artefacts from a naive 24k->48k sample duplication.

Usage:  python wem_build.py [--limit N] [--quality Q] [--out DIR]
"""
import csv, json, os, shutil, subprocess, sys, tempfile, wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE, out
WAV_DIR = out('jp_events')
TOOLS = os.path.join(BASE, 'tools')
ENCODE = os.path.join(TOOLS, 'encode.exe')
WEMPY = os.path.join(TOOLS, 'wem.py')
DEFAULT_OUT = out('jp_wem')

# The .wem the game ships uses vorbs where: mask 0x4101, and the media is mono 48 kHz.
# encode.exe -> wem.py produce mask 0x4 for mono; the game's own files use 0x4101 for the
# same channel layout, so we patch the channel mask to match the game byte for byte.
GAME_CHANNEL_MASK = 0x4101


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        for cand in ('ffmpeg', 'ffmpeg.exe'):
            p = shutil.which(cand)
            if p:
                return p
        raise SystemExit('ffmpeg introuvable (pip install imageio-ffmpeg)')


def to_48k(src, dst, ff):
    cmd = [ff, '-hide_banner', '-loglevel', 'error', '-y', '-i', src,
           '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', '-f', 'wav', dst]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not os.path.exists(dst):
        raise RuntimeError('ffmpeg failed: ' + r.stderr.decode('utf-8', 'replace')[:300])


def patch_channel_mask(path, mask=GAME_CHANNEL_MASK):
    """Set the fmt chunk's channel mask so the .wem matches the game's layout."""
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
                # layout: tag(2) ch(2) rate(4) avg(4) ba(2) bits(2) cbSize(2) zeros(2) mask(4)
                struct_pack_into(b, p + 20, mask)
            break
        pos += 8 + sz + (sz & 1)
    with open(path, 'wb') as f:
        f.write(bytes(b))
    return True


def struct_pack_into(buf, off, value):
    buf[off:off + 4] = value.to_bytes(4, 'little')


def build_one(event, out_dir, ff, quality, tmpdir):
    wav = os.path.join(WAV_DIR, event + '.wav')
    if not os.path.exists(wav):
        return 'missing'
    raw48 = os.path.join(tmpdir, event + '.48k.wav')
    ogg = os.path.join(tmpdir, event + '.ogg')
    wem = os.path.join(out_dir, event + '.wem')
    to_48k(wav, raw48, ff)
    r = subprocess.run([ENCODE, raw48, ogg, str(quality)], capture_output=True)
    if r.returncode != 0 or not os.path.exists(ogg):
        raise RuntimeError('encode failed: ' + r.stderr.decode('utf-8', 'replace')[:200])
    r = subprocess.run([sys.executable, WEMPY, ogg, wem], capture_output=True)
    if r.returncode != 0 or not os.path.exists(wem):
        raise RuntimeError('wem.py failed: ' + r.stderr.decode('utf-8', 'replace')[:200])
    patch_channel_mask(wem)
    for f in (raw48, ogg):
        try:
            os.remove(f)
        except OSError:
            pass
    return 'ok'


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--quality', type=int, default=9)
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--events', default='', help='comma separated event names')
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    ff = ffmpeg_exe()
    rows = list(csv.DictReader(open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8')))
    names = [r['event_name'] for r in rows if r['status'] == 'ok']
    if args.events:
        wanted = set(args.events.split(','))
        names = [n for n in names if n in wanted]
    if args.limit:
        names = names[:args.limit]

    tmpdir = tempfile.mkdtemp(prefix='wembuild_')
    ok = 0
    errs = []
    for i, ev in enumerate(names):
        out = os.path.join(args.out, ev + '.wem')
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            ok += 1
            continue
        try:
            st = build_one(ev, args.out, ff, args.quality, tmpdir)
            if st == 'ok':
                ok += 1
        except Exception as e:
            errs.append((ev, repr(e)[:150]))
        if (i + 1) % 25 == 0:
            print(f'{i + 1}/{len(names)} built={ok} errors={len(errs)}', flush=True)
    shutil.rmtree(tmpdir, ignore_errors=True)
    print(f'done. built={ok} errors={len(errs)}')
    for ev, msg in errs[:10]:
        print('  ERR', ev, msg)


if __name__ == '__main__':
    main()
