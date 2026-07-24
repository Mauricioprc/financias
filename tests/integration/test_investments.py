def _create_investment(client, headers, invested_amount=1000.0, current_amount=None):
    payload = {
        "name": "Tesouro Selic 2029",
        "type": "fixed_income",
        "invested_amount": invested_amount,
        "acquired_at": "2026-01-10",
    }
    if current_amount is not None:
        payload["current_amount"] = current_amount
    resp = client.post("/api/v1/investments", json=payload, headers=headers)
    return resp


def test_create_defaults_current_amount_to_invested_amount(client, auth_headers):
    headers = auth_headers()

    resp = _create_investment(client, headers, invested_amount=1000.0)
    assert resp.status_code == 201
    investment = resp.get_json()["data"]
    assert investment["invested_amount"] == "1000.00"
    assert investment["current_amount"] == "1000.00"


def test_create_with_explicit_current_amount(client, auth_headers):
    headers = auth_headers()

    resp = _create_investment(client, headers, invested_amount=1000.0, current_amount=1150.0)
    investment = resp.get_json()["data"]
    assert investment["current_amount"] == "1150.00"


def test_list_get_update_delete_investment(client, auth_headers):
    headers = auth_headers()
    investment_id = _create_investment(client, headers).get_json()["data"]["id"]

    resp = client.get("/api/v1/investments", headers=headers)
    assert resp.get_json()["meta"]["total"] == 1

    resp = client.get(f"/api/v1/investments/{investment_id}", headers=headers)
    assert resp.status_code == 200

    resp = client.patch(
        f"/api/v1/investments/{investment_id}", json={"current_amount": 1200.0}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["current_amount"] == "1200.00"

    resp = client.delete(f"/api/v1/investments/{investment_id}", headers=headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/v1/investments/{investment_id}", headers=headers)
    assert resp.status_code == 404


def test_cannot_access_investment_from_another_user(client, auth_headers):
    headers_a = auth_headers(email="a@example.com")
    headers_b = auth_headers(email="b@example.com")
    investment_id = _create_investment(client, headers_a).get_json()["data"]["id"]

    resp = client.get(f"/api/v1/investments/{investment_id}", headers=headers_b)
    assert resp.status_code == 404


def test_invalid_investment_type_rejected(client, auth_headers):
    headers = auth_headers()

    resp = client.post(
        "/api/v1/investments",
        json={
            "name": "Ação X",
            "type": "not_a_real_type",
            "invested_amount": 100.0,
            "acquired_at": "2026-01-10",
        },
        headers=headers,
    )
    assert resp.status_code == 422
