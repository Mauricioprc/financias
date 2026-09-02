"""Fase B do bot: expõe insights_service/budget_service/net_worth_service/
upcoming_bills_service via handlers diretos — mesmo padrão de
test_bot_new_flows.py."""

from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.invoice import Invoice
from app.models.user import User
from app.services import invoice_service
from bot import conversation


@pytest.fixture(autouse=True)
def fake_whatsapp(monkeypatch):
    sent = []

    def _record(kind):
        def _fn(to, *args, **kwargs):
            sent.append({"kind": kind, "to": to, "args": args, "kwargs": kwargs})
            return {}

        return _fn

    monkeypatch.setattr(conversation.whatsapp_client, "send_text", _record("text"))
    monkeypatch.setattr(conversation.whatsapp_client, "send_buttons", _record("buttons"))
    monkeypatch.setattr(conversation.whatsapp_client, "send_list", _record("list"))
    return sent


def _register_and_link(client, auth_headers, phone="+5511977097728", email="bot@example.com"):
    headers = auth_headers(email=email)
    client.patch("/api/v1/users/me", json={"phone_number": phone}, headers=headers)
    user = db.session.query(User).filter_by(email=email).first()
    return user, headers


def _text_event(wa_id, text, message_id="msg-1"):
    return {
        "message_id": message_id,
        "wa_id": wa_id.lstrip("+"),
        "type": "text",
        "text": text,
        "reply_id": None,
    }


# ---------- Orçamentos ----------


def test_budget_progress_with_no_budget(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation._handle_event(_text_event(user.phone_number, "10", "m0"))

    assert "não tem orçamento cadastrado" in fake_whatsapp[-1]["args"][0]


def test_budget_progress_shows_category_and_percentage(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 1000},
        headers=headers,
    ).get_json()["data"]
    category = client.post(
        "/api/v1/categories", json={"name": "Mercado", "type": "expense"}, headers=headers
    ).get_json()["data"]
    client.post(
        "/api/v1/budgets",
        json={"category_id": category["id"], "monthly_limit": 100},
        headers=headers,
    )
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": category["id"],
            "type": "expense",
            "description": "Compra",
            "amount": 150,
            "date": date.today().isoformat(),
        },
        headers=headers,
    )

    conversation._handle_event(_text_event(user.phone_number, "10", "m0"))

    text = fake_whatsapp[-1]["args"][0]
    assert "Mercado" in text
    assert "150%" in text
    assert "⚠️" in text  # estourou o orçamento


# ---------- Previsão de saldo ----------


def test_balance_forecast_with_no_account(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation._handle_event(_text_event(user.phone_number, "11", "m0"))

    assert "nenhuma conta" in fake_whatsapp[-1]["args"][0]


def test_balance_forecast_on_last_day_of_month_has_no_arrow(
    app, client, auth_headers, fake_whatsapp, monkeypatch
):
    user, headers = _register_and_link(client, auth_headers)
    client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 1000},
        headers=headers,
    )

    with app.app_context():
        from app.services import insights_service

        class FrozenDate(date):
            @classmethod
            def today(cls):
                return date(2026, 6, 30)  # último dia de junho

        monkeypatch.setattr(insights_service, "date", FrozenDate)

        conversation._handle_event(_text_event(user.phone_number, "11", "m0"))

    text = fake_whatsapp[-1]["args"][0]
    assert "Conta" in text
    assert "→" not in text


def test_balance_forecast_shows_projection_when_days_remain(
    app, client, auth_headers, fake_whatsapp, monkeypatch
):
    user, headers = _register_and_link(client, auth_headers)
    client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 1000},
        headers=headers,
    )

    with app.app_context():
        from app.services import insights_service

        class FrozenDate(date):
            @classmethod
            def today(cls):
                return date(2026, 6, 15)  # meio do mês

        monkeypatch.setattr(insights_service, "date", FrozenDate)

        conversation._handle_event(_text_event(user.phone_number, "11", "m0"))

    text = fake_whatsapp[-1]["args"][0]
    assert "Conta" in text
    assert "→" in text
    assert "previsão de" in text


# ---------- Próximos vencimentos ----------


def test_upcoming_bills_empty(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation._handle_event(_text_event(user.phone_number, "12", "m0"))

    assert "Nenhuma conta prevista" in fake_whatsapp[-1]["args"][0]


def test_upcoming_bills_lists_grouped_by_date(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 1000},
        headers=headers,
    ).get_json()["data"]
    today = date.today().isoformat()
    day_of_month = date.today().day
    client.post(
        "/api/v1/recurring-transactions",
        json={
            "account_id": account["id"],
            "description": "Aluguel",
            "type": "expense",
            "amount": 1200,
            "frequency": "monthly",
            "day_of_month": day_of_month,
            "start_date": today,
        },
        headers=headers,
    )

    conversation._handle_event(_text_event(user.phone_number, "12", "m0"))

    text = fake_whatsapp[-1]["args"][0]
    assert "Aluguel" in text
    assert "📅" in text


# ---------- Patrimônio ----------


def test_net_worth_shows_components(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 1000},
        headers=headers,
    )

    conversation._handle_event(_text_event(user.phone_number, "13", "m0"))

    text = fake_whatsapp[-1]["args"][0]
    assert "Patrimônio líquido" in text
    assert "Contas: R$ 1.000,00" in text
    assert "Investimentos: R$ 0,00" in text
    assert "Faturas em aberto: -R$ 0,00" in text


# ---------- Alertas anexados ao resumo mensal ----------


def test_monthly_summary_without_alerts_is_unchanged(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 1000},
        headers=headers,
    )

    conversation._handle_event(_text_event(user.phone_number, "3", "m0"))

    text = fake_whatsapp[-1]["args"][0]
    assert "Alertas" not in text
    assert text.startswith("Resumo de")


def test_monthly_summary_appends_invoice_trend_alert(app, client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 1000},
        headers=headers,
    ).get_json()["data"]
    card = client.post(
        "/api/v1/credit-cards",
        json={"name": "Cartão X", "credit_limit": 50000, "closing_day": 28, "due_day": 5},
        headers=headers,
    ).get_json()["data"]

    with app.app_context():
        # 3 faturas fechadas com histórico baixo — necessário pro alerta de
        # tendência (detect_invoice_trend_alerts) ter uma média de
        # comparação.
        for i, ref_year_month in enumerate([(2020, 1), (2020, 2), (2020, 3)]):
            db.session.add(
                Invoice(
                    user_id=user.id,
                    credit_card_id=card["id"],
                    reference_month=date(ref_year_month[0], ref_year_month[1], 1),
                    closing_date=date(ref_year_month[0], ref_year_month[1], 28),
                    due_date=date(ref_year_month[0], ref_year_month[1], 28),
                    total_amount=Decimal("100.00"),
                    paid_amount=Decimal("100.00"),
                    status="paid" if i == 0 else "closed",
                )
            )
        db.session.commit()

        # Fatura aberta do ciclo atual, com valor bem acima da média —
        # garante o alerta independente de quantos dias já passaram do
        # ciclo (ver comentário em test_insights.py sobre esse cálculo).
        reference_month, closing_date_, due_date_ = invoice_service.compute_invoice_period(
            date.today(), card["closing_day"], card["due_day"]
        )
        db.session.add(
            Invoice(
                user_id=user.id,
                credit_card_id=card["id"],
                reference_month=reference_month,
                closing_date=closing_date_,
                due_date=due_date_,
                total_amount=Decimal("100000.00"),
                paid_amount=Decimal("0.00"),
                status="open",
            )
        )
        db.session.commit()

    conversation._handle_event(_text_event(user.phone_number, "3", "m0"))

    text = fake_whatsapp[-1]["args"][0]
    assert text.startswith("Resumo de")
    assert "⚠️ Alertas:" in text
    assert "Cartão X" in text
    assert "% acima da média" in text
