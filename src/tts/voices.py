"""Resolves the VOICEVOX style to use for a voice event.

The identity of the speaker comes from the game itself: ``DT_LocTable`` has a
``Speaker`` column that names the character of every line (see
src/tts/voice_assign.py, which builds data/character_voices.json). When the
character is unknown, the older per-prefix mapping is used as a fallback.

The ``speaker`` parameter of the VOICEVOX HTTP API is a *style* id.
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE

_CACHE = {}


def _load():
    if _CACHE:
        return _CACHE
    ev2sp = {}
    p = os.path.join(BASE, 'data', 'event_speaker.json')
    if os.path.exists(p):
        ev2sp = json.load(open(p, encoding='utf-8'))
    voices = {}
    p = os.path.join(BASE, 'data', 'character_voices.json')
    if os.path.exists(p):
        voices = json.load(open(p, encoding='utf-8'))
    vm = json.load(open(os.path.join(BASE, 'data', 'voice_map.json'), encoding='utf-8'))
    _CACHE.update(event_speaker=ev2sp, character_voices=voices,
                  prefix_speaker=vm['prefix_speaker'], default_speaker=vm['default_speaker'])
    return _CACHE


def speaker_for(event):
    """The style id to synthesize this event with."""
    c = _load()
    code = c['event_speaker'].get(event)
    if code:
        v = c['character_voices'].get(code)
        if v:
            return v['style']
    m = re.match(r'Vo_(?:Plot_)?(.+)$', event)
    rest = m.group(1) if m else ''
    for key in sorted(c['prefix_speaker'], key=len, reverse=True):
        if rest.startswith(key + '_') or rest == key or rest.lower().startswith(key.lower()):
            return c['prefix_speaker'][key]
    return c['default_speaker']


def character_of(event):
    """The character code of this event, when the game knows it."""
    return _load()['event_speaker'].get(event)
