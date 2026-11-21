"""Lists the voices and styles of the running VOICEVOX engine.

The HTTP API of the engine takes a *style* id in the ``speaker`` parameter, and
those ids change between engine versions. The stable way to name a voice is
therefore (voice name, style name), which this script resolves once and stores
in ``data/voicevox_styles.json``.

Usage:
    python src/tts/voicevox_styles.py [--port 50021] [--out data/voicevox_styles.json]
"""
import argparse, json, os, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE

#: gender of the character each voice plays (the engine does not expose it)
GENDER = {
    '四国めたん': 'F', 'ずんだもん': 'F', '春日部つむぎ': 'F', '雨晴はう': 'F',
    '波音リツ': 'F', '玄野武宏': 'M', '白上虎太郎': 'M', '青山龍星': 'M',
    '冥鳴ひまり': 'F', '九州そら': 'F', 'もち子さん': 'F', '剣崎雌雄': 'M',
    'WhiteCUL': 'F', '後鬼': 'M', 'No.7': 'M', 'ちび式じい': 'M',
    '櫻歌ミコ': 'F', '小夜/SAYO': 'F', 'ナースロボ＿タイプТ': 'F',
    '†聖騎士 紅桜†': 'F', '雀松朱司': 'M', '麒ヶ島宗麟': 'M', '春歌ナナ': 'F',
    '猫使アル': 'F', '猫使ビィ': 'F', '中国うさぎ': 'F', '栗田まろん': 'F',
    'あいえるたん': 'F', '満別花丸': 'M', '琴詠ニア': 'F', 'Voidoll': 'M',
    'ぞん子': 'F', '中部つるぎ': 'F', '離途': 'M', '黒沢冴白': 'F',
    'ユーレイちゃん': 'F', '東北ずん子': 'F', '東北きりたん': 'F', '東北イタコ': 'F',
    'あんこもん': 'F', '夜語トバリ': 'M', '暁記ミタマ': 'F', '里石ユカ': 'F',
    'ブイブイ・コバコ': 'M',
}


def fetch(port):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/speakers', timeout=30) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=50021)
    ap.add_argument('--out', default=os.path.join(BASE, 'data', 'voicevox_styles.json'))
    a = ap.parse_args()

    speakers = fetch(a.port)
    styles = {}
    for sp in speakers:
        gender = GENDER.get(sp['name'], '?')
        for st in sp.get('styles', []):
            styles[f'{sp["name"]}|{st["name"]}'] = {
                'id': st['id'],
                'voice': sp['name'],
                'style': st['name'],
                'gender': gender,
            }
    json.dump(styles, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    by_gender = {}
    for v in styles.values():
        by_gender.setdefault(v['gender'], []).append(v['id'])
    for g, ids in sorted(by_gender.items()):
        print(f'  {g}: {len(ids)} styles')
    print(f'{len(styles)} styles -> {a.out}')


if __name__ == '__main__':
    main()
