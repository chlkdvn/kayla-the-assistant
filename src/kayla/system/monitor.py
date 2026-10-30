"""Look inside the laptop: running apps, windows, memory, CPU, and battery.

Kayla answers "what's open on my laptop?" and "how much RAM is free?" from here.
The heavy lifting is psutil plus ``wmctrl`` for open windows (X11). Both are
injected into :class:`SystemMonitor` so tests never touch the real machine.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Runner = Callable[[list[str]], tuple[str, str]]
"""Run one command and return (stdout, stderr)."""


def _subprocess_runner(argv: list[str]) -> tuple[str, str]:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=8, check=False)
    return result.stdout, result.stderr


def _load_psutil() -> Any:
    """Import psutil lazily so a missing wheel degrades to a clear error."""
    try:
        import psutil
    except ImportError as error:  # pragma: no cover - depends on install
        raise RuntimeError("psutil is not installed; run 'uv sync'.") from error
    return psutil


@dataclass(frozen=True)
class WindowEntry:
    """One open window as the X11 window manager sees it."""

    window_id: str
    app_class: str
    title: str
    desktop: str = ""  # "-1" for sticky/panel surfaces; unchanged column otherwise


@dataclass(frozen=True)
class ProcessUsage:
    """Aggregated resource use for one program (all its processes grouped)."""

    name: str
    memory_mb: float
    cpu_percent: float


def _short_app_class(app_class: str) -> str:
    """Display helper: the tail of ``gnome-terminal-server.Gnome-terminal``."""
    tail = app_class.rsplit(".", 1)[-1]
    return tail or app_class


@dataclass
class SystemSnapshot:
    """A readable picture of the machine at one moment."""

    cpu_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    ram_percent: float = 0.0
    battery_percent: float | None = None
    battery_plugged: bool | None = None
    top: list[ProcessUsage] = field(default_factory=list)
    windows: list[WindowEntry] = field(default_factory=list)

    def app_names(self) -> list[str]:
        """Programs with at least one visible window (class names deduped)."""
        seen: list[str] = []
        for window in self.windows:
            name = window.app_class.rsplit(".", 1)[-1]
            if name and name.lower() not in (entry.lower() for entry in seen):
                seen.append(name)
        return seen


def parse_wmctrl(text: str) -> list[WindowEntry]:
    """Parse ``wmctrl -l -x`` output into window entries.

    Each line: window_id, desktop, host, WM_CLASS, then the title. The desktop
    column ("-1" for undocked/panel surfaces) is preserved for callers that
    need it.
    """
    entries: list[WindowEntry] = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        pieces = line.split(maxsplit=4)
        if len(pieces) < 5:
            continue
        window_id, desktop, _host, app_class, title = pieces
        app_class = app_class.split("/")[-1]
        entries.append(
            WindowEntry(window_id=window_id, app_class=app_class, title=title, desktop=desktop)
        )
    return entries


def parse_work_area(text: str) -> tuple[int, int, int, int] | None:
    """Read the panel-free work area out of ``wmctrl -d`` output.

    Real lines look like::

        0  * DG: 1366x768  VP: 0,0  WA: 0,30 1366x738  Workspace 1

    so after ``WA:`` the geometry is ``x,y`` then ``WxH`` (comma- and
    x-separated). The current desktop's line (marked ``*``) wins; otherwise the
    first line that carries a work area. Returns ``(x, y, width, height)``.
    """
    fallback: tuple[int, int, int, int] | None = None
    for line in text.splitlines():
        marker = line.find("WA:")
        if marker < 0:
            continue
        rest = line[marker + 3 :].split()
        if len(rest) < 2:
            continue
        try:
            x_text, y_text = rest[0].split(",", 1)
            w_text, h_text = rest[1].split("x", 1)
            area = int(x_text), int(y_text), int(w_text), int(h_text)
        except ValueError:
            continue
        if "*" in line:
            return area  # the desktop the user is looking at
        fallback = fallback or area
    return fallback


class SystemMonitor:
    """Collect one :class:`SystemSnapshot` and describe it in Kayla's voice."""

    def __init__(
        self,
        *,
        psutil_module: Any | None = None,
        run: Runner | None = None,
        top_count: int = 8,
    ) -> None:
        self._psutil = psutil_module or _load_psutil()
        self._run = run or _subprocess_runner
        self._top_count = top_count

    def snapshot(self) -> SystemSnapshot:
        """Take the whole reading in one go; missing pieces degrade gracefully."""
        psutil = self._psutil
        snapshot = SystemSnapshot()
        memory = psutil.virtual_memory()
        snapshot.ram_total_gb = memory.total / 1_000_000_000
        snapshot.ram_used_gb = memory.total - memory.available
        snapshot.ram_used_gb = snapshot.ram_used_gb / 1_000_000_000
        snapshot.ram_percent = memory.percent
        snapshot.cpu_percent = psutil.cpu_percent(interval=0.1)
        snapshot.battery_percent, snapshot.battery_plugged = self._battery(psutil)
        snapshot.top = self._top_processes()
        snapshot.windows = self._windows()
        return snapshot

    def describe(self) -> str:
        """Turn the snapshot into a short paragraph the model can quote."""
        snapshot = self.snapshot()
        ram = (
            f"RAM: {snapshot.ram_used_gb:.1f}/{snapshot.ram_total_gb:.1f} GB used"
            f" ({snapshot.ram_percent:.0f}%)"
        )
        lines = [
            ram,
            f"CPU: {snapshot.cpu_percent:.0f}%",
        ]
        if snapshot.battery_percent is not None:
            state = ""
            if snapshot.battery_plugged:
                state = " (plugged in)"
            lines.append(f"Battery: {snapshot.battery_percent:.0f}%{state}")
        else:
            lines.append("Battery: unknown (desktop power)")
        if snapshot.top:
            heavy = ", ".join(
                f"{entry.name} {entry.memory_mb:.0f} MB"
                for entry in snapshot.top[: self._top_count]
            )
            lines.append(f"Heaviest running programs: {heavy}")
        if snapshot.windows:
            windows = ", ".join(
                f"{_short_app_class(entry.app_class)}: {entry.title}" for entry in snapshot.windows
            )
            lines.append(f"Open windows: {windows}")
        else:
            lines.append("Open windows: could not read the window list (wmctrl missing?)")
        return "\n".join(lines)

    def _battery(self, psutil: Any) -> tuple[float | None, bool | None]:
        try:
            sensor = psutil.sensors_battery()
        except (AttributeError, NotImplementedError):
            return None, None
        if sensor is None:
            return None, None
        plugged = bool(sensor.power_plugged) if sensor.power_plugged is not None else None
        return float(sensor.percent), plugged

    def _top_processes(self) -> list[ProcessUsage]:
        grouped: dict[str, list[tuple[float, float]]] = {}
        for process in self._psutil.process_iter(attrs=["name", "memory_info", "cpu_percent"]):
            info = process.info
            name = str(info.get("name") or "").strip()
            if not name:
                continue
            rss = getattr(info.get("memory_info"), "rss", 0) or 0
            cpu = info.get("cpu_percent") or 0.0
            grouped.setdefault(name, []).append((rss, float(cpu)))
        usage = [
            ProcessUsage(
                name=name,
                memory_mb=sum(entry[0] for entry in rows) / 1_000_000,
                cpu_percent=sum(entry[1] for entry in rows),
            )
            for name, rows in grouped.items()
        ]
        usage.sort(key=lambda entry: entry.memory_mb, reverse=True)
        return usage[: self._top_count]

    def _windows(self) -> list[WindowEntry]:
        try:
            out, _err = self._run(["wmctrl", "-l", "-x"])
        except Exception:  # noqa: BLE001 - missing wmctrl or timeout is not fatal
            return []
        if not out.strip():
            return []
        return parse_wmctrl(out)
