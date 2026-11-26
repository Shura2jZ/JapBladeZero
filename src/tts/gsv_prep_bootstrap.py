"""Bootstrap for the GPT-SoVITS bundled python (isolated mode: it ignores
PYTHONPATH). Inserts the repo paths, sets the preprocess env vars, and runs a
prepare-dataset script. Run from anywhere:

    E:/TTS_Lab/GSV/GPT-SoVITS-v3lora-20250228/runtime/python.exe \
        <repo>/src/tts/gsv_prep_bootstrap.py [script.py]
"""
import os, sys

ROOT = r'E:/TTS_Lab/GSV/GPT-SoVITS-v3lora-20250228'
PKGD = ROOT + r'/GPT_SoVITS'
DATASET = r'E:/TTS_Lab/GSV_dataset'

for p in (ROOT, PKGD):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ['PATH'] = ROOT + os.pathsep + os.environ.get('PATH', '')
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
os.chdir(ROOT)

os.environ.setdefault('inp_text', DATASET + r'\Main_1.list')
os.environ.setdefault('inp_wav_dir', DATASET + r'\Main_1_wav')
os.environ.setdefault('exp_name', 'Main_1')
os.environ.setdefault('i_part', '0')
os.environ.setdefault('all_parts', '1')
os.environ.setdefault('opt_dir', ROOT + r'/logs/Main_1')
os.environ.setdefault('cnhubert_base_dir', PKGD + r'/pretrained_models/chinese-hubert-base')
os.environ.setdefault('is_half', 'True')
os.environ.setdefault('bert_pretrained_dir', PKGD + r'/pretrained_models/chinese-roberta-wwm-ext-large')
os.environ.setdefault('_CUDA_VISIBLE_DEVICES', '0')

script = sys.argv[1] if len(sys.argv) > 1 else PKGD + r'/prepare_datasets/2-get-hubert-wav32k.py'
src = open(script, encoding='utf-8').read()
exec(compile(src, script, 'exec'), {'__name__': '__main__', '__file__': script})
