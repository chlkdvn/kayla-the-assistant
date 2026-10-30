"""Offline tests for boot autostart: unit contents and install/remove (tmp home)."""

from __future__ import annotations

from pathlib import Path

from kayla.setup import boot


def test_service_unit_runs_the_realtime_session() -> None:
    unit = boot.service_unit()

    assert "ExecStart=" in unit
    assert "kayla.interfaces.realtime_cli" in unit
    assert "graphical-session.target" in unit
    assert "Restart=on-failure" in unit
    assert unit.count("Type=") == 1  # exactly one valid Type line


def test_desktop_entry_makes_kayla_searchable() -> None:
    entry = boot.desktop_entry()

    assert "Name=Kayla" in entry
    assert "Terminal=false" in entry
    assert "kayla.interfaces.cli" in entry


def test_service_unit_includes_working_directory_when_config_exists(tmp_path: Path) -> None:
    (tmp_path / ".config" / "kayla").mkdir(parents=True)
    (tmp_path / ".config" / "kayla" / ".env").write_text("GROQ_API_KEY=x\n")

    unit = boot.service_unit(home=tmp_path)

    assert f"WorkingDirectory={tmp_path / '.config' / 'kayla'}" in unit


def test_install_writes_both_files_and_enables(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_ctl(argv: list[str]) -> tuple[int, str]:
        calls.append(argv)
        return 0, ""

    report = boot.install(run=fake_ctl, home=tmp_path)

    service = tmp_path / ".config" / "systemd" / "user" / "kayla.service"
    entry = tmp_path / ".local" / "share" / "applications" / "kayla.desktop"
    assert service.is_file()
    assert entry.is_file()
    assert "Boot service enabled" in report
    assert ["systemctl", "--user", "daemon-reload"] in calls
    assert ["systemctl", "--user", "enable", "--now", "kayla.service"] in calls


def test_remove_disables_and_unlinks(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_ctl(argv: list[str]) -> tuple[int, str]:
        calls.append(argv)
        return 0, ""

    boot.install(run=fake_ctl, home=tmp_path)
    report = boot.remove(run=fake_ctl, home=tmp_path)

    assert not (tmp_path / ".config" / "systemd" / "user" / "kayla.service").exists()
    assert not (tmp_path / ".local" / "share" / "applications" / "kayla.desktop").exists()
    assert ["systemctl", "--user", "disable", "--now", "kayla.service"] in calls
    assert "Boot service disabled" in report


def test_status_reports_installed_files(tmp_path: Path) -> None:
    assert "not installed" in boot.status(home=tmp_path)
    boot.install(run=lambda _argv: (0, ""), home=tmp_path)
    report = boot.status(home=tmp_path)
    assert "boot service unit: installed" in report
    assert "desktop entry:     installed" in report


def test_install_reports_how_to_enable_when_systemctl_fails(tmp_path: Path) -> None:
    report = boot.install(run=lambda _argv: (3, "no systemd"), home=tmp_path)

    assert "systemctl --user enable --now kayla.service" in report
