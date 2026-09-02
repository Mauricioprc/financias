"""Fluxo 'Ver fatura' — só consulta (diferente de invoice_action.py, que é
pra ação de pagar/fechar). Mesmo padrão de test_bot_invoice_action.py.
Reaproveita invoice_service.get_invoice_detail (o mesmo do dashboard web),
nenhum cálculo novo."""

import pytest

from app.extensions import db
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


def _setup_card_account_invoice(client, headers, amount=200.0, category_id=None):
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
            "category_id": category_id,
            "type": "expense",
            "description": "Compra",
            "amount": amount,
            "date": "2026-07-05",
        },
        headers=headers,
    ).get_json()["data"]
    return account, card, tx["invoice_id"]


def test_invoice_view_with_no_cards_does_not_start(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation._handle_event(_text_event(user.phone_number, "18", "m0"))

    assert "não tem nenhum cartão" in fake_whatsapp[-1]["args"][0]


def test_paid_invoice_appears_in_the_list(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    account, _card, invoice_id = _setup_card_account_invoice(client, headers)
    client.post(f"/api/v1/invoices/{invoice_id}/close", headers=headers)
    client.post(
        f"/api/v1/invoices/{invoice_id}/pay", json={"account_id": account["id"]}, headers=headers
    )

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "18", "m0"))
    conversation._handle_event(_reply_event(phone, "1", "m1"))

    invoice_prompt = fake_whatsapp[-1]
    assert invoice_prompt["kind"] == "list"
    rows = invoice_prompt["args"][2][0]["rows"]
    assert any(row["id"] == str(invoice_id) and "paga" in row["title"] for row in rows)


def test_invoice_detail_shows_transactions_with_installment_and_category(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    category = client.post(
        "/api/v1/categories", json={"name": "Mercado", "type": "expense"}, headers=headers
    ).get_json()["data"]
    account, card, invoice_id = _setup_card_account_invoice(
        client, headers, category_id=category["id"]
    )
    # Compra parcelada — a 1ª parcela cai na mesma fatura de julho (fecha
    # dia 10, compra em 05/07); as seguintes vão pras faturas seguintes.
    client.post(
        "/api/v1/transactions/installment-purchases",
        json={
            "account_id": account["id"],
            "credit_card_id": card["id"],
            "description": "Notebook",
            "total_amount": 300.0,
            "installments": 3,
            "date": "2026-07-05",
        },
        headers=headers,
    )

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "18", "m0"))
    conversation._handle_event(_reply_event(phone, "1", "m1"))
    conversation._handle_event(_reply_event(phone, str(invoice_id), "m2"))

    text = fake_whatsapp[-1]["args"][0]
    assert "Nubank" in text
    assert "Status: aberta" in text
    assert "Mercado" in text
    assert "Notebook" in text
    assert "(1/3)" in text


def test_invoice_detail_truncates_when_many_transactions(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    account, card, invoice_id = _setup_card_account_invoice(client, headers, amount=1.0)

    for i in range(25):
        client.post(
            "/api/v1/transactions",
            json={
                "account_id": account["id"],
                "credit_card_id": card["id"],
                "type": "expense",
                "description": f"compra {i}",
                "amount": 1.0,
                "date": "2026-07-05",
            },
            headers=headers,
        )

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "18", "m0"))
    conversation._handle_event(_reply_event(phone, "1", "m1"))
    conversation._handle_event(_reply_event(phone, str(invoice_id), "m2"))

    text = fake_whatsapp[-1]["args"][0]
    assert "e mais" in text
    assert "dashboard" in text


def test_invoice_view_first_step_has_no_back_second_step_does(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    _setup_card_account_invoice(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "18", "m0"))

    first_prompt = fake_whatsapp[-1]
    assert first_prompt["kind"] == "list"
    assert all(row["id"] != "back" for row in first_prompt["args"][2][0]["rows"])

    conversation._handle_event(_reply_event(phone, "1", "m1"))

    second_prompt = fake_whatsapp[-1]
    assert second_prompt["kind"] == "list"
    assert any(row["id"] == "back" for row in second_prompt["args"][2][0]["rows"])
