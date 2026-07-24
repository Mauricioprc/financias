def _create_card(client, headers, closing_day=10, due_day=20):
    resp = client.post(
        "/api/v1/credit-cards",
        json={
            "name": "Nubank Ultravioleta",
            "credit_limit": 5000.0,
            "closing_day": closing_day,
            "due_day": due_day,
        },
        headers=headers,
    )
    return resp.get_json()["data"]["id"]


def test_create_list_get_update_credit_card(client, auth_headers):
    headers = auth_headers()

    resp = client.post(
        "/api/v1/credit-cards",
        json={"name": "Nubank", "credit_limit": 3000.0, "closing_day": 5, "due_day": 15},
        headers=headers,
    )
    assert resp.status_code == 201
    card = resp.get_json()["data"]
    card_id = card["id"]
    assert card["credit_limit"] == "3000.00"

    resp = client.get("/api/v1/credit-cards", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["meta"]["total"] == 1

    resp = client.get(f"/api/v1/credit-cards/{card_id}", headers=headers)
    assert resp.status_code == 200

    resp = client.patch(
        f"/api/v1/credit-cards/{card_id}", json={"name": "Nubank Renomeado"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["name"] == "Nubank Renomeado"


def test_delete_credit_card_without_invoices_succeeds(client, auth_headers):
    headers = auth_headers()
    card_id = _create_card(client, headers)

    resp = client.delete(f"/api/v1/credit-cards/{card_id}", headers=headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/v1/credit-cards/{card_id}", headers=headers)
    assert resp.status_code == 404


def test_delete_credit_card_with_invoice_is_conflict(client, auth_headers):
    headers = auth_headers()
    card_id = _create_card(client, headers)

    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Nubank Conta", "type": "checking", "initial_balance": 0.0},
        headers=headers,
    )
    account_id = resp.get_json()["data"]["id"]

    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "type": "expense",
            "description": "Compra no cartão",
            "amount": 100.0,
            "date": "2026-07-05",
        },
        headers=headers,
    )

    resp = client.delete(f"/api/v1/credit-cards/{card_id}", headers=headers)
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "CONFLICT"
