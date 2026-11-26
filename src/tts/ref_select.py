"""Chooses the reference line for each benchmark event (GPT-SoVITS requires a
3-10 s prompt).

Rule: among the SAME character's events (3 <= duration <= 10 s), pick the one
whose measured profile is closest to the line to synthesize (f0 median and
duration). Never use the line itself as its own prompt.

    python src/tts/ref_select.py     # writes data/benchmark_refchoice.json
"""
import csv, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE

bench = json.load(open(os.path.join(BASE, 'data', 'benchmark_set.json'), encoding='utf-8'))
speakers = json.load(open(os.path.join(BASE, 'data', 'event_speaker.json'), encoding='utf-8'))
profiles = json.load(open(os.path.join(BASE, 'data', 'cn_voice_profiles.json'), encoding='utf-8'))['events']
rows = {r['event_name']: r for r in csv.DictReader(
    open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8'))}
durations = json.load(open(os.path.join(BASE, 'data', 'durations.json'), encoding='utf-8'))

# index of the game's whole cast: character -> [(event, f0, dur)]
cast = {}
for r in csv.DictReader(open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8')):
    ev = r['event_name']
    sp = speakers.get(ev)
    if not sp:
        continue
    p = profiles.get(ev)
    d = (durations.get(ev, [0, 0]) or [0, 0])[0]
    if p and 3.0 <= d <= 10.0:
        cast.setdefault(sp, []).append((ev, p.get('f0_median'), d))

out = {}
for ev, meta in bench.items():
    sp = speakers.get(ev)
    p = profiles.get(ev)
    d = (durations.get(ev, [0, 0]) or [0, 0])[0]
    f0 = p.get('f0_median') if p else None
    cands = [c for c in cast.get(sp, []) if c[0] != ev]
    if not cands:
        out[ev] = None
        continue
    # distance on the measured profile: f0 and duration, duration is the weak term
    def dist(c):
        e2, f2, d2 = c
        g = abs((f2 or f0 or 0) - (f0 or 0)) / max(f0, 1) if f0 else 0.0
        t = abs(d2 - d) / max(d, 1)
        return g * 3 + t
    best = min(cands, key=dist)
    out[ev] = {'ref_event': best[0], 'ref_f0': best[1], 'ref_dur': best[2]}

json.dump(out, open(os.path.join(BASE, 'data', 'benchmark_refchoice.json'), 'w'),
          ensure_ascii=False, indent=1)
n = sum(1 for v in out.values() if v)
print(f'{n}/{len(out)} lignes avec une reference du meme personnage (3-10 s)')
