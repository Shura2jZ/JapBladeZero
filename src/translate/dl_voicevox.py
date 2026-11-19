"""Downloads the VOICEVOX engine.

The engine is a large archive (~250 Mo) and takes a lot of disk space: it is
downloaded on E:, next to the other heavy artefacts, not on the system drive.

    python src/translate/dl_voicevox.py [destination]

The default destination is taken from the PBZ_WORK environment variable, and
falls back to E:/PBZ_Build.
"""

import os
import sys
import urllib.request

URL = 'https://github.com/VOICEVOX/voicevox_engine/releases/download/0.26.2/voicevox_engine-windows-cpu-0.26.2.7z.001'

work = os.environ.get('PBZ_WORK') or 'E:/PBZ_Build'
dst = sys.argv[1] if len(sys.argv) > 1 else os.path.join(work, 'voicevox.7z.001')

os.makedirs(os.path.dirname(dst), exist_ok=True)
req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=120) as r, open(dst, 'wb') as o:
    tot = 0
    while True:
        b = r.read(1 << 20)
        if not b:
            break
        o.write(b)
        tot += len(b)
        if tot % (100 << 20) < (1 << 20):
            print(tot, flush=True)
print('DL DONE', tot, dst)
