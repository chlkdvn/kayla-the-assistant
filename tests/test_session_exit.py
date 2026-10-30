"""Offline tests for closing the terminal that launched Kayla."""

from __future__ import annotations

from pathlib import Path

from kayla.system.session_exit import ancestor_chain, close_calling_terminal, shell_ancestor


def make_proc(root: Path, tree: dict[str, dict[str, str]]) -> None:
    """Fake /proc: ``tree["42"] = {"Name": "bash", "PPid": "40"}`` etc."""
    for pid, fields in tree.items():
        directory = root / pid
        directory.mkdir(parents=True)
        lines = "".join(f"{key}: {value}\n" for key, value in fields.items())
        (directory / "status").write_text(lines)


def test_walks_up_until_pid_one(tmp_path: Path):
    make_proc(
        tmp_path,
        {
            "400": {"Name": "gnome-terminal-Server", "PPid": "1"},
            "405": {"Name": "bash", "PPid": "400"},
            "410": {"Name": "uv", "PPid": "405"},
            "412": {"Name": "python", "PPid": "410"},
        },
    )
    assert ancestor_chain(412, proc_root=str(tmp_path)) == [410, 405, 400]


def test_finds_nearest_shell(tmp_path: Path):
    make_proc(
        tmp_path,
        {
            "400": {"Name": "gnome-terminal-Server", "PPid": "1"},
            "405": {"Name": "bash", "PPid": "400"},
            "410": {"Name": "uv", "PPid": "405"},
            "412": {"Name": "python", "PPid": "410"},
        },
    )
    assert shell_ancestor(412, proc_root=str(tmp_path)) == 405


kills: list[tuple[int, int]] = []


def test_closes_the_shell_and_reports(tmp_path: Path):
    make_proc(
        tmp_path,
        {"400": {"Name": "bash", "PPid": "1"}, "405": {"Name": "uv", "PPid": "400"}},
    )
    killed: list[tuple[int, int]] = []

    def killer(pid: int, sig: int) -> None:
        killed.append((pid, sig))

    message = close_calling_terminal(start_pid=405, proc_root=str(tmp_path), kill=killer)
    assert "bash" in message and "400" in message
    assert killed == [(400, 15)]


def test_without_shell_does_nothing(tmp_path: Path):
    make_proc(tmp_path, {"400": {"Name": "gnome-shell", "PPid": "1"}})
    killed: list[tuple[int, int]] = []

    def killer(pid: int, sig: int) -> None:
        killed.append((pid, sig))

    message = close_calling_terminal(start_pid=400, proc_root=str(tmp_path), kill=killer)
    assert "nothing to close" in message
    assert killed == []


def test_missing_proc_entries_terminate_chain(tmp_path: Path):
    # /proc has only the process itself; the unreadable ancestor is listed
    # (from PPid) but confidently resolves to NO shell.
    make_proc(tmp_path, {"9": {"Name": "python", "PPid": "999"}})
    assert ancestor_chain(9, proc_root=str(tmp_path)) == [999]
    assert shell_ancestor(9, proc_root=str(tmp_path)) is None


def test_kill_failure_is_a_message_not_a_crash(tmp_path: Path):
    make_proc(tmp_path, {"400": {"Name": "zsh", "PPid": "1"}, "405": {"Name": "uv", "PPid": "400"}})

    def killer(pid: int, sig: int) -> None:
        raise PermissionError("nope")

    message = close_calling_terminal(start_pid=405, proc_root=str(tmp_path), kill=killer)
    assert "Couldn't close" in message and "nope" in message
