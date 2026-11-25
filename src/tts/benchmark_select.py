"""Selects a representative benchmark set for the TTS engine comparison.

The set covers the acoustic and dramatic variety of the game: old men, young
women, combat shouts, long emotional lines, short barks. The selection is
measured (gender, F0, duration), not hand-picked.

    python src/tts/benchmark_select.py          # writes data/benchmark_set.json
"""
import csv, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE

rows = [r for r in csv.DictReader(open(os.path.join(BASE, 'data', 'manifest_jp.csv'),
                                       encoding='utf-8'))
        if (r.get('japanese_text_tts') or r.get('japanese_text') or '').strip()
        and r.get('status') == 'ok']
durations = json.load(open(os.path.join(BASE, 'data', 'durations.json'), encoding='utf-8'))
profiles = json.load(open(os.path.join(BASE, 'data', 'cn_voice_profiles.json'), encoding='utf-8'))
_profiles_events = profiles.get('events', {})
_profiles_chars = profiles.get('characters', {})
speakers = json.load(open(os.path.join(BASE, 'data', 'event_speaker.json'), encoding='utf-8'))


def f0_of(event):
    p = _profiles_events.get(event)
    if p:
        return p.get('f0_median')
    sp = speakers.get(event)
    if not sp:
        return None
    p = _profiles_chars.get(sp)
    return (p or {}).get('f0_median')


def take(events, n):
    out = []
    for e in events:
        if e not in seen:
            seen.add(e)
            out.append(e)
            if len(out) >= n:
                break
    return out


seen = set()
buckets = {'old_man': [], 'young_man': [], 'woman': [], 'shout': [], 'long': [], 'short': []}
for r in rows:
    e = r['event_name']
    d = (durations.get(e, [0, 0]) or [0, 0])[0]
    f0 = f0_of(e)
    if f0 and f0 < 95:
        buckets['old_man'].append((e, d))
    elif f0 and f0 < 145:
        buckets['young_man'].append((e, d))
    elif f0 and f0 >= 200:
        buckets['woman'].append((e, d))
    if 'Battle' in e or 'Yell' in e:
        buckets['shout'].append((e, d))
    if d > 6.0:
        buckets['long'].append((e, d))
    if 0.8 < d < 1.8:
        buckets['short'].append((e, d))

plan = [('old_man', 8), ('young_man', 8), ('woman', 8), ('shout', 6), ('long', 6), ('short', 4)]
picked = {}
for name, n in plan:
    picked[name] = take([e for e, _ in sorted(buckets[name], key=lambda x: -x[1])], n)

out = {}
for name, events in picked.items():
    for e in events:
        out[e] = {'bucket': name, 'character': speakers.get(e),
                  'duration_zh': (durations.get(e, [0, 0]) or [0, 0])[0]}
json.dump(out, open(os.path.join(BASE, 'data', 'benchmark_set.json'), 'w'),
          ensure_ascii=False, indent=1)
print(f'{len(out)} lignes retenues :',
      ', '.join(f'{k}={len(v)}' for k, v in picked.items()))
