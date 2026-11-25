"""Generates the benchmark takes for one or several engines.

    python src/tts/benchmark_generate.py --engine voicevox

Writes out/benchmark/<engine>/<event>.wav for every line of
data/benchmark_set.json. Never touches out/jp_events (the production WAVs).
"""
import argparse, csv, json, os, sys, wave, io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE
from tts.voices import speaker_for

bench = json.load(open(os.path.join(BASE, 'data', 'benchmark_set.json'), encoding='utf-8'))
rows = {r['event_name']: r for r in csv.DictReader(
    open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8'))}

# rough per-bucket direction: the same text should not be read the same way
DIRECTION = {
    'old_man':   {'intonation': 0.8, 'speed': 0.93},
    'young_man': {'intonation': 1.2, 'speed': 1.0},
    'woman':     {'intonation': 1.15},
    'shout':     {'intonation': 1.6, 'volume': 1.4, 'speed': 1.05},
    'long':      {'intonation': 1.1},
    'short':     {},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--engine', default='voicevox')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    if args.engine == 'voicevox':
        from tts.engines.voicevox import Engine
        engine = Engine()
    else:
        raise SystemExit(f'moteur inconnu : {args.engine}')

    if not engine.available():
        raise SystemExit(f'{engine.name}: indisponible')

    outdir = os.path.join(BASE, 'out', 'benchmark', engine.name)
    os.makedirs(outdir, exist_ok=True)

    items = list(bench.items())
    if args.limit:
        items = items[:args.limit]
    ok = fail = 0
    for event, meta in items:
        r = rows.get(event)
        if not r:
            continue
        text = (r.get('japanese_text_tts') or r.get('japanese_text') or '').strip()
        opts = dict(DIRECTION.get(meta.get('bucket'), {}))
        speaker = speaker_for(event)
        try:
            res = engine.synthesize(text, opts, speaker=speaker)
            wav, sr = res
            p = os.path.join(outdir, event + '.wav')
            with wave.open(p, 'wb') as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(wav)
            ok += 1
        except Exception as e:
            print('ERR', event, repr(e)[:100])
            fail += 1
    print(f'{engine.name}: {ok} prises, {fail} echecs -> {outdir}')


if __name__ == '__main__':
    main()
