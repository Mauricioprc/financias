"""Correção de regressão: o menu raiz passou de 10 itens e
send_root_menu chamava send_list (não paginado) direto, o que estoura o
limite de 10 linhas da API do WhatsApp e cai silenciosamente pro fallback
de texto simples. Cobre que send_root_menu agora usa send_list_paginated
(bot/conversation.py)."""

import pytest

from app.extensions import db
from app.models.user import User
from bot import conversation, menus


@pytest.fixture(autouse=True)
def fake_whatsapp(monkeypatch):
    sent = []

    def _record(kind):
        def _fn(to, *args, **kwargs):
            sent.append({"kind": kind, "to": to, "args": args, "kwargs": kwargs})
            return {}

        return _fn

    monkeypatch.setattr(conversation.whatsapp_client, "send_text", _record("text"))
    monkeypatch.setattr(conversation.whatsapp_client, "send_list", _record("list"))
    return sent


def _register_and_link(client, auth_headers, phone="+5511977097728", email="bot@example.com"):
    headers = auth_headers(email=email)
    client.patch("/api/v1/users/me", json={"phone_number": phone}, headers=headers)
    user = db.session.query(User).filter_by(email=email).first()
    return user, headers


def test_root_menu_has_more_than_10_items():
    # Trava a regressão: se alguém reduzir o menu pra <=10 de novo, esse
    # teste falha lembrando que send_root_menu precisa continuar paginando.
    assert len(menus.ROOT_MENU_ITEMS) > 10


def test_send_root_menu_paginates_into_multiple_list_messages(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)

    conversation.send_root_menu(user)

    list_messages = [entry for entry in fake_whatsapp if entry["kind"] == "list"]
    assert len(list_messages) >= 2

    total_rows = 0
    for entry in list_messages:
        sections = entry["args"][2]
        rows = sections[0]["rows"]
        assert len(rows) <= 10
        total_rows += len(rows)

    assert total_rows == len(menus.ROOT_MENU_ITEMS)


def test_root_menu_rows_cover_every_item():
    rows = menus.root_menu_rows()
    assert len(rows) == len(menus.ROOT_MENU_ITEMS)
    assert {r["id"] for r in rows} == {item["id"] for item in menus.ROOT_MENU_ITEMS}
