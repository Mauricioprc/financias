from datetime import date, timedelta


def _create_account(client, headers, initial_balance=0.0):
    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Nubank", "type": "checking", "initial_balance": initial_balance},
        headers=headers,
    )
    return resp.get_json()["data"]["id"]


def _create_category(client, headers, name, type):
    resp = client.post("/api/v1/categories", json={"name": name, "type": type}, headers=headers)
    return resp.get_json()["data"]["id"]


def _create_transaction(client, headers, **overrides):
    payload = {
        "type": "expense",
        "description": "Transação",
        "amount": 100.0,
        "date": date.today().isoformat(),
        "is_paid": True,
    }
    payload.update(overrides)
    resp = client.post("/api/v1/transactions", json=payload, headers=headers)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["data"]


def test_balance_history_ends_at_current_total_balance(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers, initial_balance=500.0)

    resp = client.get("/api/v1/reports/balance-history?days=7", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    points = body["data"]
    assert len(points) == 7
    assert points[-1]["date"] == date.today().isoformat()
    assert points[-1]["balance"] == "500.00"


def test_balance_history_reflects_paid_transactions_in_range(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers, initial_balance=1000.0)
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    _create_transaction(
        client, headers, account_id=account_id, type="expense", amount=200.0, date=yesterday
    )

    resp = client.get("/api/v1/reports/balance-history?days=7", headers=headers)
    points = resp.get_json()["data"]
    assert points[-1]["balance"] == "800.00"
    assert points[-2]["balance"] == "800.00"
    assert points[-3]["balance"] == "1000.00"


def test_balance_history_ignores_unpaid_transactions(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers, initial_balance=1000.0)

    _create_transaction(
        client, headers, account_id=account_id, type="expense", amount=200.0, is_paid=False
    )

    resp = client.get("/api/v1/reports/balance-history?days=3", headers=headers)
    points = resp.get_json()["data"]
    assert all(p["balance"] == "1000.00" for p in points)


def test_category_breakdown_groups_and_sorts_by_total(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers)
    market_id = _create_category(client, headers, "Mercado", "expense")
    transport_id = _create_category(client, headers, "Transporte", "expense")
    month = date.today().strftime("%Y-%m")

    _create_transaction(
        client, headers, account_id=account_id, category_id=market_id, amount=50.0
    )
    _create_transaction(
        client, headers, account_id=account_id, category_id=market_id, amount=30.0
    )
    _create_transaction(
        client, headers, account_id=account_id, category_id=transport_id, amount=200.0
    )
    _create_transaction(client, headers, account_id=account_id, category_id=None, amount=10.0)

    resp = client.get(f"/api/v1/reports/category-breakdown?month={month}", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data[0]["category_name"] == "Transporte"
    assert data[0]["total"] == "200.00"
    assert data[1]["category_name"] == "Mercado"
    assert data[1]["total"] == "80.00"
    assert data[2]["category_name"] == "Sem categoria"
    assert data[2]["total"] == "10.00"


def test_category_breakdown_requires_month(client, auth_headers):
    headers = auth_headers()
    resp = client.get("/api/v1/reports/category-breakdown", headers=headers)
    assert resp.status_code == 422


def test_income_vs_expense_current_month(client, auth_headers):
    headers = auth_headers()
    account_id = _create_account(client, headers)

    _create_transaction(client, headers, account_id=account_id, type="income", amount=1000.0)
    _create_transaction(client, headers, account_id=account_id, type="expense", amount=400.0)

    resp = client.get("/api/v1/reports/income-vs-expense?months=3", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 3
    current = data[-1]
    assert current["month"] == date.today().strftime("%Y-%m")
    assert current["income"] == "1000.00"
    assert current["expense"] == "400.00"
    assert data[0]["income"] == "0.00"
    assert data[0]["expense"] == "0.00"


def test_reports_scoped_to_authenticated_user(client, auth_headers):
    headers_a = auth_headers(email="a@example.com")
    headers_b = auth_headers(email="b@example.com")
    account_id = _create_account(client, headers_a, initial_balance=999.0)
    _create_transaction(client, headers_a, account_id=account_id, amount=50.0)

    resp = client.get("/api/v1/reports/balance-history?days=1", headers=headers_b)
    assert resp.get_json()["data"][0]["balance"] == "0.00"
