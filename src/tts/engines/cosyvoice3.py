"""CosyVoice 3 engine (0.5B, Apache 2.0) — benchmark candidate B.

Zero-shot cloning: the voice reference is a clean chunk of the character's own
Chinese in-game audio (out/benchmark/refs/<event>.cn.wav), and the direction is
a natural-language performance instruction (inference_instruct2).

This engine runs inside the dedicated venv on E: (Python 3.12 + torch CUDA):

    E:/TTS_Lab/venv-cv3/Scripts/python.exe
        E:/PBZ_Build/repo/src/tts/benchmark_cosyvoice.py --engine cosyvoice3
"""
import io
import os

MODEL_DIR = 'E:/TTS_Lab/models/cv3'
REPO_DIR = 'E:/TTS_Lab/cosyvoice'

#: the performance direction, per bucket, phrased for judgment instruct2
INSTRUCT = {
    'old_man':   '沈著穏やかに、少し低い声でゆっくり読んで。<|endofprompt|>',
    'young_man': '若々しく、エネルギーのある口調で自然に読んで。<|endofprompt|>',
    'woman':     '女性らしく明るく、落ち着いて読んで。<|endofprompt|>',
    'shout':     '戦闘の叫びのように強く、力強く叫んで。<|endofprompt|>',
    'long':      '感情を込めて、自然な抑揚で読んで。<|endofprompt|>',
    'short':     '短く自然に読んで。<|endofprompt|>',
}


class Engine:
    name = 'cosyvoice3'
    sample_rate = 24000

    def __init__(self):
        import sys
        for d in (REPO_DIR, os.path.join(REPO_DIR, 'third_party', 'Matcha-TTS')):
            if d not in sys.path:
                sys.path.insert(0, d)
        from cosyvoice.cli.cosyvoice import CosyVoice3
        self.model = CosyVoice3(MODEL_DIR)

    def available(self):
        try:
            import torch
            return torch.cuda.is_available()
        except Exception:
            return False

    def synthesize(self, text, opts=None, reference_wav=None, instruct=None):
        """opts['bucket'] selects the canned direction; `reference_wav` is the
        path of the Chinese reference; `instruct` overrides the direction."""
        if not reference_wav or not os.path.exists(reference_wav):
            return None
        instruct = (instruct or INSTRUCT.get((opts or {}).get('bucket', '')) or
                    '自然に読んで。<|endofprompt|>')
        if (opts or {}).get('mode') == 'zero_shot':
            speech = None
            for chunk in self.model.inference_zero_shot(
                    text, '', reference_wav, stream=False):
                speech = chunk['tts_speech'] if speech is None else speech
            if speech is None:
                return None
            return self._wav_bytes(speech)
        speech = None
        for chunk in self.model.inference_instruct2(
                text, instruct, reference_wav, stream=False):
            speech = chunk['tts_speech'] if speech is None else speech
        if speech is None:
            return None
        return self._wav_bytes(speech)

    def _wav_bytes(self, speech):
        # CosyVoice output peaks beyond +-1.0: writing it as-is clips the
        # int16 conversion into a monster-like distortion. Guard + normalize.
        import torch
        x = speech.detach().float().flatten()
        peak = x.abs().max().item()
        if peak > 0.97:
            x = x * (0.97 / peak)
        x = x.unsqueeze(0)
        import torchaudio
        buf = io.BytesIO()
        torchaudio.save(buf, x, self.sample_rate, format='wav')
        return buf.getvalue(), self.sample_rate
