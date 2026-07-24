from app.extensions import db
from app.models.transaction import Transaction


def _create_account(client, headers, name="Conta", initial_balance=0.0):
    resp = client.post(
        "/api/v1/accounts",
        json={"name": name, "type": "checking", "initial_balance": initial_balance},
        headers=headers,
    )
    return resp.get_json()["data"]["id"]


def test_transfer_moves_balance_between_accounts(client, auth_headers):
    headers = auth_headers()
    account_a = _create_account(client, headers, "Nubank", 500.0)
    account_b = _create_account(client, headers, "Carteira", 0.0)

    resp = client.post(
        "/api/v1/transfers",
        json={
            "from_account_id": account_a,
            "to_account_id": account_b,
            "amount": 200.0,
            "date": "2026-07-10",
        },
        headers=headers,
    )
    assert resp.status_code == 201

    resp_a = client.get(f"/api/v1/accounts/{account_a}", headers=headers)
    resp_b = client.get(f"/api/v1/accounts/{account_b}", headers=headers)
    assert resp_a.get_json()["data"]["current_balance"] == "300.00"
    assert resp_b.get_json()["data"]["current_balance"] == "200.00"


def test_transfer_does_not_create_transaction(client, auth_headers, app):
    headers = auth_headers()
    account_a = _create_account(client, headers, "Nubank", 500.0)
    account_b = _create_account(client, headers, "Carteira", 0.0)

    client.post(
        "/api/v1/transfers",
        json={
            "from_account_id": account_a,
            "to_account_id": account_b,
            "amount": 200.0,
            "date": "2026-07-10",
        },
        headers=headers,
    )

    with app.app_context():
        assert db.session.query(Transaction).count() == 0


def test_transfer_same_account_is_rejected(client, auth_headers):
    headers = auth_headers()
    account_a = _create_account(client, headers, "Nubank", 500.0)

    resp = client.post(
        "/api/v1/transfers",
        json={
            "from_account_id": account_a,
            "to_account_id": account_a,
            "amount": 50.0,
            "date": "2026-07-10",
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_cannot_transfer_using_account_from_another_user(client, auth_headers):
    headers_a = auth_headers(email="a@example.com")
    headers_b = auth_headers(email="b@example.com")
    account_a = _create_account(client, headers_a, "Conta A", 500.0)
    account_b = _create_account(client, headers_b, "Conta B", 0.0)

    resp = client.post(
        "/api/v1/transfers",
        json={
            "from_account_id": account_a,
            "to_account_id": account_b,
            "amount": 50.0,
            "date": "2026-07-10",
        },
        headers=headers_a,
    )
    assert resp.status_code == 422


def test_delete_transfer_reverts_balances(client, auth_headers):
    headers = auth_headers()
    account_a = _create_account(client, headers, "Nubank", 500.0)
    account_b = _create_account(client, headers, "Carteira", 0.0)

    resp = client.post(
        "/api/v1/transfers",
        json={
            "from_account_id": account_a,
            "to_account_id": account_b,
            "amount": 200.0,
            "date": "2026-07-10",
        },
        headers=headers,
    )
    transfer_id = resp.get_json()["data"]["id"]

    resp = client.delete(f"/api/v1/transfers/{transfer_id}", headers=headers)
    assert resp.status_code == 204

    resp_a = client.get(f"/api/v1/accounts/{account_a}", headers=headers)
    resp_b = client.get(f"/api/v1/accounts/{account_b}", headers=headers)
    assert resp_a.get_json()["data"]["current_balance"] == "500.00"
    assert resp_b.get_json()["data"]["current_balance"] == "0.00"


def test_list_transfers_filters_by_account(client, auth_headers):
    headers = auth_headers()
    account_a = _create_account(client, headers, "Nubank", 500.0)
    account_b = _create_account(client, headers, "Carteira", 0.0)
    account_c = _create_account(client, headers, "Poupança", 0.0)

    client.post(
        "/api/v1/transfers",
        json={
            "from_account_id": account_a,
            "to_account_id": account_b,
            "amount": 100.0,
            "date": "2026-07-10",
        },
        headers=headers,
    )
    client.post(
        "/api/v1/transfers",
        json={
            "from_account_id": account_a,
            "to_account_id": account_c,
            "amount": 50.0,
            "date": "2026-07-11",
        },
        headers=headers,
    )

    resp = client.get(f"/api/v1/transfers?account_id={account_b}", headers=headers)
    body = resp.get_json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["to_account_id"] == account_b
