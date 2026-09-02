"""Fluxo 'Categorizar assinatura' — mesmo padrão de
test_bot_goal_contribution.py. Só edita category_id de uma recorrência já
cadastrada, via recurring_transaction_service.update_recurring_transaction
(nenhuma lógica de edição nova)."""

import pytest

from app.extensions import db
from app.models.recurring_transaction import RecurringTransaction
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


def _create_recurring(client, headers, category_id=None):
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 1000},
        headers=headers,
    ).get_json()["data"]
    from datetime import date

    resp = client.post(
        "/api/v1/recurring-transactions",
        json={
            "account_id": account["id"],
            "category_id": category_id,
            "description": "Netflix",
            "type": "expense",
            "amount": 40.0,
            "frequency": "monthly",
            "day_of_month": 10,
            "start_date": date.today().isoformat(),
        },
        headers=headers,
    )
    return resp.get_json()["data"]


def test_recurring_category_with_no_recurring_does_not_start(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation._handle_event(_text_event(user.phone_number, "17", "m0"))

    assert "não tem recorrência cadastrada" in fake_whatsapp[-1]["args"][0]
    from app.models.bot_conversation_state import BotConversationState

    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None


def test_choosing_category_updates_recurring(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    recurring = _create_recurring(client, headers)
    category = client.post(
        "/api/v1/categories", json={"name": "Streaming", "type": "expense"}, headers=headers
    ).get_json()["data"]

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "17", "m0"))
    conversation._handle_event(_reply_event(phone, str(recurring["id"]), "m1"))
    conversation._handle_event(_reply_event(phone, str(category["id"]), "m2"))

    updated = db.session.get(RecurringTransaction, recurring["id"])
    assert updated.category_id == category["id"]
    text = fake_whatsapp[-1]["args"][0]
    assert "Streaming" in text
    assert "Netflix" in text


def test_choosing_no_category_clears_the_field(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    category = client.post(
        "/api/v1/categories", json={"name": "Streaming", "type": "expense"}, headers=headers
    ).get_json()["data"]
    recurring = _create_recurring(client, headers, category_id=category["id"])
    assert recurring["category_id"] == category["id"]

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "17", "m0"))
    conversation._handle_event(_reply_event(phone, str(recurring["id"]), "m1"))
    conversation._handle_event(_reply_event(phone, "none", "m2"))

    updated = db.session.get(RecurringTransaction, recurring["id"])
    assert updated.category_id is None
    text = fake_whatsapp[-1]["args"][0]
    assert "Sem categoria" in text


def test_recurring_category_first_step_has_no_back_second_step_does(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    _create_recurring(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "17", "m0"))

    first_prompt = fake_whatsapp[-1]
    assert first_prompt["kind"] == "list"
    first_rows = first_prompt["args"][2][0]["rows"]
    assert all(row["id"] != "back" for row in first_rows)

    conversation._handle_event(_reply_event(phone, first_rows[0]["id"], "m1"))

    second_prompt = fake_whatsapp[-1]
    assert second_prompt["kind"] == "list"
    second_rows = second_prompt["args"][2][0]["rows"]
    assert any(row["id"] == "back" for row in second_rows)
