"""Offline tests for the GNOME focus (notifications) controller."""

from __future__ import annotations

from kayla.system.focus import FocusMode


def recorder():
    calls: list[list[str]] = []

    def run(argv):
        calls.append(argv)
        if argv[1] == "get":
            last_set = next(iter([c for c in calls if c[1] == "set"]), None)
            value = last_set[-1] if last_set else "true"
            return 0, f"{value}\n"
        return 0, ""

    return run, calls


def test_on_silences_banners_and_sounds():
    run, calls = recorder()
    message = FocusMode(run=run, which=lambda _n: "/usr/bin/gsettings").on()
    assert message.startswith("Focus mode is ON")
    assert ["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "false"] in calls
    assert ["gsettings", "set", "org.gnome.desktop.sound", "event-sounds", "false"] in calls


def test_off_restores_banners_and_sounds():
    run, calls = recorder()
    message = FocusMode(run=run, which=lambda _n: "/x").off()
    assert message.startswith("Focus mode is OFF")
    assert ["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "true"] in calls


def test_missing_gsettings_reports_helpfully():
    message = FocusMode(run=None, which=lambda _n: None).on()  # type: ignore[arg-type]
    assert "gsettings" in message and "couldn't find" in message


def test_is_on_reflects_banners():
    run, _calls = recorder()
    mode = FocusMode(run=run, which=lambda _n: "/x")
    assert mode.is_on() is False  # nothing set yet -> banners default true


def test_gsettings_failure_is_explained():
    def failing(argv):
        return 1, "no schema org.gnome.desktop.notifications\n"

    message = FocusMode(run=failing, which=lambda _n: "/x").on()
    assert "couldn't silence" in message and "no schema" in message
