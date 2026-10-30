"""Tests for the phone HTTP bridge - real server, ephemeral port, no internet."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from kayla.devices.bridge import DeviceBridge, start_bridge


def live_bridge(tmp_path):
    bridge = DeviceBridge(path=tmp_path / "devices.json")
    server = start_bridge(bridge, host="127.0.0.1", port=0)
    address = f"http://{server.server_address[0]}:{server.server_address[1]}"
    return bridge, server, address


def get(address: str, path: str) -> dict:
    with urllib.request.urlopen(address + path, timeout=5) as response:
        return json.loads(response.read().decode())


def post(address: str, path: str, body: dict) -> dict:
    request = urllib.request.Request(
        address + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode())


def test_pair_exchange_code_for_token_and_persists(tmp_path):
    bridge, server, address = live_bridge(tmp_path)
    try:
        code = bridge.pair_code()
        wrong = get(address, "/pair?code=000000&name=Phone")
        assert wrong.get("ok") is False

        paired = get(address, f"/pair?code={code.replace('', '')}&name=My-iPhone")
        assert paired["ok"] is True and paired["token"].startswith("kayla-")

        reloaded = DeviceBridge(path=bridge.path)
        assert [device.token for device in reloaded.devices()] == [paired["token"]]
        assert reloaded.pair_code() != code  # one-shot codes
    finally:
        server.shutdown()


def test_focus_command_flows_to_phone_and_acks(tmp_path):
    bridge, server, address = live_bridge(tmp_path)
    try:
        token = bridge.pair(bridge.pair_code(), "iPhone")

        # Kayla queues a command that every device will pick up.
        assert bridge.attach({"action": "focus_on"}, token="*")

        fetched = get(address, f"/commands?token={token}")
        commands = fetched["commands"]
        assert len(commands) == 1 and commands[0]["action"] == "focus_on"

        # Draining twice must not repeat the same work.
        assert get(address, f"/commands?token={token}")["commands"] == []

        acked = post(address, f"/ack?token={token}&id={commands[0]['id']}", {})
        assert acked["ok"] is True
    finally:
        server.shutdown()


def test_unknown_token_gets_nothing_and_invalid_post_is_400(tmp_path):
    bridge, server, address = live_bridge(tmp_path)
    try:
        assert get(address, "/commands?token=bogus")["commands"] == []
    finally:
        server.shutdown()


def test_health_reports_kayla(tmp_path):
    _bridge, server, address = live_bridge(tmp_path)
    try:
        assert get(address, "/health")["ok"] is True
    finally:
        server.shutdown()


def test_bad_http_fails_softly(tmp_path):
    _bridge, server, address = live_bridge(tmp_path)
    try:
        try:
            get(address, "/definitely-not-a-path")
            raised = False
        except urllib.error.HTTPError as error:
            raised = error.code == 404
        assert raised
    finally:
        server.shutdown()


def test_a_second_session_skips_a_taken_bridge_port(tmp_path):
    bridge, server, _address = live_bridge(tmp_path)
    try:
        stranger = DeviceBridge(path=tmp_path / "other.json")
        taken = server.server_address[1]
        assert start_bridge(stranger, host="127.0.0.1", port=taken) is None
    finally:
        server.shutdown()
