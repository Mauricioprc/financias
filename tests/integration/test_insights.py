"""Testes de app/services/insights_service.py. "Hoje" é congelado via
monkeypatch (substitui o nome `date` importado no módulo por uma subclasse
cujo `.today()` retorna uma data fixa) pra deixar os cálculos totalmente
determinísticos, independente de quando a suíte é rodada — sem isso,
qualquer teste numérico aqui ficaria refém do relógio real da máquina."""

from datetime import date, datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models.account import Account
from app.models.category import Category
from app.models.credit_card import CreditCard
from app.models.goal import Goal
from app.models.invoice import Invoice
from app.models.recurring_transaction import RecurringTransaction
from app.models.transaction import Transaction
from app.services import insights_service

FROZEN_TODAY = date(2026, 6, 15)  # meio do mês — evita casos de borda por acidente


def _freeze_today(monkeypatch, fixed=FROZEN_TODAY):
    class FrozenDate(date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr(insights_service, "date", FrozenDate)


def _user_id(client, auth_headers, email="insights@example.com"):
    headers = auth_headers(email=email)
    resp = client.get("/api/v1/auth/me", headers=headers)
    return resp.get_json()["data"]["id"], headers


def _account(user_id, current_balance="0.00"):
    account = Account(
        user_id=user_id,
        name="Conta",
        type="checking",
        initial_balance=Decimal(current_balance),
        current_balance=Decimal(current_balance),
    )
    db.session.add(account)
    db.session.commit()
    return account


def _category(user_id, name="Categoria", type="expense"):
    category = Category(user_id=user_id, name=name, type=type)
    db.session.add(category)
    db.session.commit()
    return category


def _expense(user_id, account_id, category_id, amount, d: date):
    tx = Transaction(
        user_id=user_id,
        account_id=account_id,
        category_id=category_id,
        credit_card_id=None,
        recurring_id=None,
        type="expense",
        description="x",
        amount=Decimal(str(amount)),
        date=d,
        is_paid=True,
    )
    db.session.add(tx)
    db.session.commit()
    return tx


def _income_or_expense(user_id, account_id, amount, d: date, type_="expense"):
    tx = Transaction(
        user_id=user_id,
        account_id=account_id,
        category_id=None,
        credit_card_id=None,
        recurring_id=None,
        type=type_,
        description="variável",
        amount=Decimal(str(abs(amount))),
        date=d,
        is_paid=True,
    )
    db.session.add(tx)
    db.session.commit()
    return tx


# ---------- 1. forecast_account_balance ----------


def test_forecast_account_balance_variable_only(app, client, auth_headers, monkeypatch):
    with app.app_context():
        _freeze_today(monkeypatch)
        user_id, _headers = _user_id(client, auth_headers, "forecast1@example.com")
        account = _account(user_id, "1000.00")

        # 3 meses completos anteriores a junho: março, abril, maio.
        _income_or_expense(user_id, account.id, 90, date(2026, 3, 10), "expense")
        _income_or_expense(user_id, account.id, 60, date(2026, 4, 10), "expense")
        _income_or_expense(user_id, account.id, 30, date(2026, 5, 10), "income")

        result = insights_service.forecast_account_balance(user_id, account.id)

        assert result["account_id"] == account.id
        assert result["current_balance"] == Decimal("1000.00")
        assert result["days_remaining"] == 15  # 15 até 30 de junho
        assert result["components"]["recurring_expected"] == Decimal("0.00")
        assert result["components"]["upcoming_invoice_debits"] == Decimal("0.00")

        # -90 -90? não: -90 -60 +30 = -120, em 92 dias (mar+abr+mai), * 15 dias restantes
        total_days = 92
        expected_avg_daily = Decimal("-120.00") / total_days
        expected_variable = (expected_avg_daily * 15).quantize(Decimal("0.01"))
        assert result["components"]["variable_spending_estimate"] == expected_variable

        expected_projected = (Decimal("1000.00") + expected_variable).quantize(Decimal("0.01"))
        assert result["projected_end_of_month_balance"] == expected_projected


def test_forecast_account_balance_with_recurring_and_invoice(app, client, auth_headers, monkeypatch):
    with app.app_context():
        _freeze_today(monkeypatch)
        user_id, _headers = _user_id(client, auth_headers, "forecast2@example.com")
        account = _account(user_id, "500.00")

        # Recorrência mensal dia 20 — só uma ocorrência (20/06) cai na janela
        # amanhã(16/06)..fim do mês(30/06).
        recurring = RecurringTransaction(
            user_id=user_id,
            account_id=account.id,
            category_id=None,
            credit_card_id=None,
            description="Salário",
            type="income",
            amount=Decimal("1000.00"),
            frequency="monthly",
            day_of_month=20,
            start_date=date(2026, 1, 20),
            is_active=True,
        )
        db.session.add(recurring)

        card = CreditCard(
            user_id=user_id,
            account_id=account.id,
            name="Cartão",
            credit_limit=Decimal("5000.00"),
            closing_day=10,
            due_day=25,
        )
        db.session.add(card)
        db.session.flush()

        invoice = Invoice(
            user_id=user_id,
            credit_card_id=card.id,
            reference_month=date(2026, 6, 1),
            closing_date=date(2026, 6, 10),
            due_date=date(2026, 6, 25),  # dentro de [hoje, fim do mês]
            total_amount=Decimal("300.00"),
            paid_amount=Decimal("50.00"),
            status="closed",
        )
        db.session.add(invoice)
        db.session.commit()

        result = insights_service.forecast_account_balance(user_id, account.id)

        assert result["components"]["recurring_expected"] == Decimal("1000.00")
        assert result["components"]["upcoming_invoice_debits"] == Decimal("-250.00")
        assert result["components"]["variable_spending_estimate"] == Decimal("0.00")
        assert result["projected_end_of_month_balance"] == Decimal("1250.00")


def test_forecast_account_balance_last_day_of_month_has_no_projection(
    app, client, auth_headers, monkeypatch
):
    with app.app_context():
        _freeze_today(monkeypatch, fixed=date(2026, 6, 30))
        user_id, _headers = _user_id(client, auth_headers, "forecast3@example.com")
        account = _account(user_id, "777.00")

        result = insights_service.forecast_account_balance(user_id, account.id)

        assert result["days_remaining"] == 0
        assert result["projected_end_of_month_balance"] == Decimal("777.00")
        assert result["components"]["recurring_expected"] == Decimal("0.00")
        assert result["components"]["upcoming_invoice_debits"] == Decimal("0.00")
        assert result["components"]["variable_spending_estimate"] == Decimal("0.00")


# ---------- 2 & 3. compare_category_spending / detect_spending_anomalies ----------


def test_compare_category_spending_and_anomalies(app, client, auth_headers, monkeypatch):
    with app.app_context():
        _freeze_today(monkeypatch)
        user_id, _headers = _user_id(client, auth_headers, "categories@example.com")
        account = _account(user_id, "0.00")

        mercado = _category(user_id, "Mercado")
        transporte = _category(user_id, "Transporte")
        lazer = _category(user_id, "Lazer")

        # Mercado: histórico forte, gasto de junho MUITO acima da média -> "alta"
        _expense(user_id, account.id, mercado.id, 300, date(2026, 6, 10))
        _expense(user_id, account.id, mercado.id, 100, date(2026, 5, 10))
        _expense(user_id, account.id, mercado.id, 80, date(2026, 4, 10))
        _expense(user_id, account.id, mercado.id, 60, date(2026, 3, 10))
        _expense(user_id, account.id, mercado.id, 40, date(2026, 2, 10))

        # Transporte: projeção fica exatamente na faixa "moderada" (1.2x-1.4x)
        _expense(user_id, account.id, transporte.id, 65, date(2026, 6, 5))
        _expense(user_id, account.id, transporte.id, 100, date(2026, 4, 10))
        _expense(user_id, account.id, transporte.id, 100, date(2026, 3, 10))
        _expense(user_id, account.id, transporte.id, 100, date(2026, 2, 10))

        # Lazer: só tem gasto neste mês, sem histórico trailing nenhum —
        # elegível pra comparação, mas não pode virar anomalia (trailing_avg=0).
        _expense(user_id, account.id, lazer.id, 50, date(2026, 6, 12))

        comparison = insights_service.compare_category_spending(user_id)
        by_name = {item["category_name"]: item for item in comparison}

        assert set(by_name) == {"Mercado", "Transporte", "Lazer"}
        # ordenado por current_month_total desc
        assert [item["category_name"] for item in comparison] == ["Mercado", "Transporte", "Lazer"]

        mercado_item = by_name["Mercado"]
        assert mercado_item["current_month_total"] == Decimal("300.00")
        assert mercado_item["same_period_last_month_total"] == Decimal("100.00")
        assert mercado_item["trailing_3_month_avg"] == Decimal("60.00")  # (80+60+40)/3
        assert mercado_item["pct_change_vs_last_month"] == Decimal("200.00")
        assert mercado_item["pct_change_vs_avg"] == Decimal("400.00")

        lazer_item = by_name["Lazer"]
        assert lazer_item["trailing_3_month_avg"] == Decimal("0.00")
        assert lazer_item["pct_change_vs_last_month"] is None  # base 0 -> indefinido
        assert lazer_item["pct_change_vs_avg"] is None

        anomalies = insights_service.detect_spending_anomalies(user_id)
        by_name_anomaly = {item["category_name"]: item for item in anomalies}

        # Lazer não pode aparecer (sem histórico trailing suficiente).
        assert "Lazer" not in by_name_anomaly

        assert by_name_anomaly["Mercado"]["severity"] == "alta"
        assert by_name_anomaly["Transporte"]["severity"] == "moderada"


# ---------- 4. detect_invoice_trend_alerts ----------


def test_invoice_trend_alert_fires_with_three_closed_invoices(
    app, client, auth_headers, monkeypatch
):
    with app.app_context():
        _freeze_today(monkeypatch)
        user_id, _headers = _user_id(client, auth_headers, "invoicetrend@example.com")

        card = CreditCard(
            user_id=user_id,
            name="Cartão com histórico",
            credit_limit=Decimal("5000.00"),
            closing_day=25,
            due_day=5,
            is_archived=False,
        )
        db.session.add(card)
        db.session.flush()

        for i, month in enumerate((3, 4, 5)):
            db.session.add(
                Invoice(
                    user_id=user_id,
                    credit_card_id=card.id,
                    reference_month=date(2026, month, 1),
                    closing_date=date(2026, month, 25),
                    due_date=date(2026, month, 5),
                    total_amount=Decimal("100.00"),
                    paid_amount=Decimal("100.00"),
                    status="paid" if i == 0 else "closed",
                )
            )

        # Fatura aberta do ciclo atual (fecha 25/06, ciclo começou 25/05).
        db.session.add(
            Invoice(
                user_id=user_id,
                credit_card_id=card.id,
                reference_month=date(2026, 6, 1),
                closing_date=date(2026, 6, 25),
                due_date=date(2026, 7, 5),
                total_amount=Decimal("100.00"),
                paid_amount=Decimal("0.00"),
                status="open",
            )
        )
        db.session.commit()

        alerts = insights_service.detect_invoice_trend_alerts(user_id)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["card_id"] == card.id
        assert alert["avg_of_last_3"] == Decimal("100.00")
        # ciclo: 25/05 -> 25/06 = 31 dias; hoje (15/06) = 21 dias decorridos
        expected_projected = (Decimal("100.00") / 21 * 31).quantize(Decimal("0.01"))
        assert alert["projected_total"] == expected_projected
        assert expected_projected > Decimal("130.00")  # > avg * 1.3, senão não devia ter disparado


def test_invoice_trend_alert_skipped_without_three_closed_invoices(
    app, client, auth_headers, monkeypatch
):
    with app.app_context():
        _freeze_today(monkeypatch)
        user_id, _headers = _user_id(client, auth_headers, "invoicetrend2@example.com")

        card = CreditCard(
            user_id=user_id,
            name="Cartão novo",
            credit_limit=Decimal("5000.00"),
            closing_day=25,
            due_day=5,
            is_archived=False,
        )
        db.session.add(card)
        db.session.flush()

        # Só 2 faturas fechadas — não atinge o mínimo de 3.
        for month in (4, 5):
            db.session.add(
                Invoice(
                    user_id=user_id,
                    credit_card_id=card.id,
                    reference_month=date(2026, month, 1),
                    closing_date=date(2026, month, 25),
                    due_date=date(2026, month, 5),
                    total_amount=Decimal("500.00"),
                    paid_amount=Decimal("500.00"),
                    status="paid",
                )
            )
        db.session.add(
            Invoice(
                user_id=user_id,
                credit_card_id=card.id,
                reference_month=date(2026, 6, 1),
                closing_date=date(2026, 6, 25),
                due_date=date(2026, 7, 5),
                total_amount=Decimal("900.00"),
                paid_amount=Decimal("0.00"),
                status="open",
            )
        )
        db.session.commit()

        alerts = insights_service.detect_invoice_trend_alerts(user_id)
        assert alerts == []


# ---------- 5. project_goal_completion ----------


def _create_goal(user_id, current_amount, target_amount, target_date, created_at):
    goal = Goal(
        user_id=user_id,
        name="Meta",
        target_amount=Decimal(str(target_amount)),
        current_amount=Decimal(str(current_amount)),
        target_date=target_date,
        status="in_progress",
    )
    db.session.add(goal)
    db.session.commit()
    # created_at do TimestampMixin usa o relógio real no insert — sobrescreve
    # direto pra controlar months_elapsed de forma determinística no teste.
    goal.created_at = created_at
    db.session.commit()
    return goal


def test_project_goal_completion_no_contribution_yet(app, client, auth_headers, monkeypatch):
    with app.app_context():
        _freeze_today(monkeypatch)
        user_id, _headers = _user_id(client, auth_headers, "goal1@example.com")
        goal = _create_goal(
            user_id,
            current_amount=0,
            target_amount=1000,
            target_date=None,
            created_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        )

        result = insights_service.project_goal_completion(user_id, goal.id)

        assert result["is_rough_estimate"] is True
        assert result["projected_completion_date"] is None
        assert result["reason"] == "sem contribuição detectável ainda"
        assert result["on_track"] is None


def test_project_goal_completion_on_track_when_target_date_is_later(
    app, client, auth_headers, monkeypatch
):
    with app.app_context():
        _freeze_today(monkeypatch)
        user_id, _headers = _user_id(client, auth_headers, "goal2@example.com")
        goal = _create_goal(
            user_id,
            current_amount=1000,
            target_amount=2000,
            target_date=date(2027, 1, 1),  # depois da projeção (15/11/2026)
            created_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        )

        result = insights_service.project_goal_completion(user_id, goal.id)

        # months_elapsed = 5 (jan->jun), avg = 1000/5 = 200/mês
        assert result["avg_monthly_contribution"] == Decimal("200.00")
        # remaining=1000, months_to_complete = ceil(1000/200) = 5 -> 15/11/2026
        assert result["projected_completion_date"] == date(2026, 11, 15)
        assert result["is_rough_estimate"] is True
        assert result["on_track"] is True


def test_project_goal_completion_not_on_track_when_target_date_is_earlier(
    app, client, auth_headers, monkeypatch
):
    with app.app_context():
        _freeze_today(monkeypatch)
        user_id, _headers = _user_id(client, auth_headers, "goal3@example.com")
        goal = _create_goal(
            user_id,
            current_amount=1000,
            target_amount=2000,
            target_date=date(2026, 10, 1),  # antes da projeção (15/11/2026)
            created_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        )

        result = insights_service.project_goal_completion(user_id, goal.id)

        assert result["projected_completion_date"] == date(2026, 11, 15)
        assert result["on_track"] is False


# ---------- Endpoints (smoke) ----------


def test_insights_endpoints_are_wired_and_serializable(app, client, auth_headers, monkeypatch):
    with app.app_context():
        _freeze_today(monkeypatch)
    user_id, headers = _user_id(client, auth_headers, "endpoints@example.com")

    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 100.0},
        headers=headers,
    )
    account_id = resp.get_json()["data"]["id"]

    resp = client.post(
        "/api/v1/goals",
        json={"name": "Meta", "target_amount": 1000.0},
        headers=headers,
    )
    goal_id = resp.get_json()["data"]["id"]

    resp = client.get(f"/api/v1/insights/balance-forecast/{account_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["account_id"] == account_id

    resp = client.get("/api/v1/insights/category-comparison", headers=headers)
    assert resp.status_code == 200

    resp = client.get("/api/v1/insights/spending-anomalies", headers=headers)
    assert resp.status_code == 200

    resp = client.get("/api/v1/insights/invoice-trends", headers=headers)
    assert resp.status_code == 200

    resp = client.get(f"/api/v1/insights/goal-projection/{goal_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["goal_id"] == goal_id
    assert resp.get_json()["data"]["is_rough_estimate"] is True

    resp = client.get("/api/v1/insights/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()["data"]
    assert {"balance_forecasts", "category_comparison", "spending_anomalies", "invoice_trends"} == set(
        body.keys()
    )
    assert len(body["balance_forecasts"]) == 1


def test_balance_forecast_404_for_account_of_another_user(client, auth_headers):
    headers_owner = auth_headers(email="owner@example.com")
    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 100.0},
        headers=headers_owner,
    )
    account_id = resp.get_json()["data"]["id"]

    headers_intruder = auth_headers(email="intruder@example.com")
    resp = client.get(f"/api/v1/insights/balance-forecast/{account_id}", headers=headers_intruder)
    assert resp.status_code == 404


def test_goal_projection_404_for_goal_of_another_user(client, auth_headers):
    headers_owner = auth_headers(email="owner2@example.com")
    resp = client.post(
        "/api/v1/goals",
        json={"name": "Meta", "target_amount": 1000.0},
        headers=headers_owner,
    )
    goal_id = resp.get_json()["data"]["id"]

    headers_intruder = auth_headers(email="intruder2@example.com")
    resp = client.get(f"/api/v1/insights/goal-projection/{goal_id}", headers=headers_intruder)
    assert resp.status_code == 404
