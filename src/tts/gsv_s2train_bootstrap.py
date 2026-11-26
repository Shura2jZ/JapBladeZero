"""Launches the GPT-SoVITS SoVITS v2 fine-tune (s2_train.py) for one speaker.

Follows exactly what the package webui does (webui.open1Ba): it loads
GPT_SoVITS/configs/s2.json, overrides the training fields, writes a temp
config and runs s2_train.py --config.

    E:/TTS_Lab/GSV/GPT-SoVITS-v3lora-20250228/runtime/python.exe <repo>/src/tts/gsv_s2train_bootstrap.py [epochs]
"""
import json, os, sys, subprocess

ROOT = r'E:/TTS_Lab/GSV/GPT-SoVITS-v3lora-20250228'
PKGD = ROOT + r'/GPT_SoVITS'
EXP = os.environ.get('GSV_EXP', 'Main_1')
EPOCHS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
BATCH = int(os.environ.get('GSV_BATCH', '6'))
EXP_DIR = ROOT + r'/logs/' + EXP

for p in (ROOT, PKGD):
    if p not in sys.path:
        sys.path.insert(0, p)
os.chdir(ROOT)
os.environ['PATH'] = ROOT + os.pathsep + os.environ.get('PATH', '')

cfg = json.load(open(PKGD + r'/configs/s2.json', encoding='utf-8'))
cfg['train']['epochs'] = EPOCHS
cfg['train']['batch_size'] = BATCH
cfg['train']['fp16_run'] = False            # fp32: plus stable sur 10 Go
cfg['train']['pretrained_s2G'] = PKGD + r'/pretrained_models/gsv-v2final-pretrained/s2G2333k.pth'
cfg['train']['pretrained_s2D'] = PKGD + r'/pretrained_models/gsv-v2final-pretrained/s2D2333k.pth'
cfg['train']['if_save_latest'] = True
cfg['train']['if_save_every_weights'] = True
cfg['train']['save_every_epoch'] = EPOCHS
cfg['train']['gpu_numbers'] = '0'
cfg['model']['version'] = 'v2'
cfg['data']['exp_dir'] = EXP_DIR
cfg['data']['training_set'] = None
cfg['s2_ckpt_dir'] = EXP_DIR
cfg['save_weight_dir'] = ROOT + r'/SoVITS_weights_v2'
cfg['name'] = EXP
cfg['version'] = 'v2'

tmp = os.environ.get('TEMP', r'C:\Windows\Temp') + r'\gsv_s2_config.json'
json.dump(cfg, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('config ->', tmp)

cmd = [ROOT + r'/runtime/python.exe', '-c',
       "import sys; sys.argv = [%r, '--config', %r];"
       "sys.path.insert(0, r'%s');"
       "sys.path.insert(0, r'%s');"
       "import runpy; runpy.run_path(%r, run_name='__main__')"
       % (PKGD + r'/s2_train.py', tmp, PKGD, ROOT, PKGD + r'/s2_train.py')]
env = dict(os.environ)
env['PATH'] = ROOT + os.pathsep + env.get('PATH', '')
r = subprocess.run(cmd, env=env)
sys.exit(r.returncode)
