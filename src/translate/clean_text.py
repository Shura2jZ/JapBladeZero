import csv, json, os, re

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
rows = list(csv.DictReader(open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8')))

TAGS = re.compile(r'</?[A-Za-z][A-Za-z0-9_]*>|</?>')
KANA = re.compile(r'[\u3040-\u30ff\u3000-\u303f\uff00-\uffef]')
KANJI_OK = re.compile(r'[\u4e00-\u9fff]')

# Characters that Chinese-only text may still contain after MT: those cannot be read by VOICEVOX.
# Keep only kanji that also exist in Japanese usage; drop the rest.
JAPANESE_ONLY_BLOCK = set('这那会说个吗吧呢啊哦嗯呀么呗啦嘛噢哟呵嘿喂哇嘞诶')

def clean_for_tts(text):
    t = TAGS.sub('', text)
    # drop remaining CJK ideographs that are Chinese-specific function words
    t = ''.join(ch for ch in t if ch not in JAPANESE_ONLY_BLOCK)
    # collapse whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    return t

n_changed = 0
out_rows = []
for r in rows:
    jp = r['japanese_text']
    c = clean_for_tts(jp)
    if c != jp:
        n_changed += 1
        r['japanese_text_tts'] = c
    else:
        r['japanese_text_tts'] = c
    out_rows.append(r)

with open(os.path.join(BASE, 'data', 'manifest_jp.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(out_rows)

empty = [r for r in out_rows if r['japanese_text'].strip() and not r['japanese_text_tts'].strip()]
print('rows', len(out_rows), 'modified by cleaning', n_changed, 'emptied', len(empty))
with_tags = [r for r in out_rows if '<' in r['japanese_text']]
print('rows containing tags:', len(with_tags))
for r in with_tags[:5]:
    print('  ', r['event_name'], '|', r['japanese_text'][:70], '->', r['japanese_text_tts'][:60])
