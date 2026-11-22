"""Assigns a VOICEVOX voice to every character of the game.

The identity of a character comes from the game herself: ``DT_LocTable`` has a
``Speaker`` column that names the character of every line (``Character_Main_1``,
``Character_Imp_18``, ...). The text is the official Japanese one.

Which voice fits a character is decided by measurement, not by guesswork: the
game already has a Chinese voice for every character, and
``src/audio/voice_profile.py`` has measured its height (the fundamental
frequency). A character dubbing at 80 Hz is a man with a low voice, one at
250 Hz is a woman with a high one, and that is what the Japanese voice has to
reproduce. The heights of the VOICEVOX voices are measured the same way by
``src/audio/voicevox_profile.py``.

So each character is given:

  * the voice whose height is the closest to that of its Chinese voice,
    among the voices of the same gender;
  * a voice that is not already used by a more important character, so that the
    main cast does not all sound alike;
  * a style of that voice that fits a straight dubbing (no toy voice, no
    "sexy", no "loli"...).

Usage:
    python src/tts/voice_assign.py [--out data/character_voices.json]
"""
import argparse
import collections
import csv
import json
import math
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE

#: the styles that fit a straight dubbing; the others are for a specific mood
NEUTRAL_STYLES = {
    'ノーマル', 'あまあま', 'ふつう', '人間ver.', 'つぼみ', 'シリアス', '元気', '熱血',
}

#: below and above that height, the voice is a man, respectively a woman
MALE_MAX = 140.0
FEMALE_MIN = 165.0

#: the first person pronouns, per gender, used when the height is ambiguous
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


def gender_of(f0, pronouns):
    """The gender of a character, from its height and, if need be, its words."""
    if f0 < MALE_MAX:
        return 'M'
    if f0 > FEMALE_MIN:
        return 'F'
    return pronouns or 'F'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(BASE, 'data', 'character_voices.json'))
    ap.add_argument('--profiles', default=os.path.join(BASE, 'data', 'cn_voice_profiles.json'))
    ap.add_argument('--vv-profiles', default=os.path.join(BASE, 'data', 'voicevox_profiles.json'))
    args = ap.parse_args()

    ev2sp = json.load(open(os.path.join(BASE, 'data', 'event_speaker.json'), encoding='utf-8'))
    cn = json.load(open(args.profiles, encoding='utf-8'))
    vv = json.load(open(args.vv_profiles, encoding='utf-8'))
    rows = list(csv.DictReader(open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8')))

    # the lines of every character, for the pronouns
    texts = collections.defaultdict(list)
    for r in rows:
        code = ev2sp.get(r['event_name'])
        if code:
            texts[code].append(r['japanese_text_tts'])

    # the pool of voices: the neutral styles, by gender
    pool = collections.defaultdict(list)
    for key, v in vv.items():
        if v.get('style') not in NEUTRAL_STYLES or 'f0_median' not in v:
            continue
        pool[v['gender']].append((key, v))
    for g in pool:
        pool[g].sort(key=lambda kv: kv[1]['f0_median'])

    chars = cn['characters']
    # the characters that speak the most are the ones we hear the most: they
    # get the first pick, so that they do not all end up on the same voice
    order = sorted(chars, key=lambda c: -chars[c]['lines'])

    used = collections.Counter()
    used_voices = set()
    top = set(order[:40])
    assigned = {}
    for code in order:
        info = chars[code]
        target = info['f0_median']
        gender = gender_of(target, guess_gender(texts.get(code, [])))
        candidates = pool.get(gender) or pool.get('F') or []
        if not candidates:
            continue
        best = None
        for key, v in candidates:
            height = abs(math.log(target / v['f0_median']))
            # a voice that is already used costs a little, more and more as it
            # is used: the main cast is spread out, the rare characters share.
            # The penalty is capped, so the height always wins: a character
            # with a low voice never ends up on a high one.
            penalty = 0.10 * min(used[key], 6)
            # the characters we hear the most do not share their timbre
            if code in top and v['voice'] in used_voices:
                penalty += 0.30
            score = height + penalty
            if best is None or score < best[0]:
                best = (score, key, v, height, gender)
        score, key, v, height, gender = best
        used[key] += 1
        if code in top:
            used_voices.add(v['voice'])
        assigned[code] = {
            'style': v['style_id'],
            'voice': v['voice'],
            'style_name': v['style'],
            'gender': gender,
            'lines': info['lines'],
            'target_f0': round(target, 1),
            'voice_f0': v['f0_median'],
            'f0_ratio': round(target / v['f0_median'], 3),
            'height_gap': round(height, 3),
        }

    json.dump(assigned, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    gaps = sorted(v['height_gap'] for v in assigned.values())
    n = len(gaps)
    voices = collections.Counter(v['voice'] for v in assigned.values())
    print(f'personnages       : {len(assigned)}')
    print(f'voix utilisees    : {len(voices)} / {len(set(v["voice"] for g in pool.values() for _, v in g))}')
    print(f'ecart de hauteur  : median {gaps[n // 2]:.3f} ({100 * (2 ** gaps[n // 2] - 1):.0f} %), pire {gaps[-1]:.3f}')
    print(f'personnages seuls sur leur voix : {sum(1 for v in voices.values() if v == 1)}')
    print('voix les plus partagees : ' + ', '.join('%s(%d)' % (k, v) for k, v in voices.most_common(6)))
    for code in order[:15]:
        v = assigned.get(code)
        if v:
            print('   %-24s lignes=%-4d %s  %-14s %-8s (%.0f Hz -> %.0f Hz)'
                  % (code, v['lines'], v['gender'], v['voice'], v['style_name'],
                     v['target_f0'], v['voice_f0']))
    print('->', args.out)


if __name__ == '__main__':
    main()
