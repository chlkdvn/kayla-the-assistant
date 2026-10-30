"""Find installed desktop applications and open them the way the desktop would.

Kayla reads ``.desktop`` entries from the standard XDG locations, matches a
spoken name against them ("open Spotify", "launch the calculator"), and starts
the app detached. ``gtk-launch`` is preferred because the desktop session
handles environment, icon and grouping; ``gio launch`` is the fallback.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

Runner = Callable[[list[str]], tuple[int, str]]
"""Run one launch command; return (returncode, stderr)."""


def _subprocess_runner(argv: list[str]) -> tuple[int, str]:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=12, check=False)
    return result.returncode, result.stderr


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def _app_dirs() -> list[Path]:
    """Standard application-entry directories (XDG + Flatpak exports)."""
    home = Path.home()
    data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    candidates = [
        data_home / "applications",
        Path("/usr/share/applications"),
        Path("/var/lib/flatpak/exports/share/applications"),
        home / ".local/share/flatpak/exports/share/applications",
    ]
    seen: list[Path] = []
    for path in candidates:
        if path.is_dir() and path not in seen:
            seen.append(path)
    return seen


@dataclass(frozen=True)
class DesktopApp:
    """One installed app entry."""

    name: str
    app_id: str
    path: Path
    exec_line: str = ""


def _parse_desktop_file(path: Path) -> DesktopApp | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    section = False
    name = ""
    exec_line = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            section = stripped == "[Desktop Entry]"
            continue
        if not section or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if key == "Name" and not name:
            name = value.strip()
        elif key == "Exec" and not exec_line:
            exec_line = value.strip()
        elif (
            key in {"NoDisplay", "Hidden"}
            and _parse_bool(value)
            or key == "Type"
            and value.strip() != "Application"
        ):
            return None
    if not name or not exec_line:
        return None
    return DesktopApp(name=name, app_id=path.stem, path=path, exec_line=exec_line)


class DesktopApps:
    """Index installed apps and open them on request."""

    def __init__(
        self,
        *,
        directories: list[Path] | None = None,
        run: Runner | None = None,
        which: Callable[[str], str | None] = None,
    ) -> None:
        import shutil

        self._directories = directories or _app_dirs()
        self._run = run or _subprocess_runner
        self._which = which or shutil.which
        self._cache: list[DesktopApp] | None = None

    def list(self) -> list[DesktopApp]:
        """Installed apps, sorted by name (cached; call ``refresh`` to force)."""
        if self._cache is None:
            self._cache = self.refresh()
        return self._cache

    def refresh(self) -> list[DesktopApp]:
        """Re-read every application directory."""
        found: dict[str, DesktopApp] = {}
        for directory in self._directories:
            if not directory.is_dir():
                continue
            for path in sorted(directory.iterdir()):
                if path.suffix != ".desktop":
                    continue
                app = _parse_desktop_file(path)
                if app is None:
                    continue
                # Later directories win (user entries override system ones).
                found[app.name.casefold()] = app
        apps = sorted(found.values(), key=lambda app: app.name.casefold())
        self._cache = apps
        return apps

    def find(self, query: str) -> DesktopApp | None:
        """Best-effort match for a spoken or typed app name."""
        apps = self.list()
        needle = query.strip().casefold()
        if not needle:
            return None
        for app in apps:
            if app.name.casefold() == needle or app.app_id.casefold() == needle:
                return app
        startswith: list[DesktopApp] = []
        contains: list[DesktopApp] = []
        for app in apps:
            folded = app.name.casefold()
            if folded.startswith(needle):
                startswith.append(app)
            elif needle in folded or needle in app.app_id.casefold():
                contains.append(app)
        return startswith[0] if startswith else (contains[0] if contains else None)

    def open(self, query: str) -> str:
        """Launch an app by name and report what happened, in Kayla's voice."""
        app = self.find(query)
        if app is None:
            return f"I couldn't find an installed app called '{query}'."
        try:
            self.launch(app)
        except Exception as error:  # noqa: BLE001 - launch issues surface to the model
            return f"'{app.name}' failed to open: {error}"
        return f"Opened {app.name}."

    def launch(self, app: DesktopApp) -> None:
        """Start the app detached from Kayla via the desktop launcher."""
        if self._which("gtk-launch"):
            argv = ["gtk-launch", app.app_id]
        elif self._which("gio"):
            argv = ["gio", "launch", str(app.path)]
        else:
            argv = ["/bin/sh", "-c", _strip_specifiers(app.exec_line) + " >/dev/null 2>&1 &"]
        code, err = self._run(argv)
        if code != 0 and err.strip():
            raise RuntimeError(err.strip().splitlines()[-1])


def _strip_specifiers(exec_line: str) -> str:
    """Drop desktop-entry field codes like %u or %f that a plain shell can't use."""
    words = [word for word in exec_line.split() if not (len(word) == 2 and word.startswith("%"))]
    return " ".join(words)
