def _create_account(client, headers, initial_balance=100.0):
    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Nubank", "type": "checking", "initial_balance": initial_balance},
        headers=headers,
    )
    return resp.get_json()["data"]["id"]


def test_create_transaction_updates_account_balance(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers, initial_balance=100.0)

    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "type": "income",
            "description": "Salário",
            "amount": 1000.0,
            "date": "2026-07-05",
        },
        headers=headers,
    )
    assert resp.status_code == 201

    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "type": "expense",
            "description": "Mercado",
            "amount": 300.0,
            "date": "2026-07-06",
        },
        headers=headers,
    )
    assert resp.status_code == 201

    resp = client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert resp.get_json()["data"]["current_balance"] == "800.00"


def test_update_transaction_recalculates_balance(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers, initial_balance=0.0)

    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "type": "expense",
            "description": "Mercado",
            "amount": 100.0,
            "date": "2026-07-06",
        },
        headers=headers,
    )
    transaction_id = resp.get_json()["data"]["id"]

    client.patch(
        f"/api/v1/transactions/{transaction_id}", json={"amount": 250.0}, headers=headers
    )

    resp = client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert resp.get_json()["data"]["current_balance"] == "-250.00"


def test_delete_transaction_reverts_balance(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers, initial_balance=500.0)

    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "type": "expense",
            "description": "Mercado",
            "amount": 100.0,
            "date": "2026-07-06",
        },
        headers=headers,
    )
    transaction_id = resp.get_json()["data"]["id"]

    resp = client.delete(f"/api/v1/transactions/{transaction_id}", headers=headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert resp.get_json()["data"]["current_balance"] == "500.00"


def test_cannot_use_account_from_another_user(client, auth_headers):
    headers_a = auth_headers(email="a@example.com")
    headers_b = auth_headers(email="b@example.com")
    account_id = _create_account(client, headers_a)

    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "type": "expense",
            "description": "Mercado",
            "amount": 10.0,
            "date": "2026-07-06",
        },
        headers=headers_b,
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_transaction_amount_must_be_positive(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers)

    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "type": "expense",
            "description": "Mercado",
            "amount": -10.0,
            "date": "2026-07-06",
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_list_transactions_filters_by_type(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers)

    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "type": "income",
            "description": "Salário",
            "amount": 1000.0,
            "date": "2026-07-05",
        },
        headers=headers,
    )
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "type": "expense",
            "description": "Mercado",
            "amount": 100.0,
            "date": "2026-07-06",
        },
        headers=headers,
    )

    resp = client.get("/api/v1/transactions?type=expense", headers=headers)
    body = resp.get_json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["type"] == "expense"
