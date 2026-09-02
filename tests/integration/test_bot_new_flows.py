"""Testes dos fluxos adicionados na Fase D3: os itens diretos do menu raiz
que faltavam (contas, metas, investimentos, cartões, recorrências) e o
fluxo multi-etapa de transferências."""

import pytest

from app.extensions import db
from app.models.bot_conversation_state import BotConversationState
from app.models.transfer import Transfer
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
    from app.models.user import User

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


# ---------- Fluxos diretos ----------


def test_accounts_flow_lists_accounts_with_balance(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    client.post(
        "/api/v1/accounts",
        json={"name": "Nubank", "type": "checking", "initial_balance": 250},
        headers=headers,
    )

    conversation._handle_event(_text_event(user.phone_number, "4", "m0"))

    assert fake_whatsapp[-1]["kind"] == "text"
    assert "Nubank" in fake_whatsapp[-1]["args"][0]
    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None


def test_accounts_flow_with_no_accounts(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation._handle_event(_text_event(user.phone_number, "4", "m0"))

    assert "nenhuma conta" in fake_whatsapp[-1]["args"][0]


def test_goals_flow_lists_goals_with_progress(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    client.post(
        "/api/v1/goals",
        json={"name": "Reserva de emergência", "target_amount": 1000},
        headers=headers,
    )

    conversation._handle_event(_text_event(user.phone_number, "6", "m0"))

    assert "Reserva de emergência" in fake_whatsapp[-1]["args"][0]
    assert "0%" in fake_whatsapp[-1]["args"][0]


def test_investments_flow_lists_investments_with_gain(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    client.post(
        "/api/v1/investments",
        json={
            "name": "Tesouro Selic",
            "type": "fixed_income",
            "invested_amount": 1000,
            "current_amount": 1050,
            "acquired_at": "2026-01-01",
        },
        headers=headers,
    )

    conversation._handle_event(_text_event(user.phone_number, "7", "m0"))

    assert "Tesouro Selic" in fake_whatsapp[-1]["args"][0]
    assert "Rentabilidade" in fake_whatsapp[-1]["args"][0]


def test_credit_cards_flow_shows_open_invoice(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    card = client.post(
        "/api/v1/credit-cards",
        json={"name": "Nubank", "credit_limit": 5000, "closing_day": 10, "due_day": 20},
        headers=headers,
    ).get_json()["data"]
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 1000},
        headers=headers,
    ).get_json()["data"]
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "credit_card_id": card["id"],
            "type": "expense",
            "description": "Compra",
            "amount": 100,
            "date": "2026-07-05",
        },
        headers=headers,
    )

    conversation._handle_event(_text_event(user.phone_number, "5", "m0"))

    assert "Nubank" in fake_whatsapp[-1]["args"][0]
    assert "Fatura aberta" in fake_whatsapp[-1]["args"][0]


def test_credit_cards_flow_with_no_open_invoice(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    client.post(
        "/api/v1/credit-cards",
        json={"name": "Nubank", "credit_limit": 5000, "closing_day": 10, "due_day": 20},
        headers=headers,
    )

    conversation._handle_event(_text_event(user.phone_number, "5", "m0"))

    assert "Sem fatura aberta" in fake_whatsapp[-1]["args"][0]


def test_recurring_flow_lists_active_recurrences(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 0},
        headers=headers,
    ).get_json()["data"]
    client.post(
        "/api/v1/recurring-transactions",
        json={
            "account_id": account["id"],
            "description": "Netflix",
            "type": "expense",
            "amount": 39.9,
            "frequency": "monthly",
            "day_of_month": 5,
            "start_date": "2026-01-05",
        },
        headers=headers,
    )

    conversation._handle_event(_text_event(user.phone_number, "8", "m0"))

    assert "Netflix" in fake_whatsapp[-1]["args"][0]


def test_recurring_flow_with_no_active_recurrences(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation._handle_event(_text_event(user.phone_number, "8", "m0"))

    assert "nenhuma recorrência ativa" in fake_whatsapp[-1]["args"][0]


# ---------- Fluxo de transferências (multi-etapa) ----------


def test_transfers_flow_requires_two_accounts(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    client.post(
        "/api/v1/accounts",
        json={"name": "Única", "type": "checking", "initial_balance": 100},
        headers=headers,
    )

    conversation._handle_event(_text_event(user.phone_number, "9", "m0"))

    assert "pelo menos duas contas" in fake_whatsapp[-1]["args"][0]
    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None


def test_full_transfer_flow_moves_balance_between_accounts(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    acc_a = client.post(
        "/api/v1/accounts",
        json={"name": "Conta A", "type": "checking", "initial_balance": 200},
        headers=headers,
    ).get_json()["data"]
    acc_b = client.post(
        "/api/v1/accounts",
        json={"name": "Conta B", "type": "savings", "initial_balance": 50},
        headers=headers,
    ).get_json()["data"]

    phone = user.phone_number
    steps = [
        _text_event(phone, "9", "m0"),
        _reply_event(phone, str(acc_a["id"]), "m1"),
        _reply_event(phone, str(acc_b["id"]), "m2"),
        _text_event(phone, "30", "m3"),
        _reply_event(phone, "confirm", "m4"),
    ]
    for event in steps:
        conversation._handle_event(event)

    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None
    transfer = db.session.query(Transfer).filter_by(user_id=user.id).first()
    assert transfer is not None
    assert str(transfer.amount) == "30.00"

    resp_a = client.get(f"/api/v1/accounts/{acc_a['id']}", headers=headers)
    resp_b = client.get(f"/api/v1/accounts/{acc_b['id']}", headers=headers)
    assert resp_a.get_json()["data"]["current_balance"] == "170.00"
    assert resp_b.get_json()["data"]["current_balance"] == "80.00"


def test_transfer_flow_rejects_same_account_as_destination(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    acc_a = client.post(
        "/api/v1/accounts",
        json={"name": "Conta A", "type": "checking", "initial_balance": 200},
        headers=headers,
    ).get_json()["data"]
    client.post(
        "/api/v1/accounts",
        json={"name": "Conta B", "type": "savings", "initial_balance": 50},
        headers=headers,
    )

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "9", "m0"))
    conversation._handle_event(_reply_event(phone, str(acc_a["id"]), "m1"))
    conversation._handle_event(_reply_event(phone, str(acc_a["id"]), "m2"))  # mesma conta

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_to_account"
    assert "diferente" in fake_whatsapp[-1]["args"][0]


def test_transfer_flow_back_returns_to_from_account_step(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    acc_a = client.post(
        "/api/v1/accounts",
        json={"name": "Conta A", "type": "checking", "initial_balance": 200},
        headers=headers,
    ).get_json()["data"]
    client.post(
        "/api/v1/accounts",
        json={"name": "Conta B", "type": "savings", "initial_balance": 50},
        headers=headers,
    )

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "9", "m0"))
    conversation._handle_event(_reply_event(phone, str(acc_a["id"]), "m1"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_to_account"

    conversation._handle_event(_text_event(phone, "voltar", "m2"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_from_account"
    assert "from_account_id" not in state.context_json


def test_transfer_first_step_has_no_back_row_but_second_step_does(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    client.post(
        "/api/v1/accounts",
        json={"name": "Conta A", "type": "checking", "initial_balance": 200},
        headers=headers,
    )
    client.post(
        "/api/v1/accounts",
        json={"name": "Conta B", "type": "savings", "initial_balance": 50},
        headers=headers,
    )

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "9", "m0"))

    first_prompt = fake_whatsapp[-1]
    assert first_prompt["kind"] == "list"
    first_rows = first_prompt["args"][2][0]["rows"]
    assert all(row["id"] != "back" for row in first_rows)

    acc_a_id = first_rows[0]["id"]
    conversation._handle_event(_reply_event(phone, acc_a_id, "m1"))

    second_prompt = fake_whatsapp[-1]
    assert second_prompt["kind"] == "list"
    second_rows = second_prompt["args"][2][0]["rows"]
    assert any(row["id"] == "back" for row in second_rows)


def test_transfer_flow_back_via_reply_id_works_like_typed_keyword(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    client.post(
        "/api/v1/accounts",
        json={"name": "Conta A", "type": "checking", "initial_balance": 200},
        headers=headers,
    )
    client.post(
        "/api/v1/accounts",
        json={"name": "Conta B", "type": "savings", "initial_balance": 50},
        headers=headers,
    )

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "9", "m0"))
    first_rows = fake_whatsapp[-1]["args"][2][0]["rows"]
    conversation._handle_event(_reply_event(phone, first_rows[0]["id"], "m1"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_to_account"

    conversation._handle_event(_reply_event(phone, "back", "m2"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_from_account"
    assert "from_account_id" not in state.context_json
