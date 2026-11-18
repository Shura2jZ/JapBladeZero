"""Hand-fix the last dozen lines the MT model mangled.

These are the lines that resisted automatic alignment because their Japanese text was
wrong in a way that also changed the speaking time (so no speedScale could match the
Chinese duration). Three failure modes are corrected here:

  1. Chinese <Bold> markers translated literally: 面具 -> 「BOLD」
  2. Chinese quotes 「"组织"」 translated with the wrong bracket pair (」 instead of 「)
  3. Purely literal decomposition of a Chinese list, e.g.
     我记起江湖中有一奇侠妙手老张... -> また,Aは,Aは,Aは,...

Each entry maps the Chinese source to a proper Japanese dub line of a similar length,
so the automatic aligner can then match the duration.
"""
import csv, os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANIFEST = os.path.join(BASE, 'data', 'manifest_jp.csv')

# event -> (japanese text, tts text)
FIXES = {
    'Vo_Plot_DDSD_Mask1_TM_2': (
        '彼はマスクをかぶっていない！',
        '彼はマスクをかぶっていない！'),
    'Vo_Plot_FJZL_2_MSXZ5_Hun_2': (
        'ふと、江湖には奇侠・妙手の老張がいたのを思い出した。千変万化、真偽の判別がつかず、分身/Amenoまでいくつもいたようだ。',
        'ふと、江湖には奇侠・妙手の老張がいたのを思い出した。千変万化、真偽の判別がつかず、分身までいくつもいたようだ。'),
    'Vo_Plot_LJC_1_LaoGenTou1_Hun_9': (
        'なぜ、町内へ入る必要があるんだ？',
        'なぜ、町内へ入る必要があるんだ？'),
    'Vo_Plot_PZ_HuoLiuXing_Hun_1': (
        '「ボールド」は「ボールド」か？',
        '「ボールド」は「ボールド」か？'),
    'Vo_Plot_PZ_LJGZ_LanShaoDi1_LanShaoDi_2': (
        '坊主は、兄と妹の二人だ。',
        '坊主は、兄と妹の二人だ。'),
    'Vo_Plot_PZ_YuErJ3_Hun_22': (
        '「ボールド」の「心」について聞いたことがありますか？',
        '「ボールド」の「心」について聞いたことがありますか？'),
    'Vo_Plot_Prologue_02_ZhuLin1_Hun_1_ZiYan': (
        'できるだけ早く「組織」の演武場に行って、今日の練習をしなければならない。',
        'できるだけ早く「組織」の演武場に行って、今日の練習をしなければならない。'),
    'Vo_Plot_XG_LianXie1_Hun_7_ZiYan': (
        '「虚空」は「組織」の中で幻術を修める最も精精な人物である。',
        '「虚空」は「組織」の中で幻術を修める最も精精な人物である。'),
    'Vo_Plot_XSSL_ShaQiTa_MuXuaoKui_Hun_23': (
        '「左」と「右」は「左」ではない。',
        '「左」と「右」は「左」ではない。'),
    'Vo_Plot_ZDDY_MEM_QXJZ6_LiuShiDi_1': (
        'この「竜体改造」の技は、すでにその「組織」によって改良されている。',
        'この「竜体改造」の技は、すでにその「組織」によって改良されている。'),
    'Vo_Plot_ZuZi_Conference3_Hun_11': (
        '私は義父の言ったことを覚えていますが、私はあの断魂崖の時計に',
        '私は義父の言ったことを覚えていますが、私はあの断魂崖の時計に'),
}

rows = list(csv.DictReader(open(MANIFEST, encoding='utf-8')))
changed = 0
for r in rows:
    fix = FIXES.get(r['event_name'])
    if not fix:
        continue
    r['japanese_text'], r['japanese_text_tts'] = fix
    changed += 1

with open(MANIFEST, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)

print(f'lines fixed: {changed}')
