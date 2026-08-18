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


def test_receive_webhook_acks_with_200(client):
    resp = client.post("/bot/webhook", json={"entry": []})
    assert resp.status_code == 200
