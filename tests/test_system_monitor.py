"""Offline tests for the laptop monitor (injected psutil + fake wmctrl)."""

from __future__ import annotations

from types import SimpleNamespace

from kayla.system.monitor import SystemMonitor, parse_wmctrl


def _fake_psutil():
    return SimpleNamespace(
        virtual_memory=lambda: SimpleNamespace(
            total=16_000_000_000, available=10_000_000_000, percent=37.5
        ),
        cpu_percent=lambda interval=None: 12.0,
        sensors_battery=lambda: SimpleNamespace(percent=84.0, power_plugged=True),
        process_iter=lambda attrs: [
            SimpleNamespace(
                info={
                    "name": "firefox",
                    "memory_info": SimpleNamespace(rss=1_400_000_000),
                    "cpu_percent": 8.0,
                }
            ),
            SimpleNamespace(
                info={
                    "name": "firefox",
                    "memory_info": SimpleNamespace(rss=200_000_000),
                    "cpu_percent": 2.0,
                }
            ),
            SimpleNamespace(
                info={
                    "name": "code",
                    "memory_info": SimpleNamespace(rss=700_000_000),
                    "cpu_percent": 5.0,
                }
            ),
            SimpleNamespace(info={"name": "", "memory_info": None, "cpu_percent": 0}),
        ],
    )


def test_parse_wmctrl_reads_windows():
    entries = parse_wmctrl(
        "0x05800003  0 host gnome-terminal-server.Gnome-terminal Kayla\n"
        "0x04200001 -1 host firefox.Firefox Gmail - Inbox\n"
    )
    assert [entry.app_class for entry in entries] == [
        "gnome-terminal-server.Gnome-terminal",
        "firefox.Firefox",
    ]
    assert entries[1].title == "Gmail - Inbox"
    assert entries[0].window_id == "0x05800003"


def test_parse_wmctrl_skips_garbage():
    assert parse_wmctrl("") == []
    assert parse_wmctrl("\nonly three words") == []


def test_snapshot_reports_memory_cpu_battery_and_windows():
    runner = lambda argv: (  # noqa: E731 - tiny test double
        "0x04200001 -1 host firefox.Firefox Gmail - Inbox\n",
        "",
    )
    monitor = SystemMonitor(psutil_module=_fake_psutil(), run=runner)
    snapshot = monitor.snapshot()
    assert snapshot.ram_total_gb == 16.0
    assert snapshot.ram_percent == 37.5
    assert snapshot.cpu_percent == 12.0
    assert snapshot.battery_percent == 84.0
    assert snapshot.battery_plugged is True
    top = {entry.name: entry for entry in snapshot.top}
    assert top["firefox"].memory_mb == 1600.0
    assert top["firefox"].cpu_percent == 10.0
    assert [entry.app_class for entry in snapshot.windows] == ["firefox.Firefox"]


def test_describe_is_readable_prose():
    runner = lambda argv: ("0x04200001 -1 host firefox.Firefox Gmail\n", "")  # noqa: E731
    text = SystemMonitor(psutil_module=_fake_psutil(), run=runner).describe()
    assert "RAM: 6.0/16.0 GB used" in text
    assert "CPU: 12%" in text
    assert "Battery: 84% (plugged in)" in text
    assert "firefox 1600 MB" in text
    assert "Firefox: Gmail" in text


def test_missing_battery_and_windows_degrade():
    psutil = SimpleNamespace(
        virtual_memory=lambda: SimpleNamespace(total=8, available=0, percent=0.0),
        cpu_percent=lambda interval=None: 0.0,
        sensors_battery=lambda: None,
        process_iter=lambda attrs: [],
    )

    def boom(argv):
        raise FileNotFoundError("wmctrl missing")

    monitor = SystemMonitor(psutil_module=psutil, run=boom)
    snapshot = monitor.snapshot()
    assert snapshot.battery_percent is None
    assert snapshot.windows == []
    assert "unknown (desktop power)" in monitor.describe()
