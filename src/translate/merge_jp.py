import csv, json, os, re, glob, unicodedata

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANIFEST = os.path.join(BASE, 'data', 'manifest_jp.csv')
BATCHES = os.path.join(BASE, 'data', 'batches')

rows = list(csv.DictReader(open(MANIFEST, encoding='utf-8')))
tr = json.load(open(os.path.join(BATCHES, 'out_mt.json'), encoding='utf-8'))

CN_PUNCT = '，。！？…、；：“”‘’（）《》'
JP_PUNCT = '、。！？…'

def clean(t):
    if not t:
        return ''
    t = t.strip()
    t = t.replace('　', ' ')
    # collapse MT degeneration: repeated token like われもわれもわれも
    for tok in set(re.findall(r'([\u3040-\u30ff]{2,6})', t)):
        m = re.match(r'(.+?)\1{2,}', t)
        if m:
            t = t[:m.start(1)] + m.group(1)
    # convert chinese punctuation to japanese
    out = []
    for ch in t:
        if ch == '，':
            out.append('、')
        elif ch == '：':
            out.append('：')
        elif ch == '；':
            out.append('；')
        elif ch in '“”':
            out.append('」')
        elif ch in '‘’':
            out.append('』')
        elif ch == '（':
            out.append('（')
        else:
            out.append(ch)
    t = ''.join(out)
    # chinese chars left in output -> keep as is but mark; names are kept
    t = re.sub(r'\s{2,}', ' ', t)
    t = t.replace('・・・', '……')
    return t.strip()

n = 0
for r in rows:
    src = r['chinese_text'].strip()
    if not src:
        continue
    jp = tr.get(src, '').strip()
    if jp:
        r['japanese_text'] = clean(jp)
        n += 1

with open(MANIFEST, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

miss = [r for r in rows if r['chinese_text'].strip() and not r['japanese_text']]
print('translated', n, '/', len(rows), 'missing', len(miss))
for r in miss[:10]:
    print('MISS', r['event_name'], r['chinese_text'])
leftover = [(r['event_name'], r['japanese_text']) for r in rows if re.search(r'[\u4e00-\u9fff]', r['japanese_text'])]
print('rows containing CJK ideographs (names kept):', len(leftover))
for e, t in leftover[:10]:
    print('  ', e, t)
