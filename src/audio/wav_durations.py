"""Measures the duration of every generated Japanese WAV.

The duration written in ``DT_WwiseVoiceDuration`` must be the one of the media
the engine plays, so this is measured on the WAV that VOICEVOX produced (24 kHz
mono). ``src/audio/wem_durations.py`` then checks that the encoded .wem decodes
to the very same length.

Usage:
    python src/audio/wav_durations.py [--out data/jp_media_durations.json]
"""
import argparse, csv, json, os, sys, wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE, out

WAV_DIR = out('jp_events')
MANIFEST = os.path.join(BASE, 'data', 'manifest_jp.csv')


def wav_duration(path):
    with wave.open(path, 'rb') as w:
        return w.getnframes() / float(w.getframerate())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(BASE, 'data', 'jp_media_durations.json'))
    ap.add_argument('--wav-dir', default=WAV_DIR)
    a = ap.parse_args()

    rows = list(csv.DictReader(open(MANIFEST, encoding='utf-8')))
    durations = {}
    missing = []
    for r in rows:
        event = r['event_name']
        path = os.path.join(a.wav_dir, event + '.wav')
        if not os.path.exists(path):
            missing.append(event)
            continue
        durations[event] = wav_duration(path)

    json.dump(durations, open(a.out, 'w', encoding='utf-8'))
    print(f'{len(durations)} WAV measured, {len(missing)} missing -> {a.out}')
    if missing:
        print('  missing sample:', missing[:5])


if __name__ == '__main__':
    main()
