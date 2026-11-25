"""TTS engine abstraction.

Every engine exposes:

    name                       unique id, also the benchmark subdirectory
    available()                can we generate right now?
    synthesize(text, opts)     -> (wav bytes, sample_rate) or None

`opts` is a plain dict of performance parameters, engine-interpreted:
voice (engine-specific id), speed, pitch, emotion (free text), volume.

The old voicevox inline code in tts_generate.py stays the production
reference; engines/ is where the experimental candidates live.
"""
