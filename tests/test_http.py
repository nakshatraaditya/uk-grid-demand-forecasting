from __future__ import annotations
import pytest
import requests

from griddemand import http as http_mod


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def flaky_get(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.ConnectionError("blip")
        return FakeResponse({"ok": True})

    monkeypatch.setattr(http_mod.requests, "get", flaky_get)
    monkeypatch.setattr(http_mod.time, "sleep", lambda s: None)  # don't wait in tests

    assert http_mod.get_json("https://example.com") == {"ok": True}
    assert calls["n"] == 3


def test_gives_up_after_max_retries(monkeypatch):
    def always_fails(url, params=None, timeout=None):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(http_mod.requests, "get", always_fails)
    monkeypatch.setattr(http_mod.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError, match="failed after"):
        http_mod.get_json("https://example.com")