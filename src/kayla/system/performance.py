"""Switch the laptop's power profile for best performance or battery life.

Supported profiles come from ``power-profiles-daemon`` (``powerprofilesctl``),
the standard on modern GNOME systems. Kayla rejects unknown profiles and
explains when the daemon is missing rather than failing.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable

PROFILES: tuple[str, ...] = ("performance", "balanced", "power-saver")

Runner = Callable[[list[str]], tuple[int, str]]


def _subprocess_runner(argv: list[str]) -> tuple[int, str]:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=8, check=False)
    return result.returncode, result.stderr


class PerformanceMode:
    """Set and read the system power profile."""

    def __init__(
        self, *, run: Runner | None = None, which: Callable[[str], str | None] | None = None
    ) -> None:
        self._run = run or _subprocess_runner
        self._which = which or shutil.which

    def set(self, profile: str) -> str:
        """Apply one of the known profiles and report the result in plain words."""
        profile = profile.strip().lower()
        if profile in {"best", "max", "turbo", "full"}:
            profile = "performance"
        if profile in {"normal", "default"}:
            profile = "balanced"
        if profile in {"battery", "silent", "eco", "battery-saver"}:
            profile = "power-saver"
        if profile not in PROFILES:
            return "Power profile must be one of: " + ", ".join(PROFILES) + "."
        if self._which("powerprofilesctl") is None:
            return (
                "Power profiles need power-profiles-daemon - 'powerprofilesctl' "
                "is not installed on this machine."
            )
        try:
            code, err = self._run(["powerprofilesctl", "set", profile])
        except Exception as error:  # noqa: BLE001 - surface instead of crash
            return f"Couldn't switch the power profile: {error}"
        if code != 0:
            text = err.strip().splitlines()[-1] if err.strip() else f"exit {code}"
            return f"Couldn't switch the power profile: {text}"
        word = {
            "performance": "Best performance (max CPU clocks)",
            "balanced": "Balanced power",
            "power-saver": "Battery saver",
        }[profile]
        return f"Power profile set: {word}."

    def current(self) -> str:
        """The active profile, or why it couldn't be read."""
        if self._which("powerprofilesctl") is None:
            return "Power profile unknown ('powerprofilesctl' is not installed)."
        try:
            code, out = self._run(["powerprofilesctl", "get"])
        except Exception as error:  # noqa: BLE001
            return f"Power profile unknown ({error})"
        return out.strip() if code == 0 else "Power profile unknown."
