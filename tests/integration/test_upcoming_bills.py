from datetime import date, timedelta


def _account(client, headers, initial_balance=1000.0):
    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": initial_balance},
        headers=headers,
    )
    return resp.get_json()["data"]["id"]


def test_invoice_and_recurring_appear_together_ordered_by_date(client, auth_headers):
    headers = auth_headers()
    account_id = _account(client, headers)

    resp = client.post(
        "/api/v1/credit-cards",
        json={"name": "Cartão", "credit_limit": 3000.0, "closing_day": 25, "due_day": 5},
        headers=headers,
    )
    card_id = resp.get_json()["data"]["id"]

    today = date.today()
    due_soon = (today + timedelta(days=5)).isoformat()
    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "type": "expense",
            "description": "compra",
            "amount": 100.0,
            "date": today.isoformat(),
        },
        headers=headers,
    )
    invoice_id = resp.get_json()["data"]["invoice_id"]
    # Força o due_date pra dentro da janela testada (o due_date real
    # calculado a partir de closing_day/due_day pode cair fora de 30 dias).
    from app.extensions import db
    from app.models.invoice import Invoice

    with client.application.app_context():
        invoice = db.session.get(Invoice, invoice_id)
        invoice.due_date = today + timedelta(days=5)
        db.session.commit()

    recurring_day = (today + timedelta(days=2)).day
    resp = client.post(
        "/api/v1/recurring-transactions",
        json={
            "account_id": account_id,
            "description": "Salário",
            "type": "income",
            "amount": 3000.0,
            "frequency": "monthly",
            "day_of_month": recurring_day,
            "start_date": today.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 201

    resp = client.get("/api/v1/upcoming-bills", query_string={"days": 30}, headers=headers)
    assert resp.status_code == 200
    items = resp.get_json()["data"]

    types = [item["type"] for item in items]
    assert "invoice" in types
    assert "recurring" in types

    dates = [item["date"] for item in items]
    assert dates == sorted(dates)


def test_paid_invoice_does_not_appear(client, auth_headers):
    headers = auth_headers()
    account_id = _account(client, headers)
    resp = client.post(
        "/api/v1/credit-cards",
        json={"name": "Cartão", "credit_limit": 3000.0, "closing_day": 25, "due_day": 5},
        headers=headers,
    )
    card_id = resp.get_json()["data"]["id"]

    today = date.today()
    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "type": "expense",
            "description": "compra",
            "amount": 100.0,
            "date": today.isoformat(),
        },
        headers=headers,
    )
    invoice_id = resp.get_json()["data"]["invoice_id"]

    from app.extensions import db
    from app.models.invoice import Invoice

    with client.application.app_context():
        invoice = db.session.get(Invoice, invoice_id)
        invoice.due_date = today + timedelta(days=5)
        db.session.commit()

    client.post(f"/api/v1/invoices/{invoice_id}/close", headers=headers)
    client.post(f"/api/v1/invoices/{invoice_id}/pay", json={"account_id": account_id}, headers=headers)

    resp = client.get("/api/v1/upcoming-bills", query_string={"days": 30}, headers=headers)
    items = resp.get_json()["data"]
    assert all(item["reference_id"] != invoice_id for item in items if item["type"] == "invoice")


def test_inactive_recurring_does_not_appear(client, auth_headers):
    headers = auth_headers()
    account_id = _account(client, headers)
    today = date.today()
    recurring_day = (today + timedelta(days=2)).day

    resp = client.post(
        "/api/v1/recurring-transactions",
        json={
            "account_id": account_id,
            "description": "Aluguel",
            "type": "expense",
            "amount": 1500.0,
            "frequency": "monthly",
            "day_of_month": recurring_day,
            "start_date": today.isoformat(),
        },
        headers=headers,
    )
    recurring_id = resp.get_json()["data"]["id"]
    client.patch(
        f"/api/v1/recurring-transactions/{recurring_id}", json={"is_active": False}, headers=headers
    )

    resp = client.get("/api/v1/upcoming-bills", query_string={"days": 30}, headers=headers)
    items = resp.get_json()["data"]
    assert all(
        not (item["type"] == "recurring" and item["reference_id"] == recurring_id) for item in items
    )


def test_days_over_max_is_validation_error_not_hang(client, auth_headers):
    headers = auth_headers()
    resp = client.get("/api/v1/upcoming-bills", query_string={"days": 91}, headers=headers)
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "VALIDATION_ERROR"
