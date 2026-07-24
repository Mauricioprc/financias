def _create_account(client, headers, initial_balance=0.0):
    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": initial_balance},
        headers=headers,
    )
    return resp.get_json()["data"]["id"]


def _create_recurring(
    client,
    headers,
    account_id,
    type="income",
    amount=1000.0,
    frequency="monthly",
    day_of_month=5,
    start_date="2026-01-05",
    end_date=None,
):
    payload = {
        "account_id": account_id,
        "description": "Salário",
        "type": type,
        "amount": amount,
        "frequency": frequency,
        "day_of_month": day_of_month,
        "start_date": start_date,
    }
    if end_date is not None:
        payload["end_date"] = end_date
    resp = client.post("/api/v1/recurring-transactions", json=payload, headers=headers)
    return resp


def test_create_list_get_update_recurring_transaction(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers)

    resp = _create_recurring(client, headers, account_id)
    assert resp.status_code == 201
    recurring = resp.get_json()["data"]
    recurring_id = recurring["id"]
    assert recurring["last_generated"] is None
    assert recurring["is_active"] is True

    resp = client.get("/api/v1/recurring-transactions", headers=headers)
    assert resp.get_json()["meta"]["total"] == 1

    resp = client.get(f"/api/v1/recurring-transactions/{recurring_id}", headers=headers)
    assert resp.status_code == 200

    resp = client.patch(
        f"/api/v1/recurring-transactions/{recurring_id}",
        json={"amount": 1200.0, "is_active": False},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()["data"]
    assert body["amount"] == "1200.00"
    assert body["is_active"] is False


def test_generate_monthly_creates_expected_occurrences_and_updates_balance(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers, initial_balance=0.0)

    resp = _create_recurring(
        client,
        headers,
        account_id,
        type="income",
        amount=1000.0,
        frequency="monthly",
        day_of_month=5,
        start_date="2026-01-05",
    )
    recurring_id = resp.get_json()["data"]["id"]

    resp = client.post(
        f"/api/v1/recurring-transactions/{recurring_id}/generate?until=2026-03-31",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["meta"]["total"] == 3
    dates = sorted(t["date"] for t in body["data"])
    assert dates == ["2026-01-05", "2026-02-05", "2026-03-05"]

    resp = client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert resp.get_json()["data"]["current_balance"] == "3000.00"

    resp = client.get(f"/api/v1/recurring-transactions/{recurring_id}", headers=headers)
    assert resp.get_json()["data"]["last_generated"] == "2026-03-05"


def test_generate_is_idempotent_for_same_until(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers)

    resp = _create_recurring(client, headers, account_id, start_date="2026-01-05")
    recurring_id = resp.get_json()["data"]["id"]

    client.post(
        f"/api/v1/recurring-transactions/{recurring_id}/generate?until=2026-02-28",
        headers=headers,
    )
    resp = client.post(
        f"/api/v1/recurring-transactions/{recurring_id}/generate?until=2026-02-28",
        headers=headers,
    )
    assert resp.get_json()["meta"]["total"] == 0

    resp = client.get("/api/v1/transactions", headers=headers)
    assert resp.get_json()["meta"]["total"] == 2


def test_generate_respects_end_date(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers)

    resp = _create_recurring(
        client,
        headers,
        account_id,
        start_date="2026-01-05",
        end_date="2026-02-05",
    )
    recurring_id = resp.get_json()["data"]["id"]

    resp = client.post(
        f"/api/v1/recurring-transactions/{recurring_id}/generate?until=2026-06-30",
        headers=headers,
    )
    assert resp.get_json()["meta"]["total"] == 2


def test_generate_weekly_frequency(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers)

    resp = _create_recurring(
        client,
        headers,
        account_id,
        type="expense",
        amount=50.0,
        frequency="weekly",
        day_of_month=None,
        start_date="2026-07-01",
    )
    recurring_id = resp.get_json()["data"]["id"]

    resp = client.post(
        f"/api/v1/recurring-transactions/{recurring_id}/generate?until=2026-07-22",
        headers=headers,
    )
    dates = sorted(t["date"] for t in resp.get_json()["data"])
    assert dates == ["2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22"]


def test_generate_yearly_frequency(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers)

    resp = _create_recurring(
        client,
        headers,
        account_id,
        type="expense",
        amount=200.0,
        frequency="yearly",
        day_of_month=None,
        start_date="2024-07-10",
    )
    recurring_id = resp.get_json()["data"]["id"]

    resp = client.post(
        f"/api/v1/recurring-transactions/{recurring_id}/generate?until=2026-12-31",
        headers=headers,
    )
    dates = sorted(t["date"] for t in resp.get_json()["data"])
    assert dates == ["2024-07-10", "2025-07-10", "2026-07-10"]


def test_cannot_generate_inactive_recurring(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers)

    resp = _create_recurring(client, headers, account_id, start_date="2026-01-05")
    recurring_id = resp.get_json()["data"]["id"]
    client.patch(
        f"/api/v1/recurring-transactions/{recurring_id}", json={"is_active": False}, headers=headers
    )

    resp = client.post(
        f"/api/v1/recurring-transactions/{recurring_id}/generate?until=2026-02-28",
        headers=headers,
    )
    assert resp.status_code == 422


def test_delete_recurring_without_generated_transactions_succeeds(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers)

    resp = _create_recurring(client, headers, account_id, start_date="2026-01-05")
    recurring_id = resp.get_json()["data"]["id"]

    resp = client.delete(f"/api/v1/recurring-transactions/{recurring_id}", headers=headers)
    assert resp.status_code == 204


def test_delete_recurring_with_generated_transactions_is_conflict(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers)

    resp = _create_recurring(client, headers, account_id, start_date="2026-01-05")
    recurring_id = resp.get_json()["data"]["id"]

    client.post(
        f"/api/v1/recurring-transactions/{recurring_id}/generate?until=2026-01-31",
        headers=headers,
    )

    resp = client.delete(f"/api/v1/recurring-transactions/{recurring_id}", headers=headers)
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "CONFLICT"


def test_cannot_use_account_from_another_user(client, auth_headers):
    headers_a = auth_headers(email="a@example.com")
    headers_b = auth_headers(email="b@example.com")
    account_id_a = _create_account(client, headers_a)

    resp = client.post(
        "/api/v1/recurring-transactions",
        json={
            "account_id": account_id_a,
            "description": "Salário",
            "type": "income",
            "amount": 1000.0,
            "frequency": "monthly",
            "day_of_month": 5,
            "start_date": "2026-01-05",
        },
        headers=headers_b,
    )
    assert resp.status_code == 422
