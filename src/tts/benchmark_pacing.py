"""A/B pacing test: zero_shot vs instruct2 on the pathological lines.

    E:/TTS_Lab/venv-cv3/Scripts/python.exe <repo>/src/tts/benchmark_pacing.py
"""
import csv, json, os, sys, wave

BASE = r'C:/Users/marou/.deepai-code/scratch/2026-11-16-wsh-claude-fable-cd7797cc'
sys.path.insert(0, os.path.join(BASE, 'src', 'tts'))
sys.path.insert(0, os.path.join(BASE, 'src'))
os.chdir(BASE)

from tts.engines.cosyvoice3 import Engine

WORST = [
    'Vo_Plot_XG_JianKeDuiZhang_Hun_1',
    'Vo_Plot_DHSD_LaoGenTou_Hun_4_2',
    'Vo_Plot_End_MengHua2_Battle_3',
    'Vo_Plot_ZDDY_MEM_QianQian2_MoJiZi_2',
    'Vo_Plot_DDSD_LY_LY_6',
    'Vo_Plot_LJC_MEM_CunMin4_Son_10',
]
bench = json.load(open(os.path.join(BASE, 'data', 'benchmark_set.json'), encoding='utf-8'))
rows = {r['event_name']: r for r in csv.DictReader(
    open(os.path.join(BASE, 'data', 'manifest_jp.csv'), encoding='utf-8'))}
refs = os.path.join(BASE, 'out', 'benchmark', 'refs')
outdir = os.path.join(BASE, 'out', 'benchmark', 'cosyvoice3_zero')
os.makedirs(outdir, exist_ok=True)

eng = Engine()
for ev in WORST:
    r = rows.get(ev)
    if not r:
        continue
    text = (r.get('japanese_text_tts') or r.get('japanese_text') or '').strip()
    ref = os.path.join(refs, ev + '.cn.multi.wav')
    if not os.path.exists(ref):
        ref = os.path.join(refs, ev + '.cn.wav')
    if not os.path.exists(ref):
        continue
    for mode in ('zero_shot', 'instruct2'):
        try:
            res = eng.synthesize(text, {'bucket': bench[ev]['bucket'],
                                        'mode': mode if mode == 'zero_shot' else None},
                                 reference_wav=ref)
            wav, sr = res
            p = os.path.join(outdir, f'{ev}.{mode}.wav')
            with wave.open(p, 'wb') as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(wav)
            with wave.open(p) as w:
                d = w.getnframes() / w.getframerate()
            print(f'{ev} {mode}: {d:.1f}s (zh={bench[ev]["duration_zh"]:.1f}s)', flush=True)
        except Exception as e:
            print('ERR', ev, mode, repr(e)[:120], flush=True)
