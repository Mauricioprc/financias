"""Testes do retry de rede em bot/whatsapp_client.py — só erro de
rede/timeout deve ser retentado; erro HTTP (4xx/5xx) da própria API é
definitivo e não deve gerar nova tentativa."""

import pytest
import requests

from bot import whatsapp_client


class _FakeResponse:
    def __init__(self, status_code=200, json_body=None):
        self.status_code = status_code
        self.ok = status_code < 400
        self._json_body = json_body or {}
        self.content = b"1" if json_body is not None else b""

    def json(self):
        return self._json_body


def test_succeeds_after_transient_network_failures(app, monkeypatch):
    app.config["WHATSAPP_PHONE_NUMBER_ID"] = "123"
    app.config["WHATSAPP_ACCESS_TOKEN"] = "token"

    calls = {"count": 0}

    def _fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.exceptions.ConnectionError("falha de rede")
        return _FakeResponse(200, {"messages": [{"id": "wamid.1"}]})

    monkeypatch.setattr(whatsapp_client.requests, "post", _fake_post)
    monkeypatch.setattr(whatsapp_client.time, "sleep", lambda _: None)

    with app.app_context():
        result = whatsapp_client.send_text("5511999999999", "oi")

    assert calls["count"] == 3
    assert result == {"messages": [{"id": "wamid.1"}]}


def test_gives_up_after_exhausting_retry_attempts(app, monkeypatch):
    app.config["WHATSAPP_PHONE_NUMBER_ID"] = "123"
    app.config["WHATSAPP_ACCESS_TOKEN"] = "token"

    calls = {"count": 0}

    def _fake_post(*args, **kwargs):
        calls["count"] += 1
        raise requests.exceptions.Timeout("timeout")

    monkeypatch.setattr(whatsapp_client.requests, "post", _fake_post)
    monkeypatch.setattr(whatsapp_client.time, "sleep", lambda _: None)

    with app.app_context(), pytest.raises(whatsapp_client.WhatsAppApiError):
        whatsapp_client.send_text("5511999999999", "oi")

    assert calls["count"] == whatsapp_client.NETWORK_RETRY_ATTEMPTS


def test_http_error_response_is_not_retried(app, monkeypatch):
    app.config["WHATSAPP_PHONE_NUMBER_ID"] = "123"
    app.config["WHATSAPP_ACCESS_TOKEN"] = "token"

    calls = {"count": 0}

    def _fake_post(*args, **kwargs):
        calls["count"] += 1
        return _FakeResponse(401, {"error": {"message": "token inválido"}})

    monkeypatch.setattr(whatsapp_client.requests, "post", _fake_post)
    monkeypatch.setattr(whatsapp_client.time, "sleep", lambda _: None)

    with app.app_context(), pytest.raises(whatsapp_client.WhatsAppApiError):
        whatsapp_client.send_text("5511999999999", "oi")

    assert calls["count"] == 1
