"""Estimates the pitch (F0) of a decoded voice.

The height of the voice is what makes a character recognizable: the game already
gives each character its own Chinese voice, and that voice is the reference the
Japanese one has to match. The estimator is a plain autocorrelation on the
voiced frames, which is enough for speech and needs no extra dependency.

Usage:
    python src/audio/pitch.py <file.wav> [...]
"""
import sys

import numpy as np


def f0_track(samples, rate, fmin=60.0, fmax=400.0, frame_ms=40.0, hop_ms=20.0):
    """[(time, f0)] of the voiced frames, in Hz."""
    frame = int(rate * frame_ms / 1000)
    hop = int(rate * hop_ms / 1000)
    if len(samples) < frame:
        return []
    # remove the DC offset
    x = samples - samples.mean()
    global_rms = float(np.sqrt(np.mean(x ** 2)))
    if global_rms <= 0:
        return []
    # a frame is voiced when it is loud enough compared to the whole line
    threshold = 0.12 * global_rms

    min_lag = int(rate / fmax)
    max_lag = min(int(rate / fmin), frame - 1)
    if max_lag <= min_lag:
        return []

    out = []
    for start in range(0, len(x) - frame, hop):
        block = x[start:start + frame]
        energy = float(np.sqrt(np.mean(block ** 2)))
        if energy < threshold:          # silence
            continue
        norm_block = np.linalg.norm(block)
        if norm_block <= 0:
            continue
        block = block / norm_block
        corr = np.correlate(block, block, mode='full')[frame - 1:]
        norm = corr / max(corr[0], 1e-9)
        window = norm[min_lag:max_lag + 1]
        if window.size == 0:
            continue
        best = int(np.argmax(window)) + min_lag
        if norm[best] < 0.3:
            continue
        # octave guard: the correlation of a periodic signal is just as high at
        # twice the period, so prefer the longest lag that still correlates.
        for lag in range(best + 1, max_lag + 1):
            if norm[lag] > 0.85 * norm[best]:
                best = lag
            elif norm[lag] < 0.85 * norm[best]:
                break
        # parabolic interpolation around the peak
        if 0 < best < len(corr) - 1:
            a, b, c = corr[best - 1], corr[best], corr[best + 1]
            denom = a - 2 * b + c
            shift = 0.5 * (a - c) / denom if denom else 0.0
        else:
            shift = 0.0
        f0 = rate / (best + shift)
        if fmin <= f0 <= fmax:
            out.append((start / float(rate), f0))
    return out


def describe(samples, rate):
    """The summary of a voice: median height, spread, and how much it varies."""
    track = f0_track(samples, rate)
    if len(track) < 5:
        return None
    f0 = np.array([f for _, f in track])
    # the frames that are an octave off are outliers: they are dropped before
    # the median is taken, otherwise the height of a voice is wrong
    median = float(np.median(f0))
    keep = (f0 > median / 1.6) & (f0 < median * 1.6)
    if keep.sum() >= 5:
        f0 = f0[keep]
    q = np.percentile(f0, [10, 50, 90])
    return {
        'f0_median': float(q[1]),
        'f0_low': float(q[0]),
        'f0_high': float(q[2]),
        'f0_std': float(f0.std()),
        'voiced_ratio': float(len(track) * 20.0 / max(1.0, len(samples) / rate * 1000.0)),
        'frames': len(track),
    }
