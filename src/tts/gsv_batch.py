"""Batch fine-tune: one SoVITS v2 per character, from the game's Chinese lines.

Tiers (data/batch_tiers.json):
  tier1: >= 10 lines  -> 8 epochs
  tier2: 5-9 lines    -> 4 epochs, validated by the generation QC

Each character gets: logs/<char>/ dataset + SoVITS_weights_v2/<char>_eN.pth.
Resumable: characters with an existing weight file are skipped.

    E:/TTS_Lab/GSV/GPT-SoVITS-v3lora-20250228/runtime/python.exe <repo>/src/tts/gsv_batch.py [--tier 1] [--only Char_X]
"""
import csv, json, os, sys, wave, shutil

# pyvgmstream lives in the system python: decode in a subprocess when the
# heavy deps are unavailable in the package runtime.
ROOT = r'E:/TTS_Lab/GSV/GPT-SoVITS-v3lora-20250228'
PKGD = ROOT + r'/GPT_SoVITS'
REPO = r'C:/Users/marou/.deepai-code/scratch/2026-11-16-wsh-claude-fable-cd7797cc'
DATASET = r'E:/TTS_Lab/GSV_dataset'

sys.path.insert(0, os.path.join(REPO, 'src'))
sys.path.insert(0, os.path.join(REPO, 'src', 'audio'))
os.chdir(ROOT)
os.environ['PATH'] = ROOT + os.pathsep + os.environ.get('PATH', '')
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

_DECODE_HELPER = os.path.join(REPO, 'src', 'tts', 'decode_one.py')


def decode_to_wav(ev, outp):
    if os.path.exists(outp) and os.path.getsize(outp) > 1000:
        return True
    import subprocess
    syspy = shutil.which('python') or r'C:/Users/marou/AppData/Local/Programs/Python/Python314/python.exe'
    r = subprocess.run([syspy, _DECODE_HELPER, ev, outp],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    if r.returncode == 0 and os.path.exists(outp) and os.path.getsize(outp) > 1000:
        return True
    print('  decode ERR', ev, (r.stderr or '')[-120:], flush=True)
    return False


def run_python(script, env_extra):
    import subprocess
    env = dict(os.environ)
    env.update(env_extra)
    code = ("import sys; sys.argv = [%r, '--config', %r];"
            "sys.path.insert(0, r'%s'); sys.path.insert(0, r'%s');"
            "import runpy; runpy.run_path(%r, run_name='__main__')")
    if script.endswith('2-get-hubert-wav32k.py') or script.endswith('1-get-text.py'):
        code = ("import sys; sys.path.insert(0, r'%s'); sys.path.insert(0, r'%s');"
                "exec(open(%r, encoding='utf-8').read())")
        cmd = [ROOT + r'/runtime/python.exe', '-c',
               code % (PKGD, ROOT, script)]
    else:
        cmd = [ROOT + r'/runtime/python.exe', '-c',
               code % (PKGD + r'/s2_train.py', env_extra['_config_path'], PKGD, ROOT,
                       PKGD + r'/s2_train.py')]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return r


def prep_and_train(char, lines, rows, epochs, batch=6):
    """Builds the dataset and fine-tunes SoVITS for one character."""
    exp_dir = ROOT + r'/logs/' + char
    os.makedirs(exp_dir, exist_ok=True)
    os.makedirs(exp_dir + r'/logs_s2_v2', exist_ok=True)
    wavdir = DATASET + r'/' + char + '_wav'
    os.makedirs(wavdir, exist_ok=True)

    # decode + .list
    listlines = []
    got = 0
    for ev in lines:
        if got >= 120:            # cap ~15 min of audio per character
            break
        t = (rows[ev].get('chinese_text') or '').strip().replace('|', '')
        if not t or got and got < 0:
            continue
        outp = os.path.join(wavdir, ev + '.wav')
        if decode_to_wav(ev, outp):
            listlines.append(f'{outp}|{char}|zh|{t}')
            got += 1
    if got < 5:
        print(f'  {char}: seulement {got} lignes decodables, abandon', flush=True)
        return None
    list_path = DATASET + r'/' + char + '.list'
    open(list_path, 'w', encoding='utf-8').write('\n'.join(listlines))

    base_env = dict(inp_text=list_path, inp_wav_dir=wavdir, exp_name=char,
                    i_part='0', all_parts='1', opt_dir=exp_dir,
                    cnhubert_base_dir=PKGD + r'/pretrained_models/chinese-hubert-base',
                    bert_pretrained_dir=PKGD + r'/pretrained_models/chinese-roberta-wwm-ext-large',
                    is_half='True', _CUDA_VISIBLE_DEVICES='0')

    # 1-get-text -> 2-name2text.txt
    r = run_python(PKGD + r'/prepare_datasets/1-get-text.py',
                   {**base_env, 'PYTHONPATH': PKGD})
    src_txt = exp_dir + r'/2-name2text-0.txt'
    if os.path.exists(src_txt):
        os.replace(src_txt, exp_dir + r'/2-name2text.txt')
    if not os.path.exists(exp_dir + r'/2-name2text.txt'):
        print(f'  {char}: etape 1 echouee', r.stderr[-300:], flush=True)
        return None

    # 2-get-hubert-wav32k
    r = run_python(PKGD + r'/prepare_datasets/2-get-hubert-wav32k.py', base_env)
    n_h = len(os.listdir(exp_dir + r'/4-cnhubert')) if os.path.exists(exp_dir + r'/4-cnhubert') else 0
    if n_h < 5:
        print(f'  {char}: etape 2 echouee ({n_h} hubert)', flush=True)
        return None

    # s2_train
    cfg = json.load(open(PKGD + r'/configs/s2.json', encoding='utf-8'))
    cfg['train']['epochs'] = epochs
    cfg['train']['batch_size'] = batch
    cfg['train']['fp16_run'] = False
    cfg['train']['pretrained_s2G'] = PKGD + r'/pretrained_models/gsv-v2final-pretrained/s2G2333k.pth'
    cfg['train']['pretrained_s2D'] = PKGD + r'/pretrained_models/gsv-v2final-pretrained/s2D2333k.pth'
    cfg['train']['if_save_latest'] = True
    cfg['train']['if_save_every_weights'] = True
    cfg['train']['save_every_epoch'] = epochs
    cfg['train']['gpu_numbers'] = '0'
    cfg['model']['version'] = 'v2'
    cfg['data']['exp_dir'] = exp_dir
    cfg['s2_ckpt_dir'] = exp_dir
    cfg['save_weight_dir'] = ROOT + r'/SoVITS_weights_v2'
    cfg['name'] = char
    cfg['version'] = 'v2'
    tmp = os.environ.get('TEMP', r'C:\Windows\Temp') + r'/gsv_s2_' + char + '.json'
    json.dump(cfg, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    r = run_python(PKGD + r'/s2_train.py',
                   {**base_env, '_config_path': tmp, 'PYTHONPATH': PKGD})
    weights = ROOT + r'/SoVITS_weights_v2/' + f'{char}_e{epochs}_s{epochs * max(1, got // batch) * batch}.pth'
    # the exact step count varies; find the newest weight of this character
    found = sorted([f for f in os.listdir(ROOT + r'/SoVITS_weights_v2')
                    if f.startswith(char + '_')])
    shutil.rmtree(exp_dir, ignore_errors=True)   # checkpoints d'epochs: 1+ GB/char
    if found:
        print(f'  {char}: OK -> {found[-1]}', flush=True)
        return ROOT + r'/SoVITS_weights_v2/' + found[-1]
    print(f'  {char}: echec de sauvegarde', r.stderr[-300:], flush=True)
    return None


def main():
    only = None
    if '--only' in sys.argv:
        only = sys.argv[sys.argv.index('--only') + 1]
    tier = sys.argv[sys.argv.index('--tier') + 1] if '--tier' in sys.argv else None

    speakers = json.load(open(REPO + r'/data/event_speaker.json', encoding='utf-8'))
    rows = {r['event_name']: r for r in csv.DictReader(
        open(REPO + r'/data/manifest_jp.csv', encoding='utf-8'))}
    from collections import defaultdict
    per = defaultdict(list)
    for r in csv.DictReader(open(REPO + r'/data/manifest_jp.csv', encoding='utf-8')):
        sp = speakers.get(r['event_name'])
        if sp and (r.get('chinese_text') or '').strip():
            per[sp].append(r['event_name'])

    WDIR = ROOT + r'/SoVITS_weights_v2'
    existing = set(os.path.splitext(f)[0].split('_e')[0]
                   for f in os.listdir(WDIR) if f.endswith('.pth'))
    jobs = []
    for sp, evs in per.items():
        if sp in existing:
            print(f'  {sp}: deja fait, saute', flush=True)
            continue
        n = len(evs)
        if n >= 10:
            jobs.append((sp, evs, 8))
        elif n >= 5 and tier in (None, '2'):
            jobs.append((sp, evs, 4))
    jobs.sort(key=lambda j: -len(j[1]))
    if only:
        jobs = [j for j in jobs if j[0] == only]
    print(f'{len(jobs)} personnages a fine-tuner', flush=True)

    done = {}
    wp = REPO + r'/data/gsv_weights.json'
    if os.path.exists(wp):
        done = json.load(open(wp, encoding='utf-8'))
    for sp, evs, ep in jobs:
        try:
            w = prep_and_train(sp, evs, rows, ep)
        except Exception as e:
            print(f'  {sp}: EXC {repr(e)[:120]}', flush=True)
            w = None
        if w:
            done[sp] = w
            json.dump(done, open(wp, 'w'),
                      ensure_ascii=False, indent=1)
    print('termine', flush=True)


if __name__ == '__main__':
    main()
