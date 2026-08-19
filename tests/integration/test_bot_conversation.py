import pytest

from app.extensions import db
from app.models.bot_conversation_state import BotConversationState
from app.models.transaction import Transaction
from app.models.user import User
from bot import conversation


@pytest.fixture(autouse=True)
def fake_whatsapp(monkeypatch):
    """Substitui o cliente HTTP da Meta por um espião — os testes não devem
    bater na rede de verdade, só verificar o que teria sido enviado."""
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
    return {"message_id": message_id, "wa_id": wa_id.lstrip("+"), "type": "text", "text": text, "reply_id": None}


def _reply_event(wa_id, reply_id, message_id="msg-1"):
    return {
        "message_id": message_id,
        "wa_id": wa_id.lstrip("+"),
        "type": "interactive",
        "text": None,
        "reply_id": reply_id,
    }


def test_unlinked_phone_gets_not_linked_message(app, fake_whatsapp):
    conversation._handle_event(_text_event("+5511900000000", "1", message_id="m1"))
    assert len(fake_whatsapp) == 1
    assert "vinculado" in fake_whatsapp[0]["args"][0]


def test_root_selection_starts_new_transaction_flow(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation._handle_event(_text_event(user.phone_number, "1", message_id="m1"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state is not None
    assert state.flow == "new_transaction"
    assert state.step == "awaiting_type"
    assert fake_whatsapp[-1]["kind"] == "buttons"


def test_unrecognized_root_selection_sends_menu(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation._handle_event(_text_event(user.phone_number, "hein?", message_id="m1"))

    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None
    assert fake_whatsapp[-1]["kind"] in ("list", "text")


def test_full_transaction_flow_creates_transaction_and_clears_state(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    acc = client.post(
        "/api/v1/accounts",
        json={"name": "Conta Teste", "type": "checking", "initial_balance": 100},
        headers=headers,
    ).get_json()["data"]
    cat = client.post(
        "/api/v1/categories", json={"name": "Mercado", "type": "expense"}, headers=headers
    ).get_json()["data"]

    phone = user.phone_number
    steps = [
        _text_event(phone, "1", "m0"),
        _reply_event(phone, "expense", "m1"),
        _text_event(phone, "50,00", "m2"),
        _reply_event(phone, str(cat["id"]), "m3"),
        _reply_event(phone, str(acc["id"]), "m4"),
        _text_event(phone, "Compras da semana", "m5"),
        _reply_event(phone, "confirm", "m6"),
    ]
    for event in steps:
        conversation._handle_event(event)

    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None

    tx = db.session.query(Transaction).filter_by(user_id=user.id).first()
    assert tx is not None
    assert tx.type == "expense"
    assert str(tx.amount) == "50.00"
    assert tx.description == "Compras da semana"
    assert tx.category_id == cat["id"]
    assert tx.account_id == acc["id"]

    resp = client.get(f"/api/v1/accounts/{acc['id']}", headers=headers)
    assert resp.get_json()["data"]["current_balance"] == "50.00"

    assert any("Lançado!" in m["args"][0] for m in fake_whatsapp if m["kind"] == "text")


def test_cancelling_confirmation_does_not_create_transaction(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    acc = client.post(
        "/api/v1/accounts",
        json={"name": "Conta Teste", "type": "checking", "initial_balance": 100},
        headers=headers,
    ).get_json()["data"]

    phone = user.phone_number
    steps = [
        _text_event(phone, "1", "m0"),
        _reply_event(phone, "expense", "m1"),
        _text_event(phone, "50", "m2"),
        _reply_event(phone, "none", "m3"),
        _reply_event(phone, str(acc["id"]), "m4"),
        _text_event(phone, "-", "m5"),
        _reply_event(phone, "cancel", "m6"),
    ]
    for event in steps:
        conversation._handle_event(event)

    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None
    assert db.session.query(Transaction).filter_by(user_id=user.id).count() == 0


def test_exit_keyword_aborts_flow_mid_way(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)
    phone = user.phone_number

    conversation._handle_event(_text_event(phone, "1", "m0"))
    conversation._handle_event(_reply_event(phone, "expense", "m1"))
    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is not None

    conversation._handle_event(_text_event(phone, "menu", "m2"))
    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None


def test_duplicate_message_id_is_ignored(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)
    phone = user.phone_number

    conversation._handle_event(_text_event(phone, "1", "dup-1"))
    count_after_first = len(fake_whatsapp)

    conversation._handle_event(_text_event(phone, "1", "dup-1"))
    assert len(fake_whatsapp) == count_after_first


def test_invalid_amount_reprompts_same_step(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)
    phone = user.phone_number

    conversation._handle_event(_text_event(phone, "1", "m0"))
    conversation._handle_event(_reply_event(phone, "expense", "m1"))
    conversation._handle_event(_text_event(phone, "não é número", "m2"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_amount"
