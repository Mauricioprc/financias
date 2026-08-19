import hashlib
import hmac
import json


def _signed(app, body: dict):
    app.config["WHATSAPP_APP_SECRET"] = "test-app-secret"
    raw = json.dumps(body).encode("utf-8")
    signature = hmac.new(b"test-app-secret", raw, hashlib.sha256).hexdigest()
    return raw, f"sha256={signature}"


def test_verify_webhook_returns_challenge_when_token_matches(client, app):
    app.config["WHATSAPP_VERIFY_TOKEN"] = "meu-token-secreto"

    resp = client.get(
        "/bot/webhook",
        query_string={
            "hub.mode": "subscribe",
            "hub.verify_token": "meu-token-secreto",
            "hub.challenge": "12345",
        },
    )
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "12345"


def test_verify_webhook_rejects_wrong_token(client, app):
    app.config["WHATSAPP_VERIFY_TOKEN"] = "meu-token-secreto"

    resp = client.get(
        "/bot/webhook",
        query_string={
            "hub.mode": "subscribe",
            "hub.verify_token": "token-errado",
            "hub.challenge": "12345",
        },
    )
    assert resp.status_code == 403


def test_verify_webhook_rejects_wrong_mode(client, app):
    app.config["WHATSAPP_VERIFY_TOKEN"] = "meu-token-secreto"

    resp = client.get(
        "/bot/webhook",
        query_string={
            "hub.mode": "unsubscribe",
            "hub.verify_token": "meu-token-secreto",
            "hub.challenge": "12345",
        },
    )
    assert resp.status_code == 403


def test_receive_webhook_rejects_missing_signature(client, app):
    app.config["WHATSAPP_APP_SECRET"] = "test-app-secret"
    resp = client.post("/bot/webhook", json={"entry": []})
    assert resp.status_code == 403


def test_receive_webhook_rejects_wrong_signature(client, app):
    app.config["WHATSAPP_APP_SECRET"] = "test-app-secret"
    resp = client.post(
        "/bot/webhook",
        data=json.dumps({"entry": []}),
        headers={"X-Hub-Signature-256": "sha256=deadbeef", "Content-Type": "application/json"},
    )
    assert resp.status_code == 403


def test_receive_webhook_acks_with_200_when_signature_valid(client, app):
    raw, header = _signed(app, {"entry": []})
    resp = client.post(
        "/bot/webhook", data=raw, headers={"X-Hub-Signature-256": header, "Content-Type": "application/json"}
    )
    assert resp.status_code == 200


def test_receive_webhook_ignores_status_only_payloads(client, app):
    """Payload de status (delivered/read/failed) não deve gerar erro nem
    tentar resolver usuário/enviar mensagem — só é ignorado."""
    payload = {
        "entry": [
            {
                "id": "waba",
                "changes": [
                    {
                        "value": {
                            "statuses": [{"id": "wamid.x", "status": "delivered"}],
                        },
                        "field": "messages",
                    }
                ],
            }
        ]
    }
    raw, header = _signed(app, payload)
    resp = client.post(
        "/bot/webhook", data=raw, headers={"X-Hub-Signature-256": header, "Content-Type": "application/json"}
    )
    assert resp.status_code == 200
