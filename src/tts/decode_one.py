"""Decodes one Chinese event to 16-bit WAV. Runs in the system python."""
import sys, os, wave
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'src'))
sys.path.insert(0, os.path.join(REPO, 'src', 'audio'))
import pyvgmstream
from cn_media import chinese_media
from wavio import read_wav
ev, outp = sys.argv[1], sys.argv[2]
blob = chinese_media(ev)
if blob is None:
    print('no media'); sys.exit(1)
wav = pyvgmstream.decode_buffer_to_wav_bytes(blob, filename_hint=ev + '.wem')
samples, rate = read_wav(wav)
with wave.open(outp, 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes((samples * 32767).astype('<i2').tobytes())
