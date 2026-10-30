"""Offline tests for listing/closing/focusing windows via wmctrl."""

from __future__ import annotations

from kayla.system.monitor import WindowEntry
from kayla.system.windowctl import WindowControl, _match, parse_stacking

_WMCTRL_OUT = (
    "0x04200001  0 host firefox.Firefox Gmail - Inbox\n"
    "0x04800002  0 host code.Code kayla-the-assistant - main.py\n"
    "0x05000003  0 host spotify-client.Spotify Spotify\n"
)

_WINDOWS = [
    WindowEntry("0x04200001", "firefox.Firefox", "Gmail - Inbox"),
    WindowEntry("0x04800002", "code.Code", "kayla-the-assistant - main.py"),
    WindowEntry("0x05000003", "spotify-client.Spotify", "Spotify"),
]


def _controller(out: str = _WMCTRL_OUT):
    calls: list[list[str]] = []

    def run(argv):
        calls.append(argv)
        if "-l" in argv:
            return 0, out, ""
        return 0, "", ""

    return WindowControl(run=run, which=lambda _n: "/usr/bin/wmctrl"), calls


def test_lists_windows():
    windows = _controller()[0].list()
    assert [w.app_class for w in windows] == [
        "firefox.Firefox",
        "code.Code",
        "spotify-client.Spotify",
    ]


def test_close_matches_class_and_title():
    control, calls = _controller()
    message = control.close("spotify")
    assert message == "Closed: Spotify: Spotify."
    assert ["wmctrl", "-i", "-c", "0x05000003"] in calls


def test_close_by_title_words():
    control, _calls = _controller()
    assert "Closed" in control.close("inbox")


def test_close_reports_misses():
    control, _calls = _controller()
    assert "No window matched" in control.close("minesweeper")


def test_activate_picks_best_match_and_focuses():
    control, calls = _controller()
    message = control.activate("fire")
    assert message.startswith("Focused Firefox")
    assert ["wmctrl", "-i", "-a", "0x04200001"] in calls


def test_match_prefers_exact_class_then_prefixes_then_titles():
    ranked = _match(_WINDOWS, "code")
    assert ranked[0].window_id == "0x04800002"
    assert _match(_WINDOWS, "mail")[0].window_id == "0x04200001"


def test_missing_wmctrl_degrades():
    control = WindowControl(run=None, which=lambda _n: None)  # type: ignore[arg-type]
    assert control.list() == []
    assert "refused" in control.close("x") or "couldn't list" in control.close("x")


# Several Chrome windows: raise the one the user had in front last (topmost).

_STACKING_MARK = "_NET_CLIENT_LIST_STACKING(WINDOW): window id # "


def test_parse_stacking_bottom_to_top():
    order = parse_stacking("  " + _STACKING_MARK + "0x04800002, 0x05000003, 0x04200001\n")
    assert order == [0x04800002, 0x05000003, 0x04200001]
    # Tolerate padding differences and stray tokens (xprop vs wmctrl formats).
    assert parse_stacking(_STACKING_MARK + "0x2600004, 0x3a0001e, junk") == [0x2600004, 0x3A0001E]
    assert parse_stacking("no ids here") == []
    assert parse_stacking("") == []


def _two_chrome_controller(stack_bottom_to_top: tuple[str, str]):
    """Two Chrome windows; the stack names the one used last."""
    out = (
        "0x0a000001  0 host google-chrome.Chrome Inbox - Gmail\n"
        "0x0b000002  0 host google-chrome.Chrome Documentation\n"
    )
    stack = _STACKING_MARK + f"{stack_bottom_to_top[0]}, {stack_bottom_to_top[1]}\n"
    calls: list[list[str]] = []

    def run(argv):
        calls.append(argv)
        if "-l" in argv:
            return 0, out, ""
        if argv[0] == "xprop":
            return 0, stack, ""
        return 0, "", ""

    control = WindowControl(
        run=run, which=lambda name: "/usr/bin/wmctrl" if name == "wmctrl" else "/usr/bin/xprop"
    )
    return control, calls


def test_activate_picks_the_topmost_of_several():
    control, calls = _two_chrome_controller(("0x0a000001", "0x0b000002"))
    message = control.activate("chrome")
    assert ["wmctrl", "-i", "-a", "0x0b000002"] in calls  # topmost wins
    assert message.startswith("Brought up Chrome: Documentation.")
    assert "picked the one you used last" in message


def test_activate_tracking_order_changes_the_pick():
    control, calls = _two_chrome_controller(("0x0b000002", "0x0a000001"))
    message = control.activate("google")
    assert ["wmctrl", "-i", "-a", "0x0a000001"] in calls  # now the Inbox is frontmost
    assert message.startswith("Brought up Chrome: Inbox - Gmail.")


def test_activate_without_stack_data_keeps_listing_order():
    out = (
        "0x0a000001  0 host google-chrome.Chrome Inbox - Gmail\n"
        "0x0b000002  0 host google-chrome.Chrome Documentation\n"
    )

    def run(argv):
        if "-l" in argv:
            return 0, out, ""
        return 0, "", ""

    control = WindowControl(
        run=run, which=lambda name: "/usr/bin/wmctrl" if name == "wmctrl" else "/usr/bin/xprop"
    )
    message = control.activate("chrome")
    assert message.startswith("Brought up Chrome: Inbox - Gmail.")


def test_activate_single_match_stays_quiet_about_stacking():
    control, calls = _controller()  # three distinct apps, one match for "fire"
    message = control.activate("fire")
    assert message.startswith("Focused Firefox: Gmail - Inbox.")
    assert "picked the one" not in message
    assert ["wmctrl", "-i", "-a", "0x04200001"] in calls


def test_activate_no_match_never_spawns_a_new_app():
    control, _calls = _controller()
    message = control.activate("minesweeper")
    assert message == "No window matched 'minesweeper'."
