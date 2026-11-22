"""Reads a RIFF/WAVE stream, whatever the sample format is.

The decoder of vgmstream writes 32 bit floats, the ``wave`` module of the
standard library only knows the integer formats, so the chunks are read here.

Usage:
    from wavio import read_wav
    samples, rate = read_wav(data)
"""
import struct

import numpy as np


def read_wav(data):
    """(samples as float32, sample rate) of a RIFF/WAVE buffer."""
    if data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        raise ValueError('not a RIFF/WAVE buffer')
    pos = 12
    fmt = None
    payload = None
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack_from('<I', data, pos + 4)[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b'fmt ':
            fmt = struct.unpack_from('<HHIIHH', body, 0)
        elif cid == b'data':
            payload = body
        pos += 8 + size + (size & 1)
    if fmt is None or payload is None:
        raise ValueError('missing fmt or data chunk')
    tag, channels, rate, _brate, _align, bits = fmt
    if tag == 3 and bits == 32:
        samples = np.frombuffer(payload, dtype='<f4')
    elif tag == 1 and bits == 16:
        samples = np.frombuffer(payload, dtype='<i2').astype(np.float32) / 32768.0
    elif tag == 1 and bits == 8:
        samples = (np.frombuffer(payload, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError('unsupported format %d/%d bits' % (tag, bits))
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples.astype(np.float32), rate
