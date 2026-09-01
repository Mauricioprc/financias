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


def test_purchase_exactly_on_closing_day_already_goes_to_next_month(client, auth_headers):
    """O dia do fechamento é o primeiro dia do novo ciclo, não o último do
    que está fechando — uma compra feita nesse dia exato já entra na
    próxima fatura, não na que está fechando."""
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers, closing_day=10)

    resp_day_before = _buy(client, headers, account_id, card_id, 50.0, "2026-07-09")
    resp_on_closing_day = _buy(client, headers, account_id, card_id, 70.0, "2026-07-10")

    inv_before = client.get(
        f"/api/v1/invoices/{resp_day_before.get_json()['data']['invoice_id']}", headers=headers
    ).get_json()["data"]
    inv_on_closing = client.get(
        f"/api/v1/invoices/{resp_on_closing_day.get_json()['data']['invoice_id']}", headers=headers
    ).get_json()["data"]

    assert inv_before["reference_month"] == "2026-07-01"
    assert inv_on_closing["reference_month"] == "2026-08-01"


def test_closing_day_one_sends_every_day_of_the_month_to_next_invoice(client, auth_headers):
    """Fechamento dia 1 é o caso extremo da mesma regra: como não existe
    dia 0, absolutamente nenhuma compra do mês (nem no dia 1) fica na
    fatura de referência daquele mês — todas rolam pro mês seguinte."""
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers, closing_day=1, due_day=10)

    resp_first = _buy(client, headers, account_id, card_id, 50.0, "2026-08-01")
    resp_last = _buy(client, headers, account_id, card_id, 70.0, "2026-08-31")

    inv_first = client.get(
        f"/api/v1/invoices/{resp_first.get_json()['data']['invoice_id']}", headers=headers
    ).get_json()["data"]
    inv_last = client.get(
        f"/api/v1/invoices/{resp_last.get_json()['data']['invoice_id']}", headers=headers
    ).get_json()["data"]

    assert inv_first["reference_month"] == inv_last["reference_month"] == "2026-09-01"
    assert inv_first["due_date"] == inv_last["due_date"] == "2026-09-10"


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
    resp = _buy(client, headers, account_id, card_id, 50.0, "2026-07-08")
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


def test_pending_closure_lists_overdue_open_invoices_only(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers, closing_day=10)

    # Vencida: fatura de referência 2020-01, fechou em 2020-01-10, bem no
    # passado em relação a "hoje".
    resp = _buy(client, headers, account_id, card_id, 100.0, "2020-01-05")
    overdue_invoice_id = resp.get_json()["data"]["invoice_id"]

    # Não vencida: fatura de referência num futuro distante, closing_date
    # ainda não chegou.
    _buy(client, headers, account_id, card_id, 50.0, "2099-01-05")

    resp = client.get("/api/v1/invoices/pending-closure", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["id"] == overdue_invoice_id
    assert body["data"][0]["status"] == "open"


def test_pending_closure_excludes_closed_and_paid_invoices(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers, closing_day=10)

    resp = _buy(client, headers, account_id, card_id, 100.0, "2020-01-05")
    invoice_id = resp.get_json()["data"]["invoice_id"]

    resp = client.get("/api/v1/invoices/pending-closure", headers=headers)
    assert resp.get_json()["meta"]["total"] == 1

    client.post(f"/api/v1/invoices/{invoice_id}/close", headers=headers)
    resp = client.get("/api/v1/invoices/pending-closure", headers=headers)
    assert resp.get_json()["meta"]["total"] == 0

    client.post(
        f"/api/v1/invoices/{invoice_id}/pay", json={"account_id": account_id}, headers=headers
    )
    resp = client.get("/api/v1/invoices/pending-closure", headers=headers)
    assert resp.get_json()["meta"]["total"] == 0


def test_pending_closure_orders_multiple_overdue_invoices_by_closing_date(client, auth_headers):
    headers = auth_headers()
    card_a, account_id = _setup_card_and_account(client, headers, closing_day=10)
    resp = client.post(
        "/api/v1/credit-cards",
        json={"name": "Outro cartão", "credit_limit": 3000.0, "closing_day": 5, "due_day": 15},
        headers=headers,
    )
    card_b = resp.get_json()["data"]["id"]

    resp_a = _buy(client, headers, account_id, card_a, 100.0, "2020-03-05")  # closing 2020-03-10
    resp_b = _buy(client, headers, account_id, card_b, 200.0, "2020-01-03")  # closing 2020-01-05
    resp_c = _buy(client, headers, account_id, card_a, 300.0, "2020-02-05")  # closing 2020-02-10

    invoice_a = resp_a.get_json()["data"]["invoice_id"]
    invoice_b = resp_b.get_json()["data"]["invoice_id"]
    invoice_c = resp_c.get_json()["data"]["invoice_id"]

    resp = client.get("/api/v1/invoices/pending-closure", headers=headers)
    body = resp.get_json()
    assert body["meta"]["total"] == 3
    ids_in_order = [item["id"] for item in body["data"]]
    assert ids_in_order == [invoice_b, invoice_c, invoice_a]


def test_current_invoice_preview_without_transactions(client, auth_headers):
    headers = auth_headers()
    card_id, _account_id = _setup_card_and_account(client, headers, closing_day=10, due_day=20)

    resp = client.get(f"/api/v1/credit-cards/{card_id}/current-invoice", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["persisted"] is False
    assert data["total_amount"] == "0.00"
    assert data["paid_amount"] == "0.00"
    assert data["status"] == "open"
    assert data["credit_card_id"] == card_id
    assert data["id"] is None


def test_current_invoice_preview_with_transaction_returns_real_invoice(client, auth_headers):
    from datetime import date

    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers, closing_day=28, due_day=5)

    today = date.today().isoformat()
    resp = _buy(client, headers, account_id, card_id, 75.0, today)
    invoice_id = resp.get_json()["data"]["invoice_id"]

    resp = client.get(f"/api/v1/credit-cards/{card_id}/current-invoice", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["persisted"] is True
    assert data["id"] == invoice_id
    assert data["total_amount"] == "75.00"
