"""YonerAI Romaji Composer: CLI-local romaji-to-Japanese input composition.

This package is a CLI-process input composer only. It is not a global OS IME,
does not hook keyboard input outside the YonerAI CLI process, and does not
require live provider access. Deterministic conversion works fully offline.
"""

from yonerai_cli.ime.romaji_composer import RomajiComposer, ComposerState

__all__ = ["RomajiComposer", "ComposerState"]
