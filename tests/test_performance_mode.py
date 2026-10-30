"""Offline tests for the power-profile performance controller."""

from __future__ import annotations

from kayla.system.performance import PROFILES, PerformanceMode


def test_set_normalizes_aliases():
    calls: list[list[str]] = []

    def run(argv):
        calls.append(argv)
        return 0, ""

    mode = PerformanceMode(run=run, which=lambda _n: "/x")
    for spoken, expected in {
        "best": "performance",
        "turbo": "performance",
        "normal": "balanced",
        "eco": "power-saver",
        "balanced": "balanced",
    }.items():
        assert "set" in mode.set(spoken)
        assert calls[-1] == ["powerprofilesctl", "set", expected]


def test_set_rejects_unknown_profile():
    mode = PerformanceMode(run=None, which=lambda _n: "/x")  # type: ignore[arg-type]
    message = mode.set("hyper-drive")
    assert "must be one of" in message
    assert set(PROFILES).issuperset({"performance", "balanced", "power-saver"})


def test_missing_tool_reports_cleanly():
    mode = PerformanceMode(run=None, which=lambda _n: None)  # type: ignore[arg-type]
    assert "power-profiles-daemon" in mode.set("performance")


def test_runner_failure_is_surfaced():
    def failing(argv):
        return 1, "Error: access denied"

    assert "access denied" in PerformanceMode(run=failing, which=lambda _n: "/x").set("performance")


def test_current_reads_daemon():
    assert (
        PerformanceMode(run=lambda argv: (0, "performance\n"), which=lambda _n: "/x").current()
        == "performance"
    )
