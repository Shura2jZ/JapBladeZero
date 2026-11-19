"""Re-translate the lines the MT model mangled (decomposed literally or emptied).

The MarianMT zh->ja model handles full sentences well but falls apart on very short
interjections: 可恶 (" damn! ") became 糞! and 什么？ (" what? ") became 何?, which are
semantically wrong for a dub.

Strategy, per line:
  1. re-run the MT with several decoding settings (num_beams, length penalties) and
     keep the candidate that is long enough and looks like natural Japanese,
  2. fall back to a small hand-written lexicon for the recurring interjections
     (the same Chinese phrase always gets the same Japanese line),
  3. as a last resort, keep the model output if nothing better is found.

Only the `japanese_text` and `japanese_text_tts` columns are touched.
"""
import csv, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE, models
MANIFEST = os.path.join(BASE, 'data', 'manifest_jp.csv')
MODEL_DIR = models('opus-mt-zh-ja')

# Manual lexicon for the recurring short interjections the MT model mangles.
# key = chinese source text (normalised), value = (japanese, tts form)
LEXICON = {
    '可恶！': ('くそっ！', 'くそっ！'),
    '可恶!': ('くそっ！', 'くそっ！'),
    '可恶。': ('くそっ……', 'くそっ……'),
    '什么？': ('え？', 'え？'),
    '什么?': ('え？', 'え？'),
    '什么！': ('え！', 'え！'),
    '什么。': ('なんだ……', 'なんだ……'),
    '啊啊啊！': ('ああああ！', 'ああああ！'),
    '啊啊！': ('ああ！', 'ああ！'),
    '啊啊啊啊！': ('ああああああ！', 'ああああああ！'),
    '啊啊啊啊啊啊啊！': ('あああああああああ！', 'あああああああああ！'),
    '哈哈哈哈哈！': ('ははははは！', 'ははははは！'),
    '哈哈哈哈！': ('はははは！', 'はははは！'),
    '哈哈哈哈哈哈！': ('はははははははは！', 'はははははははは！'),
    '哈哈哈哈哈哈！真是可笑至极！': ('はははは！何て滑稽なこと！', 'はははは！何て滑稽なこと！'),
    '……': ('……', '……'),
    '……！': ('……！', '……！'),
    '！': ('！', '！'),
}

MIN_LEN = 3  # below this the line is considered truncated


def is_truncated(text):
    return len((text or '').strip()) < MIN_LEN


def looks_broken(jp):
    """The MT model produced a Chinese residue or a stray latin/kana fragment."""
    if not jp:
        return True
    s = jp.strip()
    if is_truncated(s):
        return True
    # single stray punctuation / lone kana
    if re.fullmatch(r'[・。，,.!?！？ー…\'"「」『』\s]+', s):
        return True
    return False


def translate_batch(texts, batch_size=16):
    """Run MarianMT with a few decoding configurations, return candidate lists."""
    import torch
    from transformers import MarianMTModel, MarianTokenizer

    tok = MarianTokenizer.from_pretrained(MODEL_DIR)
    model = MarianMTModel.from_pretrained(MODEL_DIR)
    model.eval()
    torch.set_num_threads(max(2, (os.cpu_count() or 4) // 2))

    configs = [
        dict(num_beams=5, length_penalty=1.0),
        dict(num_beams=8, length_penalty=1.6),
        dict(num_beams=12, length_penalty=0.8),
    ]
    results = {i: [] for i in range(len(configs))}
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i + batch_size]
        for ci, cfg in enumerate(configs):
            with torch.no_grad():
                enc = tok(chunk, return_tensors='pt', padding=True, truncation=True, max_length=256)
                out = model.generate(**enc, max_new_tokens=128, **cfg)
            dec = tok.batch_decode(out, skip_special_tokens=True)
            results[ci].extend(d.strip() for d in dec)
        print(f'  translated {min(i + batch_size, len(texts))}/{len(texts)}', flush=True)
    return results


def score(cand):
    """Prefer candidates that look like real Japanese dubbing lines."""
    s = (cand or '').strip()
    if not s:
        return -1000.0
    score = 0.0
    score += min(len(s), 20) * 0.5
    # Japanese characters expected
    jp = sum(1 for c in s if '\u3040' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff')
    score += jp * 1.0
    # penalise leftovers that look like raw Chinese (kana are rare in our JP output)
    if re.search(r'[\u4e00-\u9fff]', s):
        score -= 6.0
    if re.fullmatch(r'[・。，,.!?！？…\s]+', s):
        score -= 50.0
    if len(s) < MIN_LEN:
        score -= 40.0
    return score


def main():
    rows = list(csv.DictReader(open(MANIFEST, encoding='utf-8')))
    changed = 0
    to_translate = []
    idxs = []

    for i, r in enumerate(rows):
        cn = (r.get('chinese_text') or '').strip()
        jp = (r.get('japanese_text') or '').strip()
        tts = (r.get('japanese_text_tts') or '').strip()
        if not (looks_broken(jp) or looks_broken(tts)):
            continue
        key = cn.replace(' ', '')
        if key in LEXICON:
            j, t = LEXICON[key]
            r['japanese_text'] = j
            r['japanese_text_tts'] = t
            changed += 1
            continue
        to_translate.append(cn)
        idxs.append(i)

    print(f'lexicon fixed: {changed}, to re-translate: {len(to_translate)}', flush=True)

    if to_translate:
        # unique sources only, to save time
        uniq = sorted(set(to_translate))
        print(f'unique chinese lines: {len(uniq)}', flush=True)
        cands = translate_batch(uniq)
        best = {}
        for ci in range(len(cands)):
            for k, v in enumerate(cands[ci]):
                key = uniq[k]
                if score(v) > score(best.get(key, '')):
                    best[key] = v
        for i, cn in zip(idxs, to_translate):
            key = cn.replace(' ', '')
            jp = best.get(uniq_key := next((u for u in uniq if u.replace(' ', '') == key), key), '')
            if jp and not looks_broken(jp):
                rows[i]['japanese_text'] = jp
                rows[i]['japanese_text_tts'] = jp
                changed += 1
            else:
                print(f'  UNRESOLVED: {cn}', flush=True)

    with open(MANIFEST, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print('manifest updated, rows changed:', changed, flush=True)

    json.dump([r['event_name'] for r in rows if looks_broken(r.get('japanese_text_tts'))],
              open(os.path.join(BASE, 'data', 'still_truncated.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
