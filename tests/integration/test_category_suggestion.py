from app.services import category_suggestion_service


def _category(client, headers, name="Transporte", type="expense"):
    resp = client.post("/api/v1/categories", json={"name": name, "type": type}, headers=headers)
    return resp.get_json()["data"]["id"]


def _account(client, headers):
    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 1000.0},
        headers=headers,
    )
    return resp.get_json()["data"]["id"]


def _spend(client, headers, account_id, category_id, description, amount=10.0, date="2026-07-05"):
    return client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "category_id": category_id,
            "type": "expense",
            "description": description,
            "amount": amount,
            "date": date,
        },
        headers=headers,
    )


def test_two_similar_descriptions_teach_a_pattern_that_a_third_lookup_suggests(client, auth_headers):
    headers = auth_headers()
    account_id = _account(client, headers)
    category_id = _category(client, headers)

    resp = _spend(client, headers, account_id, category_id, "UBER *TRIP 8829")
    assert resp.status_code == 201
    resp = _spend(client, headers, account_id, category_id, "UBER *TRIP 4471")
    assert resp.status_code == 201

    resp = client.get(
        "/api/v1/transactions/suggest-category",
        query_string={"description": "UBER *TRIP 1234"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["category_id"] == category_id


def test_single_occurrence_does_not_suggest(client, auth_headers):
    headers = auth_headers()
    account_id = _account(client, headers)
    category_id = _category(client, headers)

    _spend(client, headers, account_id, category_id, "Netflix assinatura")

    resp = client.get(
        "/api/v1/transactions/suggest-category",
        query_string={"description": "Netflix assinatura"},
        headers=headers,
    )
    assert resp.get_json()["data"]["category_id"] is None


def test_description_without_prior_pattern_returns_null(client, auth_headers):
    headers = auth_headers()

    resp = client.get(
        "/api/v1/transactions/suggest-category",
        query_string={"description": "Nada parecido antes"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["category_id"] is None


def test_pattern_of_another_user_never_leaks_into_suggestion(client, auth_headers):
    headers_owner = auth_headers(email="owner@example.com")
    account_id = _account(client, headers_owner)
    category_id = _category(client, headers_owner)
    _spend(client, headers_owner, account_id, category_id, "Farmácia São João")
    _spend(client, headers_owner, account_id, category_id, "Farmácia São João")

    headers_other = auth_headers(email="other@example.com")
    resp = client.get(
        "/api/v1/transactions/suggest-category",
        query_string={"description": "Farmácia São João"},
        headers=headers_other,
    )
    assert resp.get_json()["data"]["category_id"] is None


def test_update_transaction_category_also_teaches_a_pattern(client, auth_headers):
    headers = auth_headers()
    account_id = _account(client, headers)
    category_id = _category(client, headers)

    resp = _spend(client, headers, account_id, None, "Farmácia Popular", date="2026-07-01")
    transaction_id = resp.get_json()["data"]["id"]
    client.patch(
        f"/api/v1/transactions/{transaction_id}",
        json={"category_id": category_id},
        headers=headers,
    )

    resp = _spend(client, headers, account_id, category_id, "Farmácia Popular", date="2026-07-02")
    assert resp.status_code == 201

    resp = client.get(
        "/api/v1/transactions/suggest-category",
        query_string={"description": "Farmácia Popular"},
        headers=headers,
    )
    assert resp.get_json()["data"]["category_id"] == category_id


def test_normalize_description_strips_digit_sequences_and_case():
    assert category_suggestion_service.normalize_description("  UBER *Trip 8829  ") == "uber *trip"
    assert category_suggestion_service.normalize_description("Uber *Trip 4471") == "uber *trip"
