"""Fish Audio S2-Pro engine (4B, Research License — non-commercial use).

Local inference through the fish_speech repository's own TTSInferenceEngine
(no vLLM). Runs inside the venv-fs on E: (Python 3.12, torch 2.8 cu126):

    E:/TTS_Lab/venv-fs/Scripts/python.exe <repo>/src/tts/benchmark_s2pro.py

The voice reference is the character's multi-line Chinese audio
(out/benchmark/refs/<event>.cn.multi.wav) plus its Chinese transcript, built
from data/benchmark_refs.json. There is no per-replique emotion instruction in
S2-Pro: the prosody comes from the reference and the text.
"""
import io
import os
import sys
import queue

REPO = 'E:/TTS_Lab/fishspeech'
MODEL = 'E:/TTS_Lab/models/s2pro'


class Engine:
    name = 's2pro'
    sample_rate = 44100   # DAC codec output

    def __init__(self):
        if REPO not in sys.path:
            sys.path.insert(0, REPO)
        import torch
        from tools.server.model_manager import ModelManager
        torch.manual_seed(0)
        self.mm = ModelManager(
            mode='tts',
            device=os.environ.get('S2PRO_DEVICE',
                  'cuda' if torch.cuda.is_available() else 'cpu'),
            half=os.environ.get('S2PRO_HALF', '0') == '1',
            compile=False,
            llama_checkpoint_path=MODEL,
            decoder_checkpoint_path=None,
            decoder_config_name='modded_dac_vq',
        )
        self.engine = self.mm.tts_inference_engine

    def available(self):
        try:
            import torch
            return torch.cuda.is_available() or True
        except Exception:
            return False

    def synthesize(self, text, opts=None, reference_wav=None, transcript=''):
        """Returns (wav file bytes, sample_rate). `opts` unused: S2-Pro has no
        per-line emotion parameter; sampling follows the SDK defaults."""
        from fish_speech.utils.schema import ServeReferenceAudio, ServeTTSRequest
        if not reference_wav or not os.path.exists(reference_wav):
            return None
        with open(reference_wav, 'rb') as f:
            ref_audio = f.read()
        req = ServeTTSRequest(
            text=text,
            references=[ServeReferenceAudio(audio=ref_audio, text=transcript)],
            streaming=False,
            max_new_tokens=2048,
        )
        for result in self.engine.inference(req):
            if result.code == 0 and result.audio is not None:
                buf = io.BytesIO()
                import soundfile as sf
                sf.write(buf, result.audio, self.sample_rate, format='WAV',
                         subtype='PCM_16')
                return buf.getvalue(), self.sample_rate
            if result.code != 0:
                print('s2pro:', result.error)
        return None
