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


def _create_card(client, headers, closing_day=10, due_day=20):
    resp = client.post(
        "/api/v1/credit-cards",
        json={
            "name": "Nubank",
            "credit_limit": 5000.0,
            "closing_day": closing_day,
            "due_day": due_day,
        },
        headers=headers,
    )
    return resp.get_json()["data"]["id"]


def test_create_subscription_requires_expense_type(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers)
    card_id = _create_card(client, headers)

    resp = client.post(
        "/api/v1/recurring-transactions",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "description": "Netflix",
            "type": "income",
            "amount": 39.9,
            "frequency": "monthly",
            "day_of_month": 5,
            "start_date": "2026-01-05",
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_generate_subscription_charges_invoice_instead_of_account(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers, initial_balance=100.0)
    card_id = _create_card(client, headers, closing_day=10, due_day=20)

    resp = client.post(
        "/api/v1/recurring-transactions",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "description": "Netflix",
            "type": "expense",
            "amount": 39.9,
            "frequency": "monthly",
            "day_of_month": 5,
            "start_date": "2026-07-05",
        },
        headers=headers,
    )
    recurring_id = resp.get_json()["data"]["id"]

    resp = client.post(
        f"/api/v1/recurring-transactions/{recurring_id}/generate?until=2026-09-30",
        headers=headers,
    )
    assert resp.status_code == 200
    transactions = resp.get_json()["data"]
    assert len(transactions) == 3
    for t in transactions:
        assert t["credit_card_id"] == card_id
        assert t["invoice_id"] is not None

    # Saldo da conta não muda — cobrança foi pra fatura, não pra conta.
    account = client.get(f"/api/v1/accounts/{account_id}", headers=headers).get_json()["data"]
    assert account["current_balance"] == "100.00"

    invoices = client.get(
        f"/api/v1/invoices?credit_card_id={card_id}", headers=headers
    ).get_json()["data"]
    reference_months = sorted(inv["reference_month"] for inv in invoices)
    assert reference_months == ["2026-07-01", "2026-08-01", "2026-09-01"]
    for inv in invoices:
        assert inv["total_amount"] == "39.90"


def test_cannot_generate_subscription_into_a_closed_future_invoice(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers, initial_balance=100.0)
    card_id = _create_card(client, headers, closing_day=10, due_day=20)

    # Cria e fecha antecipadamente a fatura de agosto.
    august_purchase = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "type": "expense",
            "description": "Compra avulsa",
            "amount": 10.0,
            "date": "2026-08-05",
        },
        headers=headers,
    ).get_json()["data"]
    client.post(f"/api/v1/invoices/{august_purchase['invoice_id']}/close", headers=headers)

    resp = client.post(
        "/api/v1/recurring-transactions",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "description": "Netflix",
            "type": "expense",
            "amount": 39.9,
            "frequency": "monthly",
            "day_of_month": 5,
            "start_date": "2026-07-05",
        },
        headers=headers,
    )
    recurring_id = resp.get_json()["data"]["id"]

    resp = client.post(
        f"/api/v1/recurring-transactions/{recurring_id}/generate?until=2026-09-30",
        headers=headers,
    )
    assert resp.status_code == 409

    # Nada foi gerado — nem a ocorrência de julho, que teria sido processada
    # com sucesso antes de travar na de agosto (fatura fechada).
    recurring = client.get(
        f"/api/v1/recurring-transactions/{recurring_id}", headers=headers
    ).get_json()["data"]
    assert recurring["last_generated"] is None

    all_transactions = client.get(
        "/api/v1/transactions?per_page=100", headers=headers
    ).get_json()["data"]
    assert len(all_transactions) == 1  # só a "Compra avulsa"


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
