"""Close the terminal that launched Kayla - the safe way.

Typing ``kayla`` is meant to end with a floating orb and no terminal left
beholding. Walking ``/proc`` upward from the running process finds the nearest
ancestor shell (bash/zsh/fish...), which owns that interactive tab, and stops
it. Guardrails: only known shell names count, only the FIRST shell ancestor is
stopped, pid 1 is never touched, and nothing is killed when the chain has no
shell at all (for example when started programmatically).

The whole walk is injectable so tests can feed a fake ``/proc`` tree without
touching the running system.
"""

from __future__ import annotations

import os
import signal
from collections.abc import Callable
from pathlib import Path

SHELL_NAMES: frozenset[str] = frozenset({"bash", "zsh", "fish", "dash", "sh", "ksh", "tcsh", "ion"})


def read_status(proc_root: Path, pid: int) -> dict[str, str]:
    """Parse a ``/proc/<pid>/status`` file into its simple KEY: value fields."""
    fields: dict[str, str] = {}
    try:
        text = (proc_root / str(pid) / "status").read_text(errors="replace")
    except OSError:
        return fields
    for line in text.splitlines():
        key, _, value = line.partition(":")
        if _:
            fields[key.strip()] = value.strip()
    return fields


def ancestor_chain(start_pid: int, *, proc_root: str = "/proc") -> list[int]:
    """The pid chain from ``start_pid`` up to (excluding) pid 1.

    Handles missing/hidden entries (permissions, already-exited) and breaks on
    loops, which stale containers can produce.
    """
    root = Path(proc_root)
    chain: list[int] = []
    seen: set[int] = set()
    current = start_pid
    while current > 1 and current not in seen:
        seen.add(current)
        fields = read_status(root, current)
        parent_text = fields.get("PPid", "0")
        try:
            parent = int(parent_text)
        except ValueError:
            break
        if parent <= 1:
            break
        chain.append(parent)
        current = parent
    return chain


def shell_ancestor(start_pid: int, *, proc_root: str = "/proc") -> int | None:
    """The pid of the nearest ancestor shell, if any."""
    root = Path(proc_root)
    for pid in ancestor_chain(start_pid, proc_root=proc_root):
        name = read_status(root, pid).get("Name", "").partition(" ")[0]
        if name.casefold() in SHELL_NAMES:
            return pid
    return None


def close_calling_terminal(
    *,
    start_pid: int | None = None,
    proc_root: str = "/proc",
    kill: Callable[[int, int], None] | None = None,
) -> str:
    """Stop the shell session behind this process - closing its terminal tab.

    Returns a human explanation in every case, and NEVER raises: the orb must
    keep floating even here.
    """
    pid = start_pid if start_pid is not None else os.getpid()
    stop = kill if kill is not None else _stop_pid
    target = shell_ancestor(pid, proc_root=proc_root)
    if target is None:
        return "No launching terminal found - nothing to close."
    name = read_status(Path(proc_root), target).get("Name", "shell").partition(" ")[0]
    try:
        stop(target, signal.SIGTERM)
    except Exception as error:  # noqa: BLE001 - never crash over terminal cleanup
        return f"Couldn't close the connecting terminal ({error}); Kayla still floats on."
    return f"Closed the connecting {name} terminal (pid {target})."


def _stop_pid(pid: int, sig: int) -> None:
    os.kill(pid, sig)
