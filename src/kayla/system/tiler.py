"""Tile the screen: split the desktop into 2, 3, or 4 window slots.

"Kayla, split my screen into four" tiles the visible windows into a 2x2 grid;
two windows sit side by side, three in columns. The work area (excluding
panels) comes from ``wmctrl -d``; every move uses ``wmctrl`` so no extra tools
are needed. Windows on sticky surfaces (docks, panels) are skipped, and so is
Kayla's own orb window.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
from collections.abc import Callable

from kayla.system.monitor import WindowEntry, parse_wmctrl, parse_work_area

Runner = Callable[[list[str]], tuple[int, str, str]]

LAYOUTS: dict[int, tuple[int, int]] = {
    1: (1, 1),
    2: (2, 1),  # columns, rows
    3: (3, 1),
    4: (2, 2),
    6: (3, 2),
}


def _subprocess_runner(argv: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=8, check=False)
    return result.returncode, result.stdout, result.stderr


def grid_rects(count: int, area: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
    """Inside-out grid cells for ``count`` windows (pure math, testable)."""
    if count <= 0:
        return []
    cols, rows = LAYOUTS.get(count, ((count if count <= 3 else 3), (count + 2) // 3))
    x, y, width, height = area
    cell_w = width // cols
    cell_h = height // rows
    cells: list[tuple[int, int, int, int]] = []
    for index in range(count):
        col = index % cols
        row = index // cols
        cells.append((x + col * cell_w, y + row * cell_h, cell_w, cell_h))
    return cells


class WindowTiler:
    """Arrange visible windows into grids with the window manager."""

    def __init__(
        self,
        *,
        run: Runner | None = None,
        which: Callable[[str], str | None] | None = None,
    ) -> None:
        self._run = run or _subprocess_runner
        self._which = which or shutil.which

    def split(self, count: int) -> str:
        """Tile up to ``count`` visible windows; returns a spoken summary."""
        count = max(1, min(int(count), 6))
        if self._which("wmctrl") is None:
            return "Screen splitting needs wmctrl, which isn't installed."
        windows = [
            w
            for w in self._windows()
            if w.desktop != "-1" and "kayla" not in f"{w.app_class} {w.title}".lower()
        ]
        if not windows:
            return "There are no tile-able windows open right now."
        area = self._work_area()
        if area is None:
            return "I couldn't read the desktop work area, so I didn't move anything."
        chosen = windows[:count]
        cells = grid_rects(len(chosen), area)
        self._apply_windows(chosen, cells)
        shape = {
            1: "a single column",
            2: "two halves",
            3: "three columns",
            4: "a 2x2 grid",
            6: "a 3x2 grid",
        }.get(len(chosen), f"{len(chosen)} slots")
        return f"Tiled {len(chosen)} windows into {shape}."

    # -- internals (runner-injected, fakes in tests) ------------------------

    def _windows(self) -> list[WindowEntry]:
        try:
            code, out, _err = self._run(["wmctrl", "-l", "-x"])
        except Exception:  # noqa: BLE001
            return []
        if code != 0:
            return []
        return parse_wmctrl(out)

    def _work_area(self) -> tuple[int, int, int, int] | None:
        try:
            code, out, _err = self._run(["wmctrl", "-d"])
        except Exception:  # noqa: BLE001
            return None
        if code != 0:
            return None
        return parse_work_area(out)

    def _apply_windows(
        self, windows: list[WindowEntry], cells: list[tuple[int, int, int, int]]
    ) -> None:
        for window, (x, y, w, h) in zip(windows, cells, strict=True):
            with contextlib.suppress(Exception):
                self._run(["wmctrl", "-i", "-r", window.window_id, "-e", f"0,{x},{y},{w},{h}"])
                self._run(["wmctrl", "-i", "-a", window.window_id])
