from datetime import date, datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models.account import Account
from app.services import net_worth_service


def _account(client, headers, name="Conta", initial_balance=0.0):
    resp = client.post(
        "/api/v1/accounts",
        json={"name": name, "type": "checking", "initial_balance": initial_balance},
        headers=headers,
    )
    return resp.get_json()["data"]["id"]


def _category(client, headers, name="Mercado", type="expense"):
    return client.post(
        "/api/v1/categories", json={"name": name, "type": type}, headers=headers
    ).get_json()["data"]["id"]


def _user_id(client, headers):
    return client.get("/api/v1/auth/me", headers=headers).get_json()["data"]["id"]


def test_history_today_matches_sum_of_current_balance_exactly(app, client, auth_headers):
    """Teste de sanidade obrigatório: se a reconstrução estiver errada
    (algum tipo de Transaction/Transfer não contabilizado, ou contabilizado
    a mais), esse teste pega — é o que garante que o resto está certo."""
    headers = auth_headers()
    account_a = _account(client, headers, "Conta A", 1000.0)
    account_b = _account(client, headers, "Conta B", 500.0)
    category_id = _category(client, headers)

    resp = client.post(
        "/api/v1/credit-cards",
        json={"name": "Cartão", "credit_limit": 3000.0, "closing_day": 10, "due_day": 20},
        headers=headers,
    )
    card_id = resp.get_json()["data"]["id"]

    today = date.today().isoformat()

    # Transações comuns, pagas e não pagas (não pagas não devem afetar nada).
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_a,
            "category_id": category_id,
            "type": "expense",
            "description": "Compras",
            "amount": 120.0,
            "date": today,
        },
        headers=headers,
    )
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_a,
            "category_id": category_id,
            "type": "income",
            "description": "Reembolso pendente",
            "amount": 300.0,
            "date": today,
            "is_paid": False,
        },
        headers=headers,
    )
    # Compra no cartão: não afeta current_balance da conta (só a fatura).
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_a,
            "credit_card_id": card_id,
            "type": "expense",
            "description": "Compra no cartão",
            "amount": 80.0,
            "date": today,
        },
        headers=headers,
    )
    # Transferência entre as duas contas.
    client.post(
        "/api/v1/transfers",
        json={"from_account_id": account_a, "to_account_id": account_b, "amount": 200.0, "date": today},
        headers=headers,
    )

    with app.app_context():
        accounts = db.session.query(Account).filter(Account.id.in_([account_a, account_b])).all()
        expected_total = sum((a.current_balance for a in accounts), Decimal("0.00"))

        user_id = client.get("/api/v1/auth/me", headers=headers).get_json()["data"]["id"]
        history = net_worth_service.compute_net_worth_history(user_id, months=1)
        assert len(history) == 1
        assert history[0]["total_accounts_balance"] == expected_total


def test_account_created_mid_period_does_not_appear_before_its_creation(app, client, auth_headers):
    headers = auth_headers()
    old_account = _account(client, headers, "Conta antiga", 1000.0)
    new_account = _account(client, headers, "Conta nova", 500.0)

    with app.app_context():
        user_id = client.get("/api/v1/auth/me", headers=headers).get_json()["data"]["id"]

        from app.utils.datetime_utils import add_months

        # Conta antiga: "criada" bem antes da janela de 3 meses testada
        # abaixo, pra existir em todos os meses do histórico.
        old = db.session.get(Account, old_account)
        old_year, old_month = add_months(date.today().year, date.today().month, -6)
        old.created_at = datetime(old_year, old_month, 1, tzinfo=timezone.utc)

        # Conta nova: "criada" há 1 mês — simula o cenário descrito no
        # pedido, conta cadastrada no meio do período, com saldo inicial
        # representando dinheiro que já existia mas que o sistema não tem
        # como retroagir.
        new = db.session.get(Account, new_account)
        new_year, new_month = add_months(date.today().year, date.today().month, -1)
        new.created_at = datetime(new_year, new_month, 15, tzinfo=timezone.utc)

        db.session.commit()

        history = net_worth_service.compute_net_worth_history(user_id, months=3)

        # Mês mais antigo (2 meses atrás): só a conta antiga existia.
        oldest = history[0]
        assert oldest["total_accounts_balance"] == Decimal("1000.00")

        # Mês corrente: as duas já existem.
        current = history[-1]
        assert current["total_accounts_balance"] == Decimal("1500.00")


def test_transfer_is_zero_sum_and_does_not_change_combined_total(app, client, auth_headers):
    headers = auth_headers()
    account_a = _account(client, headers, "A", 1000.0)
    account_b = _account(client, headers, "B", 0.0)
    today = date.today().isoformat()

    client.post(
        "/api/v1/transfers",
        json={"from_account_id": account_a, "to_account_id": account_b, "amount": 400.0, "date": today},
        headers=headers,
    )

    with app.app_context():
        user_id = client.get("/api/v1/auth/me", headers=headers).get_json()["data"]["id"]
        history = net_worth_service.compute_net_worth_history(user_id, months=1)
        assert history[0]["total_accounts_balance"] == Decimal("1000.00")


def test_net_worth_today_includes_investment_and_excludes_paid_invoice(client, auth_headers):
    headers = auth_headers()
    account_id = _account(client, headers, "Conta", 1000.0)

    client.post(
        "/api/v1/investments",
        json={
            "name": "Tesouro",
            "type": "fixed_income",
            "broker": "XP",
            "invested_amount": 500.0,
            "current_amount": 550.0,
            "acquired_at": "2026-01-01",
        },
        headers=headers,
    )

    resp = client.post(
        "/api/v1/credit-cards",
        json={"name": "Cartão", "credit_limit": 3000.0, "closing_day": 10, "due_day": 20},
        headers=headers,
    )
    card_id = resp.get_json()["data"]["id"]

    today = date.today().isoformat()
    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "type": "expense",
            "description": "compra",
            "amount": 100.0,
            "date": today,
        },
        headers=headers,
    )
    invoice_id = resp.get_json()["data"]["invoice_id"]

    # Fatura paga: não deve entrar em unpaid_invoices_total.
    client.post(f"/api/v1/invoices/{invoice_id}/close", headers=headers)
    client.post(f"/api/v1/invoices/{invoice_id}/pay", json={"account_id": account_id}, headers=headers)

    resp = client.get("/api/v1/net-worth/today", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["investments_total"] == "550.00"
    assert data["unpaid_invoices_total"] == "0.00"
    assert Decimal(data["net_worth"]) == Decimal(data["accounts_total"]) + Decimal("550.00")


def test_net_worth_today_subtracts_unpaid_invoice(client, auth_headers):
    headers = auth_headers()
    account_id = _account(client, headers, "Conta", 1000.0)
    resp = client.post(
        "/api/v1/credit-cards",
        json={"name": "Cartão", "credit_limit": 3000.0, "closing_day": 10, "due_day": 20},
        headers=headers,
    )
    card_id = resp.get_json()["data"]["id"]

    today = date.today().isoformat()
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "credit_card_id": card_id,
            "type": "expense",
            "description": "compra",
            "amount": 250.0,
            "date": today,
        },
        headers=headers,
    )

    resp = client.get("/api/v1/net-worth/today", headers=headers)
    data = resp.get_json()["data"]
    assert data["unpaid_invoices_total"] == "250.00"
    assert Decimal(data["net_worth"]) == Decimal(data["accounts_total"]) - Decimal("250.00")


def test_history_months_out_of_range_is_validation_error(client, auth_headers):
    headers = auth_headers()
    resp = client.get("/api/v1/net-worth/history", query_string={"months": 25}, headers=headers)
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "VALIDATION_ERROR"

    resp = client.get("/api/v1/net-worth/history", query_string={"months": 0}, headers=headers)
    assert resp.status_code == 422
