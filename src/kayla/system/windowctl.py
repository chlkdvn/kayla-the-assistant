"""List, close, and bring forward open windows through the window manager.

The desktop here is X11, so ``wmctrl -l -x`` is the source of truth for what is
open, and ``wmctrl`` performs close/activate. Browser tabs themselves are
managed inside the browser, so Kayla closes and focuses whole windows by
matching the app class or the window title.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
from collections.abc import Callable

from kayla.system.monitor import WindowEntry, parse_wmctrl

Runner = Callable[[list[str]], tuple[int, str, str]]
"""Run a command: returns (returncode, stdout, stderr)."""


def _subprocess_runner(argv: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=8, check=False)
    return result.returncode, result.stdout, result.stderr


def _short_app_class(app_class: str) -> str:
    """Display helper: the tail of ``gnome-terminal-server.Gnome-terminal``."""
    tail = app_class.rsplit(".", 1)[-1]
    return tail or app_class


def parse_stacking(text: str) -> list[int]:
    """Parse ``xprop -root _NET_CLIENT_LIST_STACKING`` into ordered window ids.

    Output looks like::

        _NET_CLIENT_LIST_STACKING(WINDOW): window id # 0x3a00027, 0x3a00025, ...

    EWMH defines the list bottom-to-top, so a LARGER index in the result means
    the window was closer to the front - closest to "the one used last".
    """
    marker = "window id #"
    start = text.find(marker)
    if start < 0:
        return []
    ids: list[int] = []
    for token in text[start + len(marker) :].replace(",", " ").split():
        try:
            ids.append(int(token, 16))
        except ValueError:
            continue
    return ids


class WindowControl:
    """Close, activate, and list desktop windows by title or app."""

    def __init__(
        self,
        *,
        run: Runner | None = None,
        which: Callable[[str], str | None] | None = None,
    ) -> None:
        self._run = run or _subprocess_runner
        self._which = which or shutil.which

    def list(self) -> list[WindowEntry]:
        """Every open window the window manager reports."""
        if self._which("wmctrl") is None:
            return []
        try:
            code, out, _err = self._run(["wmctrl", "-l", "-x"])
        except Exception:  # noqa: BLE001 - tool failures never crash the chat
            return []
        if code != 0:
            return []
        return parse_wmctrl(out)

    def close(self, target: str) -> str:
        """Close windows whose class or title matches ``target`` (case-insensitive)."""
        windows = self.list()
        if not windows:
            return "No open windows matched - I couldn't list windows."
        matches = _match(windows, target)
        if not matches:
            return f"No window matched '{target}'."
        closed: list[str] = []
        for window in matches:
            if self._act(["wmctrl", "-i", "-c", window.window_id]):
                closed.append(f"{_short_app_class(window.app_class)}: {window.title}")
        if not closed:
            return "The window manager refused the close request."
        return "Closed: " + ", ".join(closed) + "."

    def activate(self, target: str) -> str:
        """Raise and focus the window the user used most recently.

        When several windows match (usually: several Chrome ones), the window
        manager's stacking order is the only thing that remembers which one
        the user had in front last - so the matching window closest to the top
        of the stack wins. One new instance is never spawned for the job.
        """
        windows = self.list()
        matches = _match(windows, target)
        if not matches:
            return f"No window matched '{target}'."
        if len(matches) > 1:
            matches = self._most_recent_first(matches)
        first = matches[0]
        if not self._act(["wmctrl", "-i", "-a", first.window_id]):
            return "The window manager refused to focus the window."
        if len(matches) > 1:
            return (
                f"Brought up {_short_app_class(first.app_class)}: {first.title}. "
                f"There were {len(matches)} matching windows open - I picked the "
                "one you used last."
            )
        return f"Focused {_short_app_class(first.app_class)}: {first.title}."

    def _most_recent_first(self, matches: list[WindowEntry]) -> list[WindowEntry]:
        """Re-order matches so the topmost (last-used) window comes first."""
        order = self._stack_order()
        if not order:
            return matches  # cannot ask the window manager; keep listing order

        def stack_index(window: WindowEntry) -> int:
            try:
                return order.index(int(window.window_id, 16))
            except ValueError:  # not in the stack; treat as furthest back
                return -1

        return sorted(matches, key=stack_index, reverse=True)

    def _stack_order(self) -> list[int]:
        """Window ids from ``xprop -root _NET_CLIENT_LIST_STACKING``, bottom first."""
        if self._which("xprop") is None:
            return []
        try:
            code, out, _err = self._run(["xprop", "-root", "_NET_CLIENT_LIST_STACKING"])
        except Exception:  # noqa: BLE001 - tool failures never crash the chat
            return []
        if code != 0:
            return []
        return parse_stacking(out)

    def _act(self, argv: list[str]) -> bool:
        """Run one wmctrl action; True when the window manager accepted it."""
        if self._which("wmctrl") is None:
            return False
        with contextlib.suppress(Exception):
            code, _out, _err = self._run(argv)
            return code == 0
        return False


def _match(windows: list[WindowEntry], target: str) -> list[WindowEntry]:
    """Best-first window matches for a spoken target like 'chrome' or 'inbox'."""
    needle = target.strip().casefold().strip("'\"")
    if not needle:
        return []
    exact: list[WindowEntry] = []
    class_starts: list[WindowEntry] = []
    class_contains: list[WindowEntry] = []
    title_contains: list[WindowEntry] = []
    for window in windows:
        klass = window.app_class.casefold()
        title = window.title.casefold()
        short = klass.rsplit(".", 1)[-1]
        if klass == needle or short == needle:
            exact.append(window)
        elif short.startswith(needle) or klass.startswith(needle):
            class_starts.append(window)
        elif needle in klass:
            class_contains.append(window)
        elif needle in title:
            title_contains.append(window)
    return exact + class_starts + class_contains + title_contains
