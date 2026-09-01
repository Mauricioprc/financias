def _setup_card_and_account(client, headers, closing_day=10, due_day=20, initial_balance=1000.0):
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
    card_id = resp.get_json()["data"]["id"]

    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": initial_balance},
        headers=headers,
    )
    account_id = resp.get_json()["data"]["id"]
    return card_id, account_id


def _buy(client, headers, account_id, card_id, amount, date):
    return client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "type": "expense",
            "description": "Compra",
            "amount": amount,
            "date": date,
        },
        headers=headers,
    )


def test_card_purchase_creates_invoice_and_does_not_affect_account_balance(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers)

    resp = _buy(client, headers, account_id, card_id, 100.0, "2026-07-05")
    assert resp.status_code == 201
    transaction = resp.get_json()["data"]
    assert transaction["invoice_id"] is not None

    resp = client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert resp.get_json()["data"]["current_balance"] == "1000.00"

    resp = client.get(f"/api/v1/invoices/{transaction['invoice_id']}", headers=headers)
    assert resp.status_code == 200
    invoice = resp.get_json()["data"]
    assert invoice["total_amount"] == "100.00"
    assert invoice["status"] == "open"
    assert invoice["reference_month"] == "2026-07-01"


def test_purchase_after_closing_day_goes_to_next_month_invoice(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers, closing_day=10)

    resp_before = _buy(client, headers, account_id, card_id, 50.0, "2026-07-08")
    resp_after = _buy(client, headers, account_id, card_id, 70.0, "2026-07-15")

    invoice_id_before = resp_before.get_json()["data"]["invoice_id"]
    invoice_id_after = resp_after.get_json()["data"]["invoice_id"]
    assert invoice_id_before != invoice_id_after

    inv_before = client.get(f"/api/v1/invoices/{invoice_id_before}", headers=headers).get_json()[
        "data"
    ]
    inv_after = client.get(f"/api/v1/invoices/{invoice_id_after}", headers=headers).get_json()[
        "data"
    ]
    assert inv_before["reference_month"] == "2026-07-01"
    assert inv_after["reference_month"] == "2026-08-01"


def test_income_type_not_allowed_on_credit_card(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers)

    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "type": "income",
            "description": "Estorno",
            "amount": 10.0,
            "date": "2026-07-05",
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_update_card_transaction_amount_updates_invoice_total(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers)

    resp = _buy(client, headers, account_id, card_id, 100.0, "2026-07-05")
    transaction_id = resp.get_json()["data"]["id"]
    invoice_id = resp.get_json()["data"]["invoice_id"]

    client.patch(
        f"/api/v1/transactions/{transaction_id}", json={"amount": 150.0}, headers=headers
    )

    invoice = client.get(f"/api/v1/invoices/{invoice_id}", headers=headers).get_json()["data"]
    assert invoice["total_amount"] == "150.00"


def test_cannot_change_account_id_or_date_on_card_transaction(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers)

    resp = _buy(client, headers, account_id, card_id, 100.0, "2026-07-05")
    transaction_id = resp.get_json()["data"]["id"]

    resp = client.patch(
        f"/api/v1/transactions/{transaction_id}", json={"date": "2026-07-20"}, headers=headers
    )
    assert resp.status_code == 422


def test_delete_card_transaction_removes_amount_from_invoice(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers)

    resp = _buy(client, headers, account_id, card_id, 100.0, "2026-07-05")
    transaction_id = resp.get_json()["data"]["id"]
    invoice_id = resp.get_json()["data"]["invoice_id"]

    resp = client.delete(f"/api/v1/transactions/{transaction_id}", headers=headers)
    assert resp.status_code == 204

    invoice = client.get(f"/api/v1/invoices/{invoice_id}", headers=headers).get_json()["data"]
    assert invoice["total_amount"] == "0.00"


def test_close_and_pay_invoice_flow(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers, initial_balance=1000.0)

    resp = _buy(client, headers, account_id, card_id, 300.0, "2026-07-05")
    invoice_id = resp.get_json()["data"]["invoice_id"]

    # não pode pagar fatura aberta
    resp = client.post(
        f"/api/v1/invoices/{invoice_id}/pay", json={"account_id": account_id}, headers=headers
    )
    assert resp.status_code == 409

    # não pode adicionar compra em fatura fechada
    resp = client.post(f"/api/v1/invoices/{invoice_id}/close", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "closed"

    resp = _buy(client, headers, account_id, card_id, 10.0, "2026-07-08")
    assert resp.status_code == 409

    # paga a fatura fechada
    resp = client.post(
        f"/api/v1/invoices/{invoice_id}/pay", json={"account_id": account_id}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "paid"

    resp = client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert resp.get_json()["data"]["current_balance"] == "700.00"

    # não pode pagar de novo
    resp = client.post(
        f"/api/v1/invoices/{invoice_id}/pay", json={"account_id": account_id}, headers=headers
    )
    assert resp.status_code == 409


def test_partial_payment_on_open_invoice_reduces_balance_and_stays_open(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers, initial_balance=1000.0)

    resp = _buy(client, headers, account_id, card_id, 300.0, "2026-07-05")
    invoice_id = resp.get_json()["data"]["invoice_id"]

    resp = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"account_id": account_id, "amount": 100.0},
        headers=headers,
    )
    assert resp.status_code == 200
    invoice = resp.get_json()["data"]
    assert invoice["status"] == "open"  # continua aceitando novas compras
    assert invoice["total_amount"] == "300.00"
    assert invoice["paid_amount"] == "100.00"

    account = client.get(f"/api/v1/accounts/{account_id}", headers=headers).get_json()["data"]
    assert account["current_balance"] == "900.00"

    history = client.get("/api/v1/transactions?per_page=100", headers=headers).get_json()["data"]
    payment_tx = [t for t in history if "Pagamento" in t["description"]]
    assert len(payment_tx) == 1
    assert payment_tx[0]["amount"] == "100.00"

    # Uma nova compra ainda pode entrar na fatura (ela continua "open").
    resp = _buy(client, headers, account_id, card_id, 50.0, "2026-07-10")
    assert resp.status_code == 201
    invoice = client.get(f"/api/v1/invoices/{invoice_id}", headers=headers).get_json()["data"]
    assert invoice["total_amount"] == "350.00"


def test_partial_payment_cannot_exceed_remaining_balance(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers)
    resp = _buy(client, headers, account_id, card_id, 100.0, "2026-07-05")
    invoice_id = resp.get_json()["data"]["invoice_id"]

    resp = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"account_id": account_id, "amount": 150.0},
        headers=headers,
    )
    assert resp.status_code == 422


def test_invoice_closed_after_being_fully_prepaid_becomes_paid(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers)
    resp = _buy(client, headers, account_id, card_id, 100.0, "2026-07-05")
    invoice_id = resp.get_json()["data"]["invoice_id"]

    # Paga o total ainda com a fatura aberta.
    resp = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"account_id": account_id, "amount": 100.0},
        headers=headers,
    )
    assert resp.get_json()["data"]["status"] == "open"  # não vira "paid" sozinha ainda aberta

    resp = client.post(f"/api/v1/invoices/{invoice_id}/close", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "paid"  # já cobria o total -> fecha direto paga


def test_pay_invoice_after_partial_payment_only_charges_remaining(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers, initial_balance=1000.0)
    resp = _buy(client, headers, account_id, card_id, 300.0, "2026-07-05")
    invoice_id = resp.get_json()["data"]["invoice_id"]

    client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"account_id": account_id, "amount": 100.0},
        headers=headers,
    )
    client.post(f"/api/v1/invoices/{invoice_id}/close", headers=headers)

    resp = client.post(
        f"/api/v1/invoices/{invoice_id}/pay", json={"account_id": account_id}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "paid"
    assert resp.get_json()["data"]["paid_amount"] == "300.00"

    # Só os 200 restantes foram debitados agora (100 já tinham saído antes).
    account = client.get(f"/api/v1/accounts/{account_id}", headers=headers).get_json()["data"]
    assert account["current_balance"] == "700.00"


def test_cannot_register_payment_on_already_paid_invoice(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers)
    resp = _buy(client, headers, account_id, card_id, 100.0, "2026-07-05")
    invoice_id = resp.get_json()["data"]["invoice_id"]

    client.post(f"/api/v1/invoices/{invoice_id}/close", headers=headers)
    client.post(
        f"/api/v1/invoices/{invoice_id}/pay", json={"account_id": account_id}, headers=headers
    )

    resp = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"account_id": account_id, "amount": 1.0},
        headers=headers,
    )
    assert resp.status_code == 409


def test_cannot_use_credit_card_from_another_user(client, auth_headers):
    headers_a = auth_headers(email="a@example.com")
    headers_b = auth_headers(email="b@example.com")
    card_id, _ = _setup_card_and_account(client, headers_a)

    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Conta B", "type": "checking", "initial_balance": 0.0},
        headers=headers_b,
    )
    account_id_b = resp.get_json()["data"]["id"]

    resp = _buy(client, headers_b, account_id_b, card_id, 50.0, "2026-07-05")
    assert resp.status_code == 422
