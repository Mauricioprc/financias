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


def test_create_credit_card_linked_to_account(client, auth_headers):
    headers = auth_headers()
    account_id = client.post(
        "/api/v1/accounts",
        json={"name": "Nubank Conta", "type": "checking", "initial_balance": 0.0},
        headers=headers,
    ).get_json()["data"]["id"]

    resp = client.post(
        "/api/v1/credit-cards",
        json={
            "name": "Nubank",
            "credit_limit": 3000.0,
            "closing_day": 5,
            "due_day": 15,
            "account_id": account_id,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["account_id"] == account_id


def test_create_credit_card_with_another_users_account_is_rejected(client, auth_headers):
    headers_a = auth_headers(email="a@example.com")
    headers_b = auth_headers(email="b@example.com")
    other_account_id = client.post(
        "/api/v1/accounts",
        json={"name": "Conta de B", "type": "checking", "initial_balance": 0.0},
        headers=headers_b,
    ).get_json()["data"]["id"]

    resp = client.post(
        "/api/v1/credit-cards",
        json={
            "name": "Nubank",
            "credit_limit": 3000.0,
            "closing_day": 5,
            "due_day": 15,
            "account_id": other_account_id,
        },
        headers=headers_a,
    )
    assert resp.status_code == 422


def test_update_credit_card_account_link(client, auth_headers):
    headers = auth_headers()
    card_id = _create_card(client, headers)
    account_id = client.post(
        "/api/v1/accounts",
        json={"name": "Nubank Conta", "type": "checking", "initial_balance": 0.0},
        headers=headers,
    ).get_json()["data"]["id"]

    resp = client.patch(
        f"/api/v1/credit-cards/{card_id}", json={"account_id": account_id}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["account_id"] == account_id
