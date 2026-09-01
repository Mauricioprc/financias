def _setup_card_and_account(client, headers, closing_day=10, due_day=20):
    card_id = client.post(
        "/api/v1/credit-cards",
        json={
            "name": "Nubank",
            "credit_limit": 5000.0,
            "closing_day": closing_day,
            "due_day": due_day,
        },
        headers=headers,
    ).get_json()["data"]["id"]
    account_id = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 1000.0},
        headers=headers,
    ).get_json()["data"]["id"]
    return card_id, account_id


def test_installment_purchase_splits_amount_across_future_invoices(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers)

    resp = client.post(
        "/api/v1/transactions/installment-purchases",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "description": "Notebook",
            "total_amount": 100.0,
            "installments": 3,
            "date": "2026-07-05",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    transactions = resp.get_json()["data"]
    assert len(transactions) == 3

    # Última parcela absorve o resto dos centavos (100 / 3 = 33,33 + 33,33 + 33,34).
    amounts = [t["amount"] for t in transactions]
    assert amounts == ["33.33", "33.33", "33.34"]
    assert sum(float(a) for a in amounts) == 100.0

    for i, t in enumerate(transactions):
        assert t["installment_number"] == i + 1
        assert t["installment_total"] == 3
    assert len({t["purchase_group_id"] for t in transactions}) == 1

    # Cada parcela foi pra fatura de um mês diferente (fecha dia 10 -> compra
    # de 05/07 entra na fatura de referência julho; parcelas seguintes, ago/set).
    invoice_ids = {t["invoice_id"] for t in transactions}
    assert len(invoice_ids) == 3

    invoices = client.get(
        f"/api/v1/invoices?credit_card_id={card_id}", headers=headers
    ).get_json()["data"]
    reference_months = sorted(inv["reference_month"] for inv in invoices)
    assert reference_months == ["2026-07-01", "2026-08-01", "2026-09-01"]

    # Compra no cartão não mexe no saldo da conta.
    account = client.get(f"/api/v1/accounts/{account_id}", headers=headers).get_json()["data"]
    assert account["current_balance"] == "1000.00"


def test_installment_purchase_requires_at_least_two_installments(client, auth_headers):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers)

    resp = client.post(
        "/api/v1/transactions/installment-purchases",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "description": "Notebook",
            "total_amount": 100.0,
            "installments": 1,
            "date": "2026-07-05",
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_installment_purchase_requires_credit_card(client, auth_headers):
    headers = auth_headers()
    _card_id, account_id = _setup_card_and_account(client, headers)

    resp = client.post(
        "/api/v1/transactions/installment-purchases",
        json={
            "account_id": account_id,
            "description": "Notebook",
            "total_amount": 100.0,
            "installments": 3,
            "date": "2026-07-05",
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_installment_purchase_fails_entirely_if_a_future_invoice_is_already_closed(
    client, auth_headers
):
    headers = auth_headers()
    card_id, account_id = _setup_card_and_account(client, headers)

    # Cria e fecha antecipadamente a fatura de agosto (a que a 2ª parcela usaria).
    future_purchase = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "type": "expense",
            "description": "Compra avulsa",
            "amount": 50.0,
            "date": "2026-08-05",
        },
        headers=headers,
    ).get_json()["data"]
    august_invoice_id = future_purchase["invoice_id"]
    client.post(f"/api/v1/invoices/{august_invoice_id}/close", headers=headers)
    august_invoice_before = client.get(
        f"/api/v1/invoices/{august_invoice_id}", headers=headers
    ).get_json()["data"]

    resp = client.post(
        "/api/v1/transactions/installment-purchases",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "description": "Notebook",
            "total_amount": 100.0,
            "installments": 2,  # julho (ok) + agosto (fechada -> falha)
            "date": "2026-07-05",
        },
        headers=headers,
    )
    assert resp.status_code == 409

    # Nada da compra parcelada foi persistido — nem a parcela de julho, que
    # teria sido processada com sucesso antes de travar na de agosto.
    all_transactions = client.get(
        "/api/v1/transactions?per_page=100", headers=headers
    ).get_json()["data"]
    assert len(all_transactions) == 1  # só a "Compra avulsa" original
    assert all_transactions[0]["description"] == "Compra avulsa"

    july_invoices = [
        inv
        for inv in client.get(
            f"/api/v1/invoices?credit_card_id={card_id}", headers=headers
        ).get_json()["data"]
        if inv["reference_month"] == "2026-07-01"
    ]
    assert july_invoices == []  # fatura de julho nem chegou a ser criada de vez

    august_invoice_after = client.get(
        f"/api/v1/invoices/{august_invoice_id}", headers=headers
    ).get_json()["data"]
    assert august_invoice_after["total_amount"] == august_invoice_before["total_amount"]
