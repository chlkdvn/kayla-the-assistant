"""Focus the user's laptop: silence GNOME notifications and system sounds.

"Focus mode" here means the desktop stops interrupting: notification banners
off and event sounds off. The state is restored when focus turns off.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
from collections.abc import Callable

_BANNER_SCHEMA = "org.gnome.desktop.notifications"
_BANNER_KEY = "show-banners"
_SOUND_SCHEMA = "org.gnome.desktop.sound"
_SOUND_KEY = "event-sounds"

Runner = Callable[[list[str]], tuple[int, str]]


def _subprocess_runner(argv: list[str]) -> tuple[int, str]:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=8, check=False)
    return result.returncode, result.stderr


class FocusMode:
    """Turn GNOME's interruptions off and back on again."""

    def __init__(
        self, *, run: Runner | None = None, which: Callable[[str], str | None] | None = None
    ) -> None:
        self._run = run or _subprocess_runner
        self._which = which or shutil.which

    def _gsettings(self) -> str | None:
        return self._which("gsettings")

    def on(self) -> str:
        """Enter focus mode: notifications and alert sounds silenced."""
        if self._gsettings() is None:
            return "Focus mode needs gsettings (GNOME), which I couldn't find."
        error = self._set(_BANNER_SCHEMA, _BANNER_KEY, "false")
        if error:
            return f"Focus mode couldn't silence notifications: {error}"
        with contextlib.suppress(Exception):
            self._set(_SOUND_SCHEMA, _SOUND_KEY, "false")
        return "Focus mode is ON - banners and notification sounds silenced."

    def off(self) -> str:
        """Leave focus mode: normal notifications and sounds return."""
        if self._gsettings() is None:
            return "Focus mode needs gsettings (GNOME), which I couldn't find."
        error = self._set(_BANNER_SCHEMA, _BANNER_KEY, "true")
        if error:
            return f"Focus mode couldn't restore notifications: {error}"
        with contextlib.suppress(Exception):
            self._set(_SOUND_SCHEMA, _SOUND_KEY, "true")
        return "Focus mode is OFF - notifications and sounds are back."

    def is_on(self) -> bool:
        """True when notification banners are currently silenced."""
        try:
            code, out = self._run(["gsettings", "get", _BANNER_SCHEMA, _BANNER_KEY])
        except Exception:  # noqa: BLE001 - unreadable means indeterminate
            return False
        return code == 0 and out.strip().lower() == "false"

    def _set(self, schema: str, key: str, value: str) -> str:
        try:
            code, err = self._run(["gsettings", "set", schema, key, value])
        except Exception as error:  # noqa: BLE001 - any launch problem degrades
            return str(error)
        if code != 0:
            return err.strip().splitlines()[-1] if err.strip() else f"exit {code}"
        return ""
