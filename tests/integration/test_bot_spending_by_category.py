"""Fluxo 'Gastos por categoria' — mesmo padrão de
test_bot_goal_contribution.py. Nenhuma soma nova: report_service.category_breakdown
já é usado pelo dashboard web e já cobre conta + cartão juntos.

Passos: período (mês atual/passado/escolher) -> modo (total do mês vs
categoria específica) -> (categoria, se específica)."""

import pytest

from app.extensions import db
from app.models.user import User
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


def _reply_event(wa_id, reply_id, message_id="msg-1"):
    return {
        "message_id": message_id,
        "wa_id": wa_id.lstrip("+"),
        "type": "interactive",
        "text": None,
        "reply_id": reply_id,
    }


def _setup_expenses(client, headers, tx_date=None):
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 1000},
        headers=headers,
    ).get_json()["data"]
    card = client.post(
        "/api/v1/credit-cards",
        json={"name": "Cartão", "credit_limit": 3000, "closing_day": 25, "due_day": 5},
        headers=headers,
    ).get_json()["data"]
    mercado = client.post(
        "/api/v1/categories", json={"name": "Mercado", "type": "expense"}, headers=headers
    ).get_json()["data"]
    lazer = client.post(
        "/api/v1/categories", json={"name": "Lazer", "type": "expense"}, headers=headers
    ).get_json()["data"]

    from datetime import date

    tx_date = tx_date or date.today().isoformat()
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": mercado["id"],
            "type": "expense",
            "description": "compra 1",
            "amount": 100.0,
            "date": tx_date,
        },
        headers=headers,
    )
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "credit_card_id": card["id"],
            "category_id": mercado["id"],
            "type": "expense",
            "description": "compra 2 no cartão",
            "amount": 50.0,
            "date": tx_date,
        },
        headers=headers,
    )
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": lazer["id"],
            "type": "expense",
            "description": "cinema",
            "amount": 30.0,
            "date": tx_date,
        },
        headers=headers,
    )
    return mercado, lazer


def test_current_month_total_includes_account_and_card_expenses_together(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    _setup_expenses(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "16", "m0"))
    conversation._handle_event(_reply_event(phone, "current_month", "m1"))
    conversation._handle_event(_reply_event(phone, "current_month", "m2"))

    text = fake_whatsapp[-1]["args"][0]
    assert "Mercado: R$ 150,00" in text
    assert "Lazer: R$ 30,00" in text


def test_specific_category_filters_to_chosen_category_total(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    mercado, _lazer = _setup_expenses(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "16", "m0"))
    conversation._handle_event(_reply_event(phone, "current_month", "m1"))
    conversation._handle_event(_reply_event(phone, "specific", "m2"))
    conversation._handle_event(_reply_event(phone, str(mercado["id"]), "m3"))

    text = fake_whatsapp[-1]["args"][0]
    assert "Mercado" in text
    assert "150,00" in text
    assert "Lazer" not in text


def test_specific_category_step_has_back_button_first_step_does_not(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    _setup_expenses(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "16", "m0"))

    first_prompt = fake_whatsapp[-1]
    assert first_prompt["kind"] == "buttons"
    assert all(b["id"] != "back" for b in first_prompt["args"][1])

    conversation._handle_event(_reply_event(phone, "current_month", "m1"))
    conversation._handle_event(_reply_event(phone, "specific", "m2"))

    last_prompt = fake_whatsapp[-1]
    assert last_prompt["kind"] == "list"
    rows = last_prompt["args"][2][0]["rows"]
    assert any(row["id"] == "back" for row in rows)


def test_spending_by_category_back_via_reply_id_returns_to_mode_step(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    _setup_expenses(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "16", "m0"))
    conversation._handle_event(_reply_event(phone, "current_month", "m1"))
    conversation._handle_event(_reply_event(phone, "specific", "m2"))

    state = db.session.query(conversation.BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_category"

    conversation._handle_event(_reply_event(phone, "back", "m3"))

    state = db.session.query(conversation.BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_mode"


def test_last_month_choice_resolves_to_previous_month_only(client, auth_headers, fake_whatsapp):
    from datetime import date

    user, headers = _register_and_link(client, auth_headers)
    today = date.today()
    prev_year, prev_month = (today.year, today.month - 1) if today.month > 1 else (
        today.year - 1,
        12,
    )
    prev_month_date = date(prev_year, prev_month, 15).isoformat()

    # Gasto no mês passado — deve aparecer.
    _setup_expenses(client, headers, tx_date=prev_month_date)
    # Gasto no mês atual — não deve aparecer no resultado de "mês passado".
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta 2", "type": "checking", "initial_balance": 1000},
        headers=headers,
    ).get_json()["data"]
    categoria = client.post(
        "/api/v1/categories", json={"name": "Transporte", "type": "expense"}, headers=headers
    ).get_json()["data"]
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": categoria["id"],
            "type": "expense",
            "description": "uber",
            "amount": 20.0,
            "date": today.isoformat(),
        },
        headers=headers,
    )

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "16", "m0"))
    conversation._handle_event(_reply_event(phone, "last_month", "m1"))
    conversation._handle_event(_reply_event(phone, "current_month", "m2"))

    text = fake_whatsapp[-1]["args"][0]
    assert "Mercado: R$ 150,00" in text
    assert "Transporte" not in text
    assert f"{prev_month:02d}/{prev_year:04d}" in text


def test_custom_month_invalid_format_reprompts(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    _setup_expenses(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "16", "m0"))
    conversation._handle_event(_reply_event(phone, "custom_month", "m1"))
    conversation._handle_event(_text_event(phone, "não sei", "m2"))

    state = db.session.query(conversation.BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_custom_period"
    assert "inválido" in fake_whatsapp[-1]["args"][0].lower()


def test_custom_month_valid_format_works_like_normal_flow(client, auth_headers, fake_whatsapp):
    from datetime import date

    user, headers = _register_and_link(client, auth_headers)
    today = date.today()
    _setup_expenses(client, headers, tx_date=today.isoformat())

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "16", "m0"))
    conversation._handle_event(_reply_event(phone, "custom_month", "m1"))
    conversation._handle_event(_text_event(phone, f"{today.month:02d}/{today.year:04d}", "m2"))
    conversation._handle_event(_reply_event(phone, "current_month", "m3"))

    text = fake_whatsapp[-1]["args"][0]
    assert "Mercado: R$ 150,00" in text
    assert "Lazer: R$ 30,00" in text
