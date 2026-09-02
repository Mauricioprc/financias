"""Fluxo 'Lançar transação' — o de maior uso, serve de padrão pros demais
fluxos (Fase D3). Cada passo mapeia 1:1 pros campos que
TransactionCreateSchema já exige/aceita.

Cartão de crédito (Fase D3/6): despesa com pelo menos um cartão cadastrado
ganha um passo extra opcional depois da conta ("foi no cartão?"). Só despesa,
porque transaction_service exige isso (transação de cartão não pode ser
receita); `account_id` continua obrigatório mesmo com cartão — é o schema que
já funciona assim, não é decisão tomada aqui."""

import logging
from datetime import date
from decimal import Decimal

from app.services import (
    account_service,
    category_service,
    category_suggestion_service,
    credit_card_service,
    invoice_service,
    transaction_service,
)
from app.services.exceptions import ServiceError
from bot import flow_utils, whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money, parse_amount
from bot.whatsapp_client import WhatsAppApiError

logger = logging.getLogger(__name__)

DEFAULT_DESCRIPTION = "Transação via WhatsApp"


def start(user) -> tuple[str, dict]:
    _render_type_prompt(to_wa_id(user.phone_number))
    return "awaiting_type", {}


def start_quick(user, parsed: dict) -> tuple[str | None, dict]:
    """Atalho de lançamento rápido (bot/quick_entry.py) — texto livre tipo
    "50 mercado" em vez do menu passo-a-passo. SEMPRE despesa (ver
    bot/quick_entry.py). Resolve o que dá pra resolver com confiança —
    categoria por padrão já aprendido (category_suggestion_service),
    descrição do próprio texto — e entrega o resto pro mesmo pipeline de
    sempre a partir do ponto certo (_ask_category_or_skip/_ask_account/
    _ask_credit_card_choice), sem duplicar nenhuma decisão que essas
    funções já tomam.

    NUNCA pula a pergunta de cartão mesmo quando tudo o resto foi
    resolvido — ver _ask_credit_card_choice, ela continua perguntando
    "foi no cartão?" sempre que o usuário tem algum cartão cadastrado.

    `context["_quick"]` é só um marcador interno: com ele presente e
    exatamente 1 conta cadastrada, `_ask_account` pula a pergunta de
    conta (sem ambiguidade nenhuma pra resolver). O fluxo normal nunca
    seta essa chave, então esse atalho não muda nada pra quem digita "1"
    no menu.
    """
    description_hint = (parsed.get("description_hint") or "").strip()
    description = description_hint or DEFAULT_DESCRIPTION

    context = {
        "_quick": True,
        "type": "expense",
        "amount": str(parsed["amount"]),
        "description": description,
    }

    category_id = None
    if description_hint:
        category_id = category_suggestion_service.suggest_category(user.id, description_hint)

    if category_id is not None:
        return _ask_account(user, {**context, "category_id": category_id})

    return _ask_category_or_skip(user, context)


def start_repeat(user) -> tuple[str | None, dict]:
    """Comando 'repetir' (bot/conversation.py) — repete a transação mais
    recente do usuário (conta, categoria, cartão e descrição herdados
    dela), perguntando só o valor."""
    to = to_wa_id(user.phone_number)
    items, _total = transaction_service.list_transactions(user.id, page=1, per_page=1)
    if not items:
        whatsapp_client.send_text(to, "Você ainda não lançou nada. Manda 'menu' pra começar.")
        return None, {}

    last = items[0]
    context = {
        "_repeat": True,
        "type": last.type,
        "account_id": last.account_id,
        "category_id": last.category_id,
        "credit_card_id": last.credit_card_id,
        "description": last.description,
    }

    category_label = "Sem categoria"
    if last.category_id:
        try:
            category_label = category_service.get_category(user.id, last.category_id).name
        except ServiceError:
            pass
    account = account_service.get_account(user.id, last.account_id)

    whatsapp_client.send_text(
        to,
        f"Repetir como {last.description} — {category_label} — {account.name}? "
        "Só falta o valor.",
    )
    _render_amount_prompt(to)
    return "awaiting_amount", context


def handle_step(user, step: str, context: dict, event: dict) -> tuple[str | None, dict]:
    """Ponto de entrada chamado pelo orquestrador (bot/conversation.py). A
    keyword 'voltar' e o histórico de passos que ela exige são genéricos —
    ver bot/flow_utils.py."""
    to = to_wa_id(user.phone_number)
    history, clean_context = flow_utils.split_history(context)

    if flow_utils.is_back(event):
        return flow_utils.handle_back(
            user, step, clean_context, history, _RENDERERS, to, whatsapp_client.send_text
        )

    handler = _STEP_HANDLERS.get(step)
    if handler is None:
        whatsapp_client.send_text(to, "Algo deu errado nesse fluxo. Voltando ao menu.")
        return None, {}

    next_step, new_context = handler(user, clean_context, event)
    if next_step is None:
        return None, {}

    return next_step, flow_utils.advance(history, step, next_step, clean_context, new_context)


# ---------- Renderização de cada pergunta (reenvio, sem processar resposta) ----------


def _render_type_prompt(to: str) -> None:
    whatsapp_client.send_buttons(
        to,
        "Vamos lançar uma transação. É receita ou despesa?",
        [{"id": "income", "title": "Receita"}, {"id": "expense", "title": "Despesa"}],
    )


def _render_amount_prompt(to: str) -> None:
    whatsapp_client.send_text(to, "Qual o valor? (ex.: 50 ou 50,00)")


def _category_rows(user, tx_type: str) -> list[dict]:
    categories = [c for c in category_service.list_categories(user.id) if c.type == tx_type]
    rows = [{"id": str(c.id), "title": c.name} for c in categories]
    rows.append({"id": "none", "title": "Sem categoria"})
    return rows


def _render_category_prompt(user, to: str, context: dict) -> None:
    rows = _category_rows(user, context["type"])
    whatsapp_client.send_list_paginated(to, "Qual categoria?", "Escolher", rows, "Categorias")


def _account_rows(user) -> list[dict]:
    accounts = account_service.list_accounts(user.id)
    return [{"id": str(a.id), "title": a.name} for a in accounts]


def _render_account_prompt(user, to: str) -> None:
    rows = _account_rows(user)
    whatsapp_client.send_list_paginated(to, "Em qual conta?", "Escolher", rows, "Contas")


def _render_credit_card_choice_prompt(to: str) -> None:
    whatsapp_client.send_buttons(
        to,
        "Foi no cartão de crédito?",
        [{"id": "card_yes", "title": "Sim"}, {"id": "card_no", "title": "Não"}],
    )


def _credit_card_rows(user) -> list[dict]:
    cards = credit_card_service.list_credit_cards(user.id)
    return [{"id": str(c.id), "title": c.name} for c in cards]


def _render_credit_card_prompt(user, to: str) -> None:
    rows = _credit_card_rows(user)
    whatsapp_client.send_list_paginated(to, "Qual cartão?", "Escolher", rows, "Cartões")


def _render_description_prompt(to: str) -> None:
    whatsapp_client.send_text(to, "Descrição? (ou manda '-' para pular)")


def _confirmation_summary(user, context: dict) -> str:
    type_label = "Receita" if context["type"] == "income" else "Despesa"
    category_label = "Sem categoria"
    if context.get("category_id"):
        try:
            category_label = category_service.get_category(user.id, context["category_id"]).name
        except ServiceError:
            pass
    account = account_service.get_account(user.id, context["account_id"])

    card_line = ""
    if context.get("credit_card_id"):
        try:
            card = credit_card_service.get_credit_card(user.id, context["credit_card_id"])
            card_line = f"Cartão: {card.name}\n"
        except ServiceError:
            pass

    return (
        f"Confirma o lançamento?\n\n"
        f"{type_label}: {money(context['amount'])}\n"
        f"Categoria: {category_label}\n"
        f"Conta: {account.name}\n"
        f"{card_line}"
        f"Descrição: {context['description']}"
    )


def _render_confirmation_prompt(user, to: str, context: dict) -> None:
    summary = _confirmation_summary(user, context)
    whatsapp_client.send_buttons(
        to, summary, [{"id": "confirm", "title": "Confirmar"}, {"id": "cancel", "title": "Cancelar"}]
    )


_RENDERERS = {
    "awaiting_type": lambda user, context: _render_type_prompt(to_wa_id(user.phone_number)),
    "awaiting_amount": lambda user, context: _render_amount_prompt(to_wa_id(user.phone_number)),
    "awaiting_category": lambda user, context: _render_category_prompt(
        user, to_wa_id(user.phone_number), context
    ),
    "awaiting_account": lambda user, context: _render_account_prompt(
        user, to_wa_id(user.phone_number)
    ),
    "awaiting_credit_card_choice": lambda user, context: _render_credit_card_choice_prompt(
        to_wa_id(user.phone_number)
    ),
    "awaiting_credit_card": lambda user, context: _render_credit_card_prompt(
        user, to_wa_id(user.phone_number)
    ),
    "awaiting_description": lambda user, context: _render_description_prompt(
        to_wa_id(user.phone_number)
    ),
    "awaiting_confirmation": lambda user, context: _render_confirmation_prompt(
        user, to_wa_id(user.phone_number), context
    ),
}


# ---------- Processamento de cada passo (interpreta a resposta do usuário) ----------


def _handle_awaiting_type(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip().lower()
    tx_type = {"income": "income", "receita": "income", "expense": "expense", "despesa": "expense"}.get(
        choice
    )
    if tx_type is None:
        whatsapp_client.send_buttons(
            to,
            "Não entendi. É receita ou despesa?",
            [{"id": "income", "title": "Receita"}, {"id": "expense", "title": "Despesa"}],
        )
        return "awaiting_type", context

    context = {**context, "type": tx_type}
    _render_amount_prompt(to)
    return "awaiting_amount", context


def _ask_category_or_skip(user, context: dict) -> tuple[str, dict]:
    """Categoria: se não houver nenhuma categoria cadastrada desse tipo,
    pula direto pra conta com category_id=None — mesma regra usada tanto
    no fluxo normal (a partir do valor) quanto no atalho de lançamento
    rápido (start_quick, quando a sugestão automática não encontrou nada
    confiável)."""
    to = to_wa_id(user.phone_number)
    rows = _category_rows(user, context["type"])
    if not rows[:-1]:  # só sobra o "Sem categoria" -> não há categorias desse tipo
        return _ask_account(user, {**context, "category_id": None})

    _render_category_prompt(user, to, context)
    return "awaiting_category", context


def _handle_awaiting_amount(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    amount = parse_amount(event.get("text") or "")
    if amount is None:
        whatsapp_client.send_text(to, "Valor inválido. Manda só o número, ex.: 50 ou 50,00.")
        return "awaiting_amount", context

    context = {**context, "amount": str(amount)}

    if context.get("_repeat"):
        # Comando 'repetir' (start_repeat): todo o resto já veio da
        # transação anterior — só faltava o valor, então vai direto pra
        # confirmação em vez de perguntar categoria de novo.
        _render_confirmation_prompt(user, to, context)
        return "awaiting_confirmation", context

    return _ask_category_or_skip(user, context)


def _handle_awaiting_category(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    if choice == "none":
        return _ask_account(user, {**context, "category_id": None})

    try:
        category = category_service.get_category(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Categoria inválida. Escolhe uma opção da lista.")
        return "awaiting_category", context

    return _ask_account(user, {**context, "category_id": category.id})


def _ask_account(user, context: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    accounts = account_service.list_accounts(user.id)
    if not accounts:
        whatsapp_client.send_text(
            to, "Você não tem nenhuma conta cadastrada ainda — cadastre uma no dashboard primeiro."
        )
        return None, {}

    # Atalho de lançamento rápido (start_quick) marca o contexto com
    # "_quick" — com exatamente 1 conta cadastrada, não há ambiguidade
    # nenhuma pra resolver, então pula a pergunta. O fluxo normal nunca
    # seta essa chave, então esse comportamento não muda em nada pra quem
    # digita "1" no menu (sempre pergunta a conta, mesmo com só uma).
    if context.get("_quick") and len(accounts) == 1:
        return _ask_credit_card_choice(user, {**context, "account_id": accounts[0].id})

    _render_account_prompt(user, to)
    return "awaiting_account", context


def _handle_awaiting_account(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    try:
        account = account_service.get_account(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Conta inválida. Escolhe uma opção da lista.")
        return "awaiting_account", context

    return _ask_credit_card_choice(user, {**context, "account_id": account.id})


def _proceed_after_credit_card_step(user, to: str, context: dict) -> tuple[str, dict]:
    """Depois de resolver cartão (perguntado ou pulado): descrição — a
    menos que o atalho de lançamento rápido ou o comando 'repetir' já
    tenham resolvido ela (start_quick/start_repeat setam
    context["description"] de antemão), caso em que pula direto pra
    confirmação. No fluxo normal, "description" nunca está em context
    nesse ponto, então esse comportamento não muda em nada."""
    if context.get("description"):
        _render_confirmation_prompt(user, to, context)
        return "awaiting_confirmation", context

    _render_description_prompt(to)
    return "awaiting_description", context


def _ask_credit_card_choice(user, context: dict) -> tuple[str, dict]:
    to = to_wa_id(user.phone_number)
    if context["type"] != "expense" or not _credit_card_rows(user):
        return _proceed_after_credit_card_step(user, to, context)

    _render_credit_card_choice_prompt(to)
    return "awaiting_credit_card_choice", context


def _handle_awaiting_credit_card_choice(
    user, context: dict, event: dict
) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip().lower()

    if choice in ("card_no", "não", "nao"):
        context = {**context, "credit_card_id": None}
        return _proceed_after_credit_card_step(user, to, context)

    if choice in ("card_yes", "sim"):
        _render_credit_card_prompt(user, to)
        return "awaiting_credit_card", context

    _render_credit_card_choice_prompt(to)
    return "awaiting_credit_card_choice", context


def _handle_awaiting_credit_card(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    try:
        card = credit_card_service.get_credit_card(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Cartão inválido. Escolhe uma opção da lista.")
        return "awaiting_credit_card", context

    context = {**context, "credit_card_id": card.id}
    return _proceed_after_credit_card_step(user, to, context)


def _handle_awaiting_description(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    raw = (event.get("text") or "").strip()
    description = DEFAULT_DESCRIPTION if raw == "-" or not raw else raw
    context = {**context, "description": description}

    _render_confirmation_prompt(user, to, context)
    return "awaiting_confirmation", context


def _success_message(user, context: dict) -> str:
    """Transação de cartão não mexe em saldo de conta (transaction_service só
    debita/credita `current_balance` quando não há cartão) — por isso a
    confirmação mostra o total da fatura em vez do saldo da conta nesse caso."""
    if context.get("credit_card_id"):
        card = credit_card_service.get_credit_card(user.id, context["credit_card_id"])
        open_invoices = invoice_service.list_invoices(
            user.id, credit_card_id=card.id, status="open"
        )
        if open_invoices:
            invoice_total = money(open_invoices[0].total_amount)
            return f"Lançado no cartão {card.name}! Fatura atual: {invoice_total}"
        return f"Lançado no cartão {card.name}!"

    updated_account = account_service.get_account(user.id, context["account_id"])
    balance = money(updated_account.current_balance)
    return f"Lançado! Novo saldo de {updated_account.name}: {balance}"


def _handle_awaiting_confirmation(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip().lower()

    if choice not in ("confirm", "confirmar"):
        whatsapp_client.send_text(to, "Lançamento cancelado.")
        return None, {}

    try:
        transaction_service.create_transaction(
            user_id=user.id,
            account_id=context["account_id"],
            category_id=context.get("category_id"),
            credit_card_id=context.get("credit_card_id"),
            type=context["type"],
            description=context["description"],
            amount=Decimal(context["amount"]),
            date=date.today(),
            is_paid=True,
            notes=None,
        )
    except ServiceError:
        logger.exception("Falha ao criar transação via bot (user_id=%s).", user.id)
        whatsapp_client.send_text(
            to, "Não consegui lançar a transação agora. Responde 'confirmar' pra tentar de novo."
        )
        # Não limpa o estado: se limpasse aqui, o usuário reenviaria "confirmar"
        # achando que ainda não tentou, e não teria como saber se já foi criada
        # ou não — mantendo o estado, uma nova tentativa de "confirmar" refaz
        # exatamente essa mesma chamada, sem duplicar nada que não foi criado.
        return "awaiting_confirmation", context

    # A transação já foi persistida neste ponto — uma falha a partir daqui é só
    # de comunicação (não deve fazer o usuário reenviar "confirmar", o que
    # duplicaria o lançamento). Por isso o estado é limpo mesmo se o aviso de
    # sucesso não chegar.
    try:
        whatsapp_client.send_text(to, _success_message(user, context))
    except (ServiceError, WhatsAppApiError):
        logger.exception(
            "Transação criada mas falha ao confirmar por WhatsApp (user_id=%s).", user.id
        )

    return None, {}


_STEP_HANDLERS = {
    "awaiting_type": _handle_awaiting_type,
    "awaiting_amount": _handle_awaiting_amount,
    "awaiting_category": _handle_awaiting_category,
    "awaiting_account": _handle_awaiting_account,
    "awaiting_credit_card_choice": _handle_awaiting_credit_card_choice,
    "awaiting_credit_card": _handle_awaiting_credit_card,
    "awaiting_description": _handle_awaiting_description,
    "awaiting_confirmation": _handle_awaiting_confirmation,
}
