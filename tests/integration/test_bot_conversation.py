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


def test_confirmation_failure_keeps_state_and_does_not_duplicate(
    client, auth_headers, fake_whatsapp, monkeypatch
):
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
    ]
    for event in steps:
        conversation._handle_event(event)

    from app.services import transaction_service
    from app.services.exceptions import ServiceError

    def _boom(**kwargs):
        raise ServiceError("falhou")

    monkeypatch.setattr(transaction_service, "create_transaction", _boom)

    conversation._handle_event(_reply_event(phone, "confirm", "m6"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state is not None
    assert state.step == "awaiting_confirmation"
    assert db.session.query(Transaction).filter_by(user_id=user.id).count() == 0
    assert "tentar de novo" in fake_whatsapp[-1]["args"][0]


def test_confirmation_message_failure_still_clears_state_and_keeps_transaction(
    client, auth_headers, fake_whatsapp, monkeypatch
):
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
    ]
    for event in steps:
        conversation._handle_event(event)

    from bot.whatsapp_client import WhatsAppApiError

    def _boom(*args, **kwargs):
        raise WhatsAppApiError("falhou")

    monkeypatch.setattr(conversation.whatsapp_client, "send_text", _boom)

    conversation._handle_event(_reply_event(phone, "confirm", "m6"))

    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None
    assert db.session.query(Transaction).filter_by(user_id=user.id).count() == 1


def test_back_at_first_step_says_so_and_stays(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)
    phone = user.phone_number

    conversation._handle_event(_text_event(phone, "1", "m0"))
    conversation._handle_event(_text_event(phone, "voltar", "m1"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_type"
    assert any(
        m["kind"] == "text" and "primeiro passo" in m["args"][0] for m in fake_whatsapp
    )


def test_back_returns_to_previous_step_and_discards_its_answer(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    acc = client.post(
        "/api/v1/accounts",
        json={"name": "Conta Teste", "type": "checking", "initial_balance": 100},
        headers=headers,
    ).get_json()["data"]

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "1", "m0"))
    conversation._handle_event(_reply_event(phone, "expense", "m1"))
    conversation._handle_event(_text_event(phone, "50", "m2"))
    conversation._handle_event(_reply_event(phone, "none", "m3"))  # sem categoria -> vai pra conta
    conversation._handle_event(_reply_event(phone, str(acc["id"]), "m4"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_description"

    conversation._handle_event(_text_event(phone, "voltar", "m5"))
    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_account"
    assert "account_id" not in state.context_json
    assert fake_whatsapp[-1]["kind"] == "list"

    # Segue de novo com uma conta diferente e confirma — o fluxo continua normal.
    conversation._handle_event(_reply_event(phone, str(acc["id"]), "m6"))
    conversation._handle_event(_text_event(phone, "Mercado", "m7"))
    conversation._handle_event(_reply_event(phone, "confirm", "m8"))

    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None
    tx = db.session.query(Transaction).filter_by(user_id=user.id).first()
    assert tx is not None
    assert tx.description == "Mercado"


def test_back_skips_category_step_when_no_categories_exist(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    client.post(
        "/api/v1/accounts",
        json={"name": "Conta Teste", "type": "checking", "initial_balance": 100},
        headers=headers,
    )

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "1", "m0"))
    conversation._handle_event(_reply_event(phone, "expense", "m1"))
    conversation._handle_event(_text_event(phone, "50", "m2"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_account"  # sem categorias cadastradas, pula direto

    conversation._handle_event(_text_event(phone, "voltar", "m3"))
    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_amount"
    assert "amount" not in state.context_json


def test_more_than_page_size_accounts_are_split_across_list_messages(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    for i in range(11):
        client.post(
            "/api/v1/accounts",
            json={"name": f"Conta {i}", "type": "checking", "initial_balance": 0},
            headers=headers,
        )

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "1", "m0"))
    conversation._handle_event(_reply_event(phone, "expense", "m1"))
    conversation._handle_event(_text_event(phone, "50", "m2"))

    lists = [m for m in fake_whatsapp if m["kind"] == "list"]
    assert len(lists) == 2
    assert "(1/2)" in lists[0]["args"][0]
    assert "(2/2)" in lists[1]["args"][0]
    # Esse prompt não é o primeiro passo do fluxo (vem depois de
    # tipo/categoria) — reserva 1 linha pro botão "◀️ Voltar" na última
    # página (flow_utils.render_list_with_back), então só 9 itens reais
    # cabem por página em vez de 10.
    assert len(lists[0]["args"][2][0]["rows"]) == 9
    assert len(lists[1]["args"][2][0]["rows"]) == 3  # 2 contas restantes + voltar
    assert lists[1]["args"][2][0]["rows"][-1]["id"] == "back"

    # As 11 contas continuam todas alcançáveis (nenhuma foi descartada).
    all_ids = {
        row["id"]
        for m in lists
        for row in m["args"][2][0]["rows"]
        if row["id"] != "back"
    }
    assert len(all_ids) == 11

    # Escolher uma linha da segunda página funciona normalmente.
    last_account_id = lists[1]["args"][2][0]["rows"][0]["id"]
    conversation._handle_event(_reply_event(phone, last_account_id, "m3"))
    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_description"
    assert state.context_json["account_id"] == int(last_account_id)


def test_invalid_amount_reprompts_same_step(client, auth_headers, fake_whatsapp):
    user, _ = _register_and_link(client, auth_headers)
    phone = user.phone_number

    conversation._handle_event(_text_event(phone, "1", "m0"))
    conversation._handle_event(_reply_event(phone, "expense", "m1"))
    conversation._handle_event(_text_event(phone, "não é número", "m2"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_amount"


# ---------- Cartão de crédito no lançamento (Fase D3/6) ----------


def _create_account_and_card(client, headers):
    acc = client.post(
        "/api/v1/accounts",
        json={"name": "Conta Teste", "type": "checking", "initial_balance": 100},
        headers=headers,
    ).get_json()["data"]
    card = client.post(
        "/api/v1/credit-cards",
        json={"name": "Nubank", "credit_limit": 5000, "closing_day": 10, "due_day": 20},
        headers=headers,
    ).get_json()["data"]
    return acc, card


def test_expense_with_card_asks_credit_card_question(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    acc, _card = _create_account_and_card(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "1", "m0"))
    conversation._handle_event(_reply_event(phone, "expense", "m1"))
    conversation._handle_event(_text_event(phone, "50", "m2"))
    conversation._handle_event(_reply_event(phone, "none", "m3"))
    conversation._handle_event(_reply_event(phone, str(acc["id"]), "m4"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_credit_card_choice"
    assert "cartão de crédito" in fake_whatsapp[-1]["args"][0]


def test_income_never_asks_credit_card_question_even_with_cards(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    acc, _card = _create_account_and_card(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "1", "m0"))
    conversation._handle_event(_reply_event(phone, "income", "m1"))
    conversation._handle_event(_text_event(phone, "50", "m2"))
    conversation._handle_event(_reply_event(phone, "none", "m3"))
    conversation._handle_event(_reply_event(phone, str(acc["id"]), "m4"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_description"


def test_full_flow_with_credit_card_creates_invoice_and_does_not_touch_balance(
    client, auth_headers, fake_whatsapp
):
    user, headers = _register_and_link(client, auth_headers)
    acc, card = _create_account_and_card(client, headers)

    phone = user.phone_number
    steps = [
        _text_event(phone, "1", "m0"),
        _reply_event(phone, "expense", "m1"),
        _text_event(phone, "50", "m2"),
        _reply_event(phone, "none", "m3"),
        _reply_event(phone, str(acc["id"]), "m4"),
        _reply_event(phone, "card_yes", "m5"),
        _reply_event(phone, str(card["id"]), "m6"),
        _text_event(phone, "Compra parcelada", "m7"),
        _reply_event(phone, "confirm", "m8"),
    ]
    for event in steps:
        conversation._handle_event(event)

    assert db.session.query(BotConversationState).filter_by(user_id=user.id).first() is None

    tx = db.session.query(Transaction).filter_by(user_id=user.id).first()
    assert tx is not None
    assert tx.credit_card_id == card["id"]
    assert tx.invoice_id is not None

    resp = client.get(f"/api/v1/accounts/{acc['id']}", headers=headers)
    assert resp.get_json()["data"]["current_balance"] == "100.00"  # saldo não muda

    assert any("cartão" in m["args"][0].lower() for m in fake_whatsapp if m["kind"] == "text")


def test_credit_card_choice_no_skips_straight_to_description(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    acc, _card = _create_account_and_card(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "1", "m0"))
    conversation._handle_event(_reply_event(phone, "expense", "m1"))
    conversation._handle_event(_text_event(phone, "50", "m2"))
    conversation._handle_event(_reply_event(phone, "none", "m3"))
    conversation._handle_event(_reply_event(phone, str(acc["id"]), "m4"))
    conversation._handle_event(_reply_event(phone, "card_no", "m5"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_description"
    assert state.context_json["credit_card_id"] is None


def test_invalid_credit_card_reprompts_same_step(client, auth_headers, fake_whatsapp):
    user, headers = _register_and_link(client, auth_headers)
    acc, _card = _create_account_and_card(client, headers)

    phone = user.phone_number
    conversation._handle_event(_text_event(phone, "1", "m0"))
    conversation._handle_event(_reply_event(phone, "expense", "m1"))
    conversation._handle_event(_text_event(phone, "50", "m2"))
    conversation._handle_event(_reply_event(phone, "none", "m3"))
    conversation._handle_event(_reply_event(phone, str(acc["id"]), "m4"))
    conversation._handle_event(_reply_event(phone, "card_yes", "m5"))
    conversation._handle_event(_reply_event(phone, "999999", "m6"))

    state = db.session.query(BotConversationState).filter_by(user_id=user.id).first()
    assert state.step == "awaiting_credit_card"
    assert "inválido" in fake_whatsapp[-1]["args"][0]


def test_message_is_marked_processed_before_handler_side_effect_runs(
    client, auth_headers, fake_whatsapp, monkeypatch
):
    """Prova a mudança de ordem em `_handle_event` (idempotência ANTES do
    efeito colateral, ver ARCHITECTURE.md > Riscos conhecidos): se o
    handler quebrar no meio do processamento (ex.: processo caiu), a
    mensagem já está marcada como processada — uma reentrega da Meta não
    tenta rodar o handler de novo (o que poderia duplicar a Transaction se
    a quebra tivesse acontecido depois de já ter comitado o lançamento)."""
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
    ]
    for event in steps:
        conversation._handle_event(event)

    confirm_event = _reply_event(phone, "confirm", "m6")

    def _boom(*args, **kwargs):
        raise RuntimeError("processo caiu no meio do efeito colateral")

    # Simula a quebra depois do commit de mark_processed, mas antes do
    # handler terminar de criar a Transaction.
    monkeypatch.setattr(
        conversation, "_handle_flow_step", lambda *a, **k: _boom()
    )

    with pytest.raises(RuntimeError):
        conversation._handle_event(confirm_event)

    assert conversation.already_processed("m6") is True
    assert db.session.query(Transaction).filter_by(user_id=user.id).first() is None

    # Reentrega da Meta pra mesma mensagem: já está marcada como
    # processada, então o handler (que criaria a Transaction) não roda de
    # novo — mensagem "engolida" em vez de lançamento duplicado.
    monkeypatch.undo()
    conversation._handle_event(confirm_event)
    assert db.session.query(Transaction).filter_by(user_id=user.id).count() == 0
