"""Offline tests for finding and opening installed desktop apps."""

from __future__ import annotations

from pathlib import Path

from kayla.system.apps import DesktopApps, _strip_specifiers

_SIMPLE = """
[Desktop Entry]
Name=Firefox Web Browser
Exec=firefox %u
Type=Application
"""

_NO_DISPLAY = """
[Desktop Entry]
Name=Hidden Tool
Exec=hidden %f
NoDisplay=true
Type=Application
"""

_LINK = """
[Desktop Entry]
Name=Code - OSS
Exec=/usr/share/code/code %F
Type=Link
"""


def _write_apps(tmp_path: Path) -> Path:
    apps = tmp_path / "applications"
    apps.mkdir()
    (apps / "firefox.desktop").write_text(_SIMPLE)
    (apps / "hidden.desktop").write_text(_NO_DISPLAY)
    (apps / "code-oss-link.desktop").write_text(_LINK, encoding="utf-8", errors="ignore")
    return apps


def test_list_parses_entries_and_skips_hidden(tmp_path: Path):
    apps = DesktopApps(directories=[_write_apps(tmp_path)])
    names = [app.name for app in apps.list()]
    assert names == ["Firefox Web Browser"]
    assert apps.list()[0].app_id == "firefox"


def test_find_matches_exact_prefix_and_contains(tmp_path: Path):
    apps = DesktopApps(directories=[_write_apps(tmp_path)])
    assert apps.find("firefox web browser").app_id == "firefox"
    assert apps.find("Firefox").app_id == "firefox"
    assert apps.find("fire").app_id == "firefox"
    assert apps.find("nothing-else") is None


def test_open_uses_gtk_launch_when_available(tmp_path: Path):
    calls: list[list[str]] = []
    apps = DesktopApps(
        directories=[_write_apps(tmp_path)],
        run=lambda argv: calls.append(argv) or (0, ""),
        which=lambda name: "/usr/bin/gtk-launch" if name == "gtk-launch" else None,
    )
    message = apps.open("firefox")
    assert message == "Opened Firefox Web Browser."
    assert calls == [["gtk-launch", "firefox"]]


def test_open_falls_back_to_gio_then_exec_line(tmp_path: Path):
    calls: list[list[str]] = []
    apps = DesktopApps(
        directories=[_write_apps(tmp_path)],
        run=lambda argv: calls.append(argv) or (0, ""),
        which=lambda _name: None,
    )
    apps.open("firefox")
    argv = calls[-1]
    assert argv[0] == "/bin/sh"
    assert "firefox" in argv[2]
    assert "%U" not in argv[2]


def test_open_reports_missing_app(tmp_path: Path):
    apps = DesktopApps(directories=[_write_apps(tmp_path)])
    assert "couldn't find" in apps.open("zune")


def test_gio_middle_path(tmp_path: Path):
    calls: list[list[str]] = []
    apps = DesktopApps(
        directories=[_write_apps(tmp_path)],
        run=lambda argv: calls.append(argv) or (0, ""),
        which=lambda name: "/usr/bin/gio" if name == "gio" else None,
    )
    apps.open("firefox")
    assert calls[-1][0] == "gio"
    assert calls[-1][1] == "launch"


def test_strip_specifiers_removes_field_codes():
    assert _strip_specifiers("code %F --open %U") == "code --open"
    assert _strip_specifiers("keep%%this") == "keep%%this"
