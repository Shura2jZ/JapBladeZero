"""Assigns a VOICEVOX style to every character of the game.

Where the identity comes from
-----------------------------
The game knows who speaks: ``DT_LocTable`` has a ``Speaker`` column holding a
character code (``Character_Main_1``, ``Character_Imp_18``, ...) next to the
``Audio`` column that names the voice event. That mapping covers 99.7% of the
patched events, and it is the only official source: the event name only hints
at the character.

The gender is read from the Japanese text of the lines themselves (first
person pronouns: 俺/僕 are male, 私/あたし are female). The text is the
official one (see src/translate/official_text.py), so it is what the voice
has to say. The Chinese cannot be used: 他 and 她 are written differently but
sound the same, so they tell nothing.

Voices
------
The engine exposes 44 voices and 128 styles; the ``speaker`` parameter of the
HTTP API is a style id, and those ids change between engine versions, so they
are resolved from data/voicevox_styles.json by (voice, style) name.

The main cast keeps the voice the earlier per-prefix mapping gave it (that
mapping was already right for them: 左殇 was male, 魂 female, ...). The
secondary cast is spread over the styles of its gender, so that two characters
rarely sound alike.

Usage:
    python src/tts/voice_assign.py [--out data/character_voices.json]
"""
import argparse, csv, json, os, re, sys, collections

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE

#: the voices of the main cast, by (voice, style) name
#: 魂 (Main_1) is male, 左殇 (Main_2) and 慕小葵 (Main_3) are female
KEEP = {
    'Character_Main_1': ('剣崎雌雄', 'ノーマル'),
    'Character_Main_2': ('琴詠ニア', 'ノーマル'),
    'Character_Main_3': ('あんこもん', 'ノーマル'),
}

#: the first person pronouns, per gender
MALE = re.compile(r'俺|僕|わし|坊や|殿')
FEMALE = re.compile(r'あたし|私|うち|姉御|姉|妹|母|妾')


def guess_gender(texts):
    """Male or female, from the first person pronouns of the lines."""
    m = sum(len(MALE.findall(t)) for t in texts)
    f = sum(len(FEMALE.findall(t)) for t in texts)
    if m > f:
        return 'M'
    if f > m:
        return 'F'
    return None


def old_voice(event, prefix_speaker, default):
    """The style the earlier per-prefix mapping gave this event."""
    m = re.match(r'Vo_(?:Plot_)?(.+)$', event)
    rest = m.group(1) if m else ''
    for key in sorted(prefix_speaker, key=len, reverse=True):
        if rest.startswith(key + '_') or rest == key or rest.lower().startswith(key.lower()):
            return prefix_speaker[key]
    return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(BASE, 'data', 'character_voices.json'))
    a = ap.parse_args()

    ev2sp = json.load(open(os.path.join(BASE, 'data', 'event_speaker.json'), encoding='utf-8'))
    rows = list(csv.DictReader(open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8')))
    vm = json.load(open(os.path.join(BASE, 'data', 'voice_map.json'), encoding='utf-8'))
    styles = json.load(open(os.path.join(BASE, 'data', 'voicevox_styles.json'), encoding='utf-8'))

    by_name = {f'{v["voice"]}|{v["style"]}': v for v in styles.values()}

    # how many lines each character speaks, and the voice it would have had
    stats = collections.defaultdict(lambda: {'lines': 0, 'texts': [], 'voices': collections.Counter()})
    for r in rows:
        code = ev2sp.get(r['event_name'])
        if not code:
            continue
        st = stats[code]
        st['lines'] += 1
        st['texts'].append(r['japanese_text_tts'])
        st['voices'][old_voice(r['event_name'], vm['prefix_speaker'], vm['default_speaker'])] += 1

    # the style pool of each gender
    pool = collections.defaultdict(list)
    for v in styles.values():
        pool[v['gender']].append(v['id'])
    for g in pool:
        pool[g].sort()

    assigned = {}
    used = collections.defaultdict(set)
    for code, label in KEEP.items():
        v = by_name.get(f'{label[0]}|{label[1]}')
        if v is None or code not in stats:
            continue
        assigned[code] = v['id']
        used[v['gender']].add(v['id'])

    # the rest: the biggest characters first, they get the best styles
    order = sorted((c for c in stats if c not in assigned), key=lambda c: -stats[c]['lines'])
    for code in order:
        gender = guess_gender(stats[code]['texts'])
        if gender is None:
            # no pronoun: keep the voice the prefix mapping had, when it is free
            wanted = stats[code]['voices'].most_common(1)[0][0]
            if wanted not in used[None]:
                assigned[code] = wanted
                used[None].add(wanted)
                continue
            gender = 'F'
        free = [s for s in pool[gender] if s not in used[gender]]
        if not free:
            free = list(pool[gender])
        # the style that is already the most used for that character family wins
        style = free[0]
        used[gender].add(style)
        assigned[code] = style

    out = {}
    for code in sorted(assigned, key=lambda c: -stats[c]['lines']):
        out[code] = {
            'style': assigned[code],
            'voice': styles_name(styles, assigned[code]),
            'gender': guess_gender(stats[code]['texts']),
            'lines': stats[code]['lines'],
        }

    json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    by_style = collections.Counter(v['style'] for v in out.values())
    print(f'personnages       : {len(out)}')
    print(f'styles utilises   : {len(by_style)} / {len(styles)}')
    print(f'lignes couvertes  : {sum(v["lines"] for v in out.values())}')
    for code, v in list(out.items())[:20]:
        print(f'   {code:22} {v["gender"] or "?"}  style={v["style"]:4} ({v["voice"]:12}) lignes={v["lines"]}')
    print(f'-> {a.out}')


def styles_name(styles, style_id):
    for v in styles.values():
        if v['id'] == style_id:
            return f'{v["voice"]} {v["style"]}'
    return '?'


if __name__ == '__main__':
    main()
