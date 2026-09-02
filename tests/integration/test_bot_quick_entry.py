"""Fase A do bot: atalhos que pulam etapas do lançamento de transação —
lançamento rápido em texto livre (bot/quick_entry.py) e comando
'repetir' — sem alterar o fluxo passo-a-passo normal."""

import pytest

from app.extensions import db
from app.models.bot_conversation_state import BotConversationState
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


def _create_account(client, headers, name="Conta", initial_balance=1000):
    return client.post(
        "/api/v1/accounts",
        json={"name": name, "type": "checking", "initial_balance": initial_balance},
        headers=headers,
    ).get_json()["data"]


def _create_category(client, headers, name="Mercado", type="expense"):
    return client.post(
        "/api/v1/categories", json={"name": name, "type": type}, headers=headers
    ).get_json()["data"]


def _teach_pattern(client, headers, account_id, category_id, description, times=2):
    for _ in range(times):
        resp = client.post(
            "/api/v1/transactions",
            json={
                "account_id": account_id,
                "category_id": category_id,
                "type": "expense",
                "description": description,
                "amount": 10,
                "date": "2026-07-01",
            },
            headers=headers,
        )
        assert resp.status_code == 201


# ---------- Lançamento rápido em texto livre ----------


def test_quick_entry_with_learned_category_and_single_account_goes_straight_to_confirmation(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    account = _create_account(client, headers)
    category = _create_category(client, headers, "Mercado")
    _teach_pattern(client, headers, account["id"], category["id"], "mercado")

    conversation._handle_event(_text_event(user.phone_number, "50 mercado", "m0"))

    assert fake_whatsapp[-1]["kind"] == "buttons"
    text = fake_whatsapp[-1]["args"][0]
    assert "Confirma o lançamento" in text
    assert "Mercado" in text
    assert "mercado" in text
    assert "R$ 50,00" in text

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state is not None
    assert state.step == "awaiting_confirmation"
    assert state.context_json["category_id"] == category["id"]
    assert state.context_json["account_id"] == account["id"]


def test_quick_entry_without_learned_category_asks_category_normally(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    _create_account(client, headers)
    _create_category(client, headers, "Mercado")
    # Sem ensinar padrão nenhum — suggest_category não deve achar nada.

    conversation._handle_event(_text_event(user.phone_number, "50 mercado", "m0"))

    assert fake_whatsapp[-1]["kind"] == "list"
    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state is not None
    assert state.step == "awaiting_category"
    # Valor e descrição já resolvidos mesmo perguntando categoria.
    assert state.context_json["amount"] == "50"
    assert state.context_json["description"] == "mercado"


def test_text_without_any_number_falls_back_to_normal_menu(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation._handle_event(_text_event(user.phone_number, "oi", "m0"))

    assert fake_whatsapp[-1]["kind"] == "list"
    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None


# ---------- Comando 'repetir' ----------


def test_repeat_without_any_previous_transaction(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation._handle_event(_text_event(user.phone_number, "repetir", "m0"))

    assert fake_whatsapp[-1]["kind"] == "text"
    assert "ainda não lançou nada" in fake_whatsapp[-1]["args"][0]
    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None


def test_repeat_with_previous_transaction_asks_only_amount_then_confirms(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    account = _create_account(client, headers)
    category = _create_category(client, headers, "Transporte")
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": category["id"],
            "type": "expense",
            "description": "Uber",
            "amount": 20,
            "date": "2026-07-01",
        },
        headers=headers,
    )

    conversation._handle_event(_text_event(user.phone_number, "repetir", "m0"))

    texts = [m["args"][0] for m in fake_whatsapp if m["kind"] == "text"]
    assert any("Repetir como Uber" in t and "Transporte" in t and account["name"] in t for t in texts)
    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state is not None
    assert state.step == "awaiting_amount"
    assert state.context_json["description"] == "Uber"
    assert state.context_json["category_id"] == category["id"]
    assert state.context_json["account_id"] == account["id"]

    conversation._handle_event(_text_event(user.phone_number, "35", "m1"))

    assert fake_whatsapp[-1]["kind"] == "buttons"
    text = fake_whatsapp[-1]["args"][0]
    assert "Uber" in text
    assert "Transporte" in text
    assert "R$ 35,00" in text
    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_confirmation"


# ---------- Regressão: fluxo normal via menu continua idêntico ----------


def test_normal_menu_flow_still_asks_type_first(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation._handle_event(_text_event(user.phone_number, "1", "m0"))

    assert fake_whatsapp[-1]["kind"] == "buttons"
    assert "receita ou despesa" in fake_whatsapp[-1]["args"][0].lower()
    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_type"
    assert state.context_json == {}


def test_normal_menu_flow_with_single_account_still_asks_account(
    client, auth_headers, fake_whatsapp
):
    """Mesmo com 1 conta só, o fluxo normal (via menu) continua perguntando
    a conta — o pulo de conta só existe no atalho de lançamento rápido."""
    user, headers = _register_and_link(client, auth_headers)
    _create_account(client, headers)

    conversation._handle_event(_text_event(user.phone_number, "1", "m0"))
    conversation._handle_event(_text_event(user.phone_number, "despesa", "m1"))
    conversation._handle_event(_text_event(user.phone_number, "50", "m2"))
    conversation._handle_event(_text_event(user.phone_number, "none", "m3"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_account"
