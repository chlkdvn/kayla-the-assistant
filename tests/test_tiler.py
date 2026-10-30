"""Offline tests for screen tiling (fake wmctrl, pure grid math)."""

from __future__ import annotations

from kayla.system.tiler import WindowTiler, grid_rects, parse_work_area

_WINDOWS = (
    "0x04200001  0 host firefox.Firefox Gmail\n"
    "0x04800002  0 host code.Code main.py\n"
    "0x05000003  0 host spotify-client.Spotify Spotify\n"
    "0x05000004  0 host x-dock.Dock helper\n"
    "0x06000005 -1 host plank.Plank\n"
)

FULL = (0, 0, 1920, 1080)

# The owner's laptop: GNOME on X11, 1366x768 with a 30px top bar strut.
LAPTOP = (0, 30, 1366, 738)


def _test_area_output() -> str:
    return "0  * DG: 1366x768  VP: 0,0  WA: 0,30 1366x738  Workspace 1\n"


def _tiler(calls: list[list[str]]):
    def run(argv):
        calls.append(argv)
        out = _WINDOWS if "-l" in argv else _test_area_output()
        return 0, out, ""

    return WindowTiler(run=run, which=lambda _n: "/usr/bin/wmctrl")


def test_parse_work_area():
    assert parse_work_area(_test_area_output()) == (0, 30, 1366, 738)
    assert parse_work_area("no work area here") is None
    # A desktop without the current marker still supplies a fallback area...
    other = "1  - DG: 1366x768  VP: 0,0  WA: 0,30 1366x738  Workspace 2\n"
    assert parse_work_area(other) == (0, 30, 1366, 738)
    # ...and multiple lines prefer the *current* desktop.
    desks = other + "0  * DG: 1366x768  VP: 0,0  WA: 0,30 1366x738  Workspace 1\n"
    assert parse_work_area(desks) == (0, 30, 1366, 738)
    # Older comma-format sizes no longer parse; refuse to guess.
    assert parse_work_area("0  * DG: 1366x768  WA: 28,30  1864,1020") is None


def test_grid_rects_for_two_three_and_four():
    two = grid_rects(2, FULL)
    assert two[0] == (0, 0, 960, 1080)
    assert two[1] == (960, 0, 960, 1080)

    four = grid_rects(4, FULL)
    assert four[0] == (0, 0, 960, 540)
    assert four[3] == (960, 540, 960, 540)

    three = grid_rects(3, FULL)
    assert three[0] == (0, 0, 640, 1080)
    assert three[2] == (1280, 0, 640, 1080)

    assert grid_rects(0, FULL) == []


def test_grid_rects_respect_work_area_origin():
    # The top bar struts 30px: rows shift down and heights come from the area.
    assert grid_rects(4, LAPTOP)[0] == (0, 30, 683, 369)
    assert grid_rects(4, LAPTOP)[3] == (683, 399, 683, 369)


def test_split_tiles_four_into_quadrants():
    calls: list[list[str]] = []
    tiler = _tiler(calls)
    message = tiler.split(4)
    assert "2x2" in message
    moves = [argv for argv in calls if "-e" in argv]
    assert len(moves) == 4  # the sticky plank window was skipped
    assert moves[0][5] == "0,0,30,683,369"
    assert moves[3][5] == "0,683,399,683,369"


def test_split_two_halves_and_focuses():
    calls: list[list[str]] = []
    tiler = _tiler(calls)
    assert "two halves" in tiler.split(2)
    moves = [argv for argv in calls if "-e" in argv]
    assert moves[0][5] == "0,0,30,683,738"


def test_missing_wmctrl_explains():
    tiler = WindowTiler(run=None, which=lambda _n: None)  # type: ignore[arg-type]
    assert "wmctrl" in tiler.split(4)


def test_no_windows_explains():
    calls: list[list[str]] = []

    def empty_run(argv):
        calls.append(argv)
        return 0, "", ""

    tiler = WindowTiler(run=empty_run, which=lambda _n: "/x")
    assert "no tile-able windows" in tiler.split(2)


def test_clamps_count():
    tiler = _tiler([])
    assert tiler.split(99).endswith("into three columns.") or "3" in tiler.split(3)
