"""Fase C do bot: fluxo multi-etapa 'Contribuir pra meta' — mesmo padrão
de test_bot_new_flows.py (fluxo de transferências)."""

import pytest

from app.extensions import db
from app.models.bot_conversation_state import BotConversationState
from app.models.goal import Goal
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


def test_goal_contribution_with_no_goal_in_progress(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation._handle_event(_text_event(user.phone_number, "14", "m0"))

    assert "não tem nenhuma meta em andamento" in fake_whatsapp[-1]["args"][0]
    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None


def test_full_goal_contribution_flow_updates_current_amount(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    goal = client.post(
        "/api/v1/goals", json={"name": "Viagem", "target_amount": 1000}, headers=headers
    ).get_json()["data"]

    phone = user.phone_number
    steps = [
        _text_event(phone, "14", "m0"),
        _reply_event(phone, str(goal["id"]), "m1"),
        _text_event(phone, "100", "m2"),
        _reply_event(phone, "confirm", "m3"),
    ]
    for event in steps:
        conversation._handle_event(event)

    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None

    updated = db.session.get(Goal, goal["id"])
    assert str(updated.current_amount) == "100.00"
    assert updated.status == "in_progress"

    text = fake_whatsapp[-1]["args"][0]
    assert "Contribuição registrada" in text
    assert "100,00" in text
    assert "10%" in text
    assert "🎉" not in text


def test_goal_contribution_reaching_target_shows_achieved_message(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    goal = client.post(
        "/api/v1/goals", json={"name": "Reserva", "target_amount": 100}, headers=headers
    ).get_json()["data"]

    phone = user.phone_number
    steps = [
        _text_event(phone, "14", "m0"),
        _reply_event(phone, str(goal["id"]), "m1"),
        _text_event(phone, "100", "m2"),
        _reply_event(phone, "confirm", "m3"),
    ]
    for event in steps:
        conversation._handle_event(event)

    updated = db.session.get(Goal, goal["id"])
    assert updated.status == "achieved"

    text = fake_whatsapp[-1]["args"][0]
    assert "🎉 Meta atingida!" in text


def test_goal_contribution_cancel_does_not_change_goal(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    goal = client.post(
        "/api/v1/goals", json={"name": "Viagem", "target_amount": 1000}, headers=headers
    ).get_json()["data"]

    phone = user.phone_number
    steps = [
        _text_event(phone, "14", "m0"),
        _reply_event(phone, str(goal["id"]), "m1"),
        _text_event(phone, "100", "m2"),
        _reply_event(phone, "cancel", "m3"),
    ]
    for event in steps:
        conversation._handle_event(event)

    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None
    updated = db.session.get(Goal, goal["id"])
    assert str(updated.current_amount) == "0.00"
    assert "cancelada" in fake_whatsapp[-1]["args"][0].lower()


def test_goal_contribution_invalid_amount_reprompts(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    goal = client.post(
        "/api/v1/goals", json={"name": "Viagem", "target_amount": 1000}, headers=headers
    ).get_json()["data"]

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "14", "m0"))
    conversation._handle_event(_reply_event(phone, str(goal["id"]), "m1"))
    conversation._handle_event(_text_event(phone, "abacate", "m2"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_amount"
    assert "inválido" in fake_whatsapp[-1]["args"][0].lower()
