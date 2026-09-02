def _category(client, headers, name="Mercado", type="expense"):
    resp = client.post("/api/v1/categories", json={"name": name, "type": type}, headers=headers)
    return resp.get_json()["data"]["id"]


def _account(client, headers, initial_balance=1000.0):
    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": initial_balance},
        headers=headers,
    )
    return resp.get_json()["data"]["id"]


def test_create_and_list_budget(client, auth_headers):
    headers = auth_headers()
    category_id = _category(client, headers)

    resp = client.post(
        "/api/v1/budgets", json={"category_id": category_id, "monthly_limit": 500.0}, headers=headers
    )
    assert resp.status_code == 201
    budget = resp.get_json()["data"]
    assert budget["category_id"] == category_id
    assert budget["monthly_limit"] == "500.00"

    resp = client.get("/api/v1/budgets", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["meta"]["total"] == 1


def test_duplicate_budget_for_same_category_is_conflict_not_500(client, auth_headers):
    headers = auth_headers()
    category_id = _category(client, headers)

    resp = client.post(
        "/api/v1/budgets", json={"category_id": category_id, "monthly_limit": 500.0}, headers=headers
    )
    assert resp.status_code == 201

    resp = client.post(
        "/api/v1/budgets", json={"category_id": category_id, "monthly_limit": 300.0}, headers=headers
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "CONFLICT"


def test_update_budget(client, auth_headers):
    headers = auth_headers()
    category_id = _category(client, headers)
    resp = client.post(
        "/api/v1/budgets", json={"category_id": category_id, "monthly_limit": 500.0}, headers=headers
    )
    budget_id = resp.get_json()["data"]["id"]

    resp = client.patch(
        f"/api/v1/budgets/{budget_id}", json={"monthly_limit": 700.0}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["monthly_limit"] == "700.00"


def test_delete_budget(client, auth_headers):
    headers = auth_headers()
    category_id = _category(client, headers)
    resp = client.post(
        "/api/v1/budgets", json={"category_id": category_id, "monthly_limit": 500.0}, headers=headers
    )
    budget_id = resp.get_json()["data"]["id"]

    resp = client.delete(f"/api/v1/budgets/{budget_id}", headers=headers)
    assert resp.status_code == 204

    resp = client.get("/api/v1/budgets", headers=headers)
    assert resp.get_json()["meta"]["total"] == 0


def test_budget_progress_matches_manual_sum(client, auth_headers):
    from datetime import date

    headers = auth_headers()
    category_id = _category(client, headers)
    account_id = _account(client, headers)
    client.post(
        "/api/v1/budgets", json={"category_id": category_id, "monthly_limit": 500.0}, headers=headers
    )

    today = date.today().isoformat()
    for amount in (100.0, 50.0, 25.5):
        resp = client.post(
            "/api/v1/transactions",
            json={
                "account_id": account_id,
                "category_id": category_id,
                "type": "expense",
                "description": "gasto",
                "amount": amount,
                "date": today,
            },
            headers=headers,
        )
        assert resp.status_code == 201

    resp = client.get("/api/v1/budgets/progress", headers=headers)
    assert resp.status_code == 200
    items = resp.get_json()["data"]
    assert len(items) == 1
    item = items[0]
    assert item["current_month_total"] == "175.50"
    assert item["monthly_limit"] == "500.00"
    assert item["remaining"] == "324.50"
    assert item["is_over_budget"] is False
    assert item["pct_used"] == "35.10"


def test_budget_progress_over_budget_and_category_without_spending(client, auth_headers):
    from datetime import date

    headers = auth_headers()
    category_over = _category(client, headers, name="Estourada")
    category_untouched = _category(client, headers, name="Intocada")
    account_id = _account(client, headers)

    client.post(
        "/api/v1/budgets",
        json={"category_id": category_over, "monthly_limit": 100.0},
        headers=headers,
    )
    client.post(
        "/api/v1/budgets",
        json={"category_id": category_untouched, "monthly_limit": 200.0},
        headers=headers,
    )

    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "category_id": category_over,
            "type": "expense",
            "description": "estourou",
            "amount": 150.0,
            "date": date.today().isoformat(),
        },
        headers=headers,
    )

    resp = client.get("/api/v1/budgets/progress", headers=headers)
    items = {item["category_id"]: item for item in resp.get_json()["data"]}

    assert items[category_over]["is_over_budget"] is True
    assert items[category_over]["remaining"] == "-50.00"

    assert items[category_untouched]["current_month_total"] == "0.00"
    assert items[category_untouched]["is_over_budget"] is False


def test_budget_of_another_user_is_not_visible_or_accessible(client, auth_headers):
    headers_owner = auth_headers(email="owner@example.com")
    category_id = _category(client, headers_owner)
    resp = client.post(
        "/api/v1/budgets",
        json={"category_id": category_id, "monthly_limit": 500.0},
        headers=headers_owner,
    )
    budget_id = resp.get_json()["data"]["id"]

    headers_other = auth_headers(email="intruder@example.com")
    resp = client.get("/api/v1/budgets", headers=headers_other)
    assert resp.get_json()["meta"]["total"] == 0

    resp = client.patch(
        f"/api/v1/budgets/{budget_id}", json={"monthly_limit": 999.0}, headers=headers_other
    )
    assert resp.status_code == 404

    resp = client.delete(f"/api/v1/budgets/{budget_id}", headers=headers_other)
    assert resp.status_code == 404


def test_create_budget_for_category_of_another_user_is_not_found(client, auth_headers):
    headers_owner = auth_headers(email="owner2@example.com")
    category_id = _category(client, headers_owner)

    headers_other = auth_headers(email="intruder2@example.com")
    resp = client.post(
        "/api/v1/budgets",
        json={"category_id": category_id, "monthly_limit": 500.0},
        headers=headers_other,
    )
    assert resp.status_code == 404
