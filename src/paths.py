"""Resolves the location of the heavy working artefacts.

The patched packages, the generated WAV and Wwise files take several
gigabytes. They do not belong on the system drive, which is usually short on
space, and they are not versioned either.

``PBZ_WORK`` designates the directory that holds them. By default it is
``E:/PBZ_Build`` when that drive exists, otherwise the repository itself.

The repository can reach them either directly (the directories are part of the
checkout) or through directory junctions:

    mklink /J build E:\\PBZ_Build\\build
    mklink /J out   E:\\PBZ_Build\\out

so the scripts keep using paths relative to the repository.
"""

import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: where the heavy artefacts live (build/, out/, models/, voicevox/)
WORK = os.environ.get('PBZ_WORK') or ('E:/PBZ_Build' if os.path.isdir('E:/') else BASE)


def work(*parts):
    """Path inside the working directory (E: by default)."""
    return os.path.join(WORK, *parts)


def build(*parts):
    """Path inside the build directory."""
    return work('build', *parts)


def out(*parts):
    """Path inside the output directory (WAV and .wem)."""
    return work('out', *parts)


def models(*parts):
    """Path inside the translation models directory."""
    return work('models', *parts)


def voicevox(*parts):
    """Path inside the VOICEVOX engine directory."""
    return os.environ.get('VOICEVOX_DIR') or work('voicevox', 'windows-cpu', *parts)
