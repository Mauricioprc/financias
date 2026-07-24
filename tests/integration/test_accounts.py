from app.extensions import db
from app.models.transaction import Transaction


def test_create_list_get_update_account(client, auth_headers):
    headers = auth_headers()

    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Nubank", "type": "checking", "initial_balance": 100.0},
        headers=headers,
    )
    assert resp.status_code == 201
    account = resp.get_json()["data"]
    account_id = account["id"]
    assert account["current_balance"] == "100.00"

    resp = client.get("/api/v1/accounts", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["meta"]["total"] == 1

    resp = client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["name"] == "Nubank"

    resp = client.patch(
        f"/api/v1/accounts/{account_id}", json={"name": "Nubank Ultravioleta"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["name"] == "Nubank Ultravioleta"


def test_delete_account_without_transactions_succeeds(client, auth_headers):
    headers = auth_headers()

    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Carteira", "type": "wallet", "initial_balance": 0.0},
        headers=headers,
    )
    account_id = resp.get_json()["data"]["id"]

    resp = client.delete(f"/api/v1/accounts/{account_id}", headers=headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert resp.status_code == 404


def test_delete_account_with_transaction_is_conflict_and_keeps_transaction(
    client, auth_headers, app
):
    headers = auth_headers()

    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Nubank", "type": "checking", "initial_balance": 100.0},
        headers=headers,
    )
    account_id = resp.get_json()["data"]["id"]

    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "type": "expense",
            "description": "Mercado",
            "amount": 50.0,
            "date": "2026-07-10",
        },
        headers=headers,
    )
    transaction_id = resp.get_json()["data"]["id"]

    resp = client.delete(f"/api/v1/accounts/{account_id}", headers=headers)
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "CONFLICT"

    with app.app_context():
        assert db.session.get(Transaction, transaction_id) is not None

    resp = client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert resp.status_code == 200
