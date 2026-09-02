"""Fase C do bot: fluxo multi-etapa 'Pagar/fechar fatura' — mesmo padrão
de test_bot_new_flows.py (fluxo de transferências)."""

import pytest

from app.extensions import db
from app.models.invoice import Invoice
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


def _setup_card_account_invoice(client, headers, amount=200.0):
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "checking", "initial_balance": 1000},
        headers=headers,
    ).get_json()["data"]
    card = client.post(
        "/api/v1/credit-cards",
        json={"name": "Nubank", "credit_limit": 5000, "closing_day": 10, "due_day": 20},
        headers=headers,
    ).get_json()["data"]
    tx = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "credit_card_id": card["id"],
            "type": "expense",
            "description": "Compra",
            "amount": amount,
            "date": "2026-07-05",
        },
        headers=headers,
    ).get_json()["data"]
    return account, card, tx["invoice_id"]


def test_invoice_action_with_card_without_actionable_invoice(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    client.post(
        "/api/v1/credit-cards",
        json={"name": "Nubank", "credit_limit": 5000, "closing_day": 10, "due_day": 20},
        headers=headers,
    )

    conversation._handle_event(_text_event(user.phone_number, "15", "m0"))
    conversation._handle_event(_reply_event(user.phone_number, "1", "m1"))

    assert "não tem fatura aberta nem fechada" in fake_whatsapp[-1]["args"][0]
    assert (
        db.session.query(conversation.BotConversationState).filter_by(user_id=user.id).first()
        is None
    )


def test_open_invoice_goes_straight_to_close_confirmation(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    _account, _card, invoice_id = _setup_card_account_invoice(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "15", "m0"))
    conversation._handle_event(_reply_event(phone, "1", "m1"))  # único cartão
    conversation._handle_event(_reply_event(phone, str(invoice_id), "m2"))

    state = db.session.query(conversation.BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_close_confirmation"
    assert fake_whatsapp[-1]["kind"] == "buttons"
    assert "Fechar a fatura" in fake_whatsapp[-1]["args"][0]


def test_close_invoice_confirmed(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    _account, _card, invoice_id = _setup_card_account_invoice(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "15", "m0"))
    conversation._handle_event(_reply_event(phone, "1", "m1"))
    conversation._handle_event(_reply_event(phone, str(invoice_id), "m2"))
    conversation._handle_event(_reply_event(phone, "confirm", "m3"))

    assert (
        db.session.query(conversation.BotConversationState).filter_by(user_id=user.id).first()
        is None
    )
    invoice = db.session.get(Invoice, invoice_id)
    assert invoice.status == "closed"
    assert "fechada" in fake_whatsapp[-1]["args"][0].lower()


def test_close_invoice_cancel_does_not_close(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    _account, _card, invoice_id = _setup_card_account_invoice(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "15", "m0"))
    conversation._handle_event(_reply_event(phone, "1", "m1"))
    conversation._handle_event(_reply_event(phone, str(invoice_id), "m2"))
    conversation._handle_event(_reply_event(phone, "cancel", "m3"))

    invoice = db.session.get(Invoice, invoice_id)
    assert invoice.status == "open"
    assert "cancelado" in fake_whatsapp[-1]["args"][0].lower()


def test_closed_invoice_asks_pay_full_or_partial(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    _account, _card, invoice_id = _setup_card_account_invoice(client, headers)
    client.post(f"/api/v1/invoices/{invoice_id}/close", headers=headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "15", "m0"))
    conversation._handle_event(_reply_event(phone, "1", "m1"))
    conversation._handle_event(_reply_event(phone, str(invoice_id), "m2"))

    state = db.session.query(conversation.BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_payment_type"
    assert fake_whatsapp[-1]["kind"] == "buttons"


def test_partial_payment_over_remaining_reprompts(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    _account, _card, invoice_id = _setup_card_account_invoice(client, headers, amount=200.0)
    client.post(f"/api/v1/invoices/{invoice_id}/close", headers=headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "15", "m0"))
    conversation._handle_event(_reply_event(phone, "1", "m1"))
    conversation._handle_event(_reply_event(phone, str(invoice_id), "m2"))
    conversation._handle_event(_reply_event(phone, "partial", "m3"))
    conversation._handle_event(_text_event(phone, "500", "m4"))  # > saldo devedor (200)

    state = db.session.query(conversation.BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_payment_amount"
    assert "maior que o saldo devedor" in fake_whatsapp[-1]["args"][0]


def test_full_payment_flow_pays_invoice_and_debits_account(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    account, _card, invoice_id = _setup_card_account_invoice(client, headers, amount=200.0)
    client.post(f"/api/v1/invoices/{invoice_id}/close", headers=headers)

    phone = user.phone_number
    steps = [
        _text_event(phone, "15", "m0"),
        _reply_event(phone, "1", "m1"),
        _reply_event(phone, str(invoice_id), "m2"),
        _reply_event(phone, "full", "m3"),
        _reply_event(phone, str(account["id"]), "m4"),
        _reply_event(phone, "confirm", "m5"),
    ]
    for event in steps:
        conversation._handle_event(event)

    assert (
        db.session.query(conversation.BotConversationState).filter_by(user_id=user.id).first()
        is None
    )
    invoice = db.session.get(Invoice, invoice_id)
    assert invoice.status == "paid"

    resp = client.get(f"/api/v1/accounts/{account['id']}", headers=headers)
    assert resp.get_json()["data"]["current_balance"] == "800.00"  # 1000 - 200


def test_partial_payment_flow_registers_partial_payment(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    account, _card, invoice_id = _setup_card_account_invoice(client, headers, amount=200.0)
    client.post(f"/api/v1/invoices/{invoice_id}/close", headers=headers)

    phone = user.phone_number
    steps = [
        _text_event(phone, "15", "m0"),
        _reply_event(phone, "1", "m1"),
        _reply_event(phone, str(invoice_id), "m2"),
        _reply_event(phone, "partial", "m3"),
        _text_event(phone, "50", "m4"),
        _reply_event(phone, str(account["id"]), "m5"),
        _reply_event(phone, "confirm", "m6"),
    ]
    for event in steps:
        conversation._handle_event(event)

    invoice = db.session.get(Invoice, invoice_id)
    assert str(invoice.paid_amount) == "50.00"
    assert invoice.status == "closed"  # ainda não pagou tudo

    resp = client.get(f"/api/v1/accounts/{account['id']}", headers=headers)
    assert resp.get_json()["data"]["current_balance"] == "950.00"  # 1000 - 50


def test_payment_confirmation_cancel_does_not_pay(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    account, _card, invoice_id = _setup_card_account_invoice(client, headers, amount=200.0)
    client.post(f"/api/v1/invoices/{invoice_id}/close", headers=headers)

    phone = user.phone_number
    steps = [
        _text_event(phone, "15", "m0"),
        _reply_event(phone, "1", "m1"),
        _reply_event(phone, str(invoice_id), "m2"),
        _reply_event(phone, "full", "m3"),
        _reply_event(phone, str(account["id"]), "m4"),
        _reply_event(phone, "cancel", "m5"),
    ]
    for event in steps:
        conversation._handle_event(event)

    invoice = db.session.get(Invoice, invoice_id)
    assert invoice.status == "closed"
    assert str(invoice.paid_amount) == "0.00"
    assert "cancelado" in fake_whatsapp[-1]["args"][0].lower()
