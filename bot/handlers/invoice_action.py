"""Fluxo 'Pagar/fechar fatura' — multi-etapa, mesmo padrão de
bot/handlers/transfers.py (voltar/histórico vêm de bot/flow_utils.py).

Passos: cartão -> fatura (aberta ou fechada não paga) -> ação disponível
pro status daquela fatura -> (se pagamento) valor (só parcial)/conta ->
confirmação. Toda regra de negócio (o que cada status permite, cálculo de
saldo devedor, geração da Transaction de pagamento) já vive em
invoice_service — este módulo só orquestra a conversa e formata mensagem.
"""

import logging
from decimal import Decimal

from app.services import account_service, credit_card_service, invoice_service
from app.services.exceptions import ServiceError
from bot import flow_utils, whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money, parse_amount
from bot.whatsapp_client import WhatsAppApiError

logger = logging.getLogger(__name__)

_STATUS_LABELS = {"open": "aberta", "closed": "fechada"}


def start(user) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    cards = [c for c in credit_card_service.list_credit_cards(user.id) if not c.is_archived]
    if not cards:
        whatsapp_client.send_text(to, "Você não tem nenhum cartão cadastrado.")
        return None, {}

    _render_card_prompt(user, to)
    return "awaiting_card", {}


def handle_step(user, step: str, context: dict, event: dict) -> tuple[str | None, dict]:
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


# ---------- Helpers de dado ----------


def _actionable_invoices(user, card_id: int) -> list:
    return [
        inv
        for inv in invoice_service.list_invoices(user.id, credit_card_id=card_id)
        if inv.status in ("open", "closed")
    ]


def _remaining(invoice) -> Decimal:
    return invoice.total_amount - invoice.paid_amount


# ---------- Renderização de cada pergunta ----------


def _render_card_prompt(user, to: str) -> None:
    cards = [c for c in credit_card_service.list_credit_cards(user.id) if not c.is_archived]
    rows = [{"id": str(c.id), "title": c.name} for c in cards]
    whatsapp_client.send_list_paginated(to, "Qual cartão?", "Escolher", rows, "Cartões")


def _render_invoice_prompt(user, to: str, context: dict) -> None:
    invoices = _actionable_invoices(user, context["card_id"])
    rows = [
        {
            "id": str(inv.id),
            "title": f"Referência {inv.reference_month.strftime('%m/%Y')} — "
            f"{money(inv.total_amount)} ({_STATUS_LABELS[inv.status]})",
        }
        for inv in invoices
    ]
    whatsapp_client.send_list_paginated(to, "Qual fatura?", "Escolher", rows, "Faturas")


def _render_close_confirmation_prompt(user, to: str, context: dict) -> None:
    invoice = invoice_service.get_invoice(user.id, context["invoice_id"])
    text = (
        f"Fechar a fatura de {invoice.reference_month.strftime('%m/%Y')}, "
        f"total {money(invoice.total_amount)}? "
        "Não será mais possível adicionar compras a ela."
    )
    whatsapp_client.send_buttons(
        to, text, [{"id": "confirm", "title": "Confirmar"}, {"id": "cancel", "title": "Cancelar"}]
    )


def _render_payment_type_prompt(user, to: str, context: dict) -> None:
    invoice = invoice_service.get_invoice(user.id, context["invoice_id"])
    text = (
        f"Fatura de {invoice.reference_month.strftime('%m/%Y')} — "
        f"saldo devedor {money(_remaining(invoice))}. O que você quer fazer?"
    )
    whatsapp_client.send_buttons(
        to, text, [{"id": "full", "title": "Pagar tudo"}, {"id": "partial", "title": "Pagar parte"}]
    )


def _render_payment_amount_prompt(user, to: str, context: dict) -> None:
    invoice = invoice_service.get_invoice(user.id, context["invoice_id"])
    whatsapp_client.send_text(
        to,
        f"Quanto você quer pagar? Saldo devedor: {money(_remaining(invoice))}",
    )


def _render_payment_account_prompt(user, to: str) -> None:
    accounts = account_service.list_accounts(user.id)
    rows = [{"id": str(a.id), "title": a.name} for a in accounts]
    whatsapp_client.send_list_paginated(to, "Pagar com qual conta?", "Escolher", rows, "Contas")


def _payment_amount(user, context: dict) -> Decimal:
    if context["payment_type"] == "full":
        invoice = invoice_service.get_invoice(user.id, context["invoice_id"])
        return _remaining(invoice)
    return Decimal(context["amount"])


def _render_payment_confirmation_prompt(user, to: str, context: dict) -> None:
    invoice = invoice_service.get_invoice(user.id, context["invoice_id"])
    account = account_service.get_account(user.id, context["account_id"])
    amount = _payment_amount(user, context)
    text = (
        f"Pagar {money(amount)} da fatura de {invoice.reference_month.strftime('%m/%Y')} "
        f"com a conta {account.name}?"
    )
    whatsapp_client.send_buttons(
        to, text, [{"id": "confirm", "title": "Confirmar"}, {"id": "cancel", "title": "Cancelar"}]
    )


_RENDERERS = {
    "awaiting_card": lambda user, context: _render_card_prompt(user, to_wa_id(user.phone_number)),
    "awaiting_invoice": lambda user, context: _render_invoice_prompt(
        user, to_wa_id(user.phone_number), context
    ),
    "awaiting_close_confirmation": lambda user, context: _render_close_confirmation_prompt(
        user, to_wa_id(user.phone_number), context
    ),
    "awaiting_payment_type": lambda user, context: _render_payment_type_prompt(
        user, to_wa_id(user.phone_number), context
    ),
    "awaiting_payment_amount": lambda user, context: _render_payment_amount_prompt(
        user, to_wa_id(user.phone_number), context
    ),
    "awaiting_payment_account": lambda user, context: _render_payment_account_prompt(
        user, to_wa_id(user.phone_number)
    ),
    "awaiting_payment_confirmation": lambda user, context: _render_payment_confirmation_prompt(
        user, to_wa_id(user.phone_number), context
    ),
}


# ---------- Processamento de cada passo ----------


def _handle_awaiting_card(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    try:
        card = credit_card_service.get_credit_card(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Cartão inválido. Escolhe uma opção da lista.")
        return "awaiting_card", context

    if not _actionable_invoices(user, card.id):
        whatsapp_client.send_text(
            to, "Esse cartão não tem fatura aberta nem fechada pendente de pagamento."
        )
        return None, {}

    context = {**context, "card_id": card.id}
    _render_invoice_prompt(user, to, context)
    return "awaiting_invoice", context


def _handle_awaiting_invoice(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    try:
        invoice = invoice_service.get_invoice(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Fatura inválida. Escolhe uma opção da lista.")
        return "awaiting_invoice", context
    if invoice.status not in ("open", "closed") or invoice.credit_card_id != context["card_id"]:
        whatsapp_client.send_text(to, "Fatura inválida. Escolhe uma opção da lista.")
        return "awaiting_invoice", context

    context = {**context, "invoice_id": invoice.id, "status": invoice.status}

    if invoice.status == "open":
        # Fatura aberta só tem uma ação sensata: fechar — vai direto pra
        # confirmação, sem perguntar "o que você quer fazer" à toa.
        _render_close_confirmation_prompt(user, to, context)
        return "awaiting_close_confirmation", context

    _render_payment_type_prompt(user, to, context)
    return "awaiting_payment_type", context


def _handle_awaiting_close_confirmation(
    user, context: dict, event: dict
) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip().lower()

    if choice not in ("confirm", "confirmar"):
        whatsapp_client.send_text(to, "Fechamento cancelado.")
        return None, {}

    try:
        invoice = invoice_service.close_invoice(user.id, context["invoice_id"])
    except ServiceError:
        logger.exception("Falha ao fechar fatura via bot (user_id=%s).", user.id)
        whatsapp_client.send_text(
            to, "Não consegui fechar a fatura agora. Responde 'confirmar' pra tentar de novo."
        )
        return "awaiting_close_confirmation", context

    try:
        whatsapp_client.send_text(
            to,
            f"Fatura de {invoice.reference_month.strftime('%m/%Y')} fechada! "
            f"Total: {money(invoice.total_amount)}.",
        )
    except (ServiceError, WhatsAppApiError):
        logger.exception(
            "Fatura fechada mas falha ao confirmar por WhatsApp (user_id=%s).", user.id
        )

    return None, {}


def _handle_awaiting_payment_type(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip().lower()

    if choice == "full":
        context = {**context, "payment_type": "full"}
        _render_payment_account_prompt(user, to)
        return "awaiting_payment_account", context

    if choice == "partial":
        context = {**context, "payment_type": "partial"}
        _render_payment_amount_prompt(user, to, context)
        return "awaiting_payment_amount", context

    _render_payment_type_prompt(user, to, context)
    return "awaiting_payment_type", context


def _handle_awaiting_payment_amount(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    amount = parse_amount(event.get("text") or "")
    if amount is None:
        whatsapp_client.send_text(to, "Valor inválido. Manda só o número, ex.: 50 ou 50,00.")
        return "awaiting_payment_amount", context

    invoice = invoice_service.get_invoice(user.id, context["invoice_id"])
    remaining = _remaining(invoice)
    if amount > remaining:
        whatsapp_client.send_text(
            to, f"Valor maior que o saldo devedor ({money(remaining)})."
        )
        return "awaiting_payment_amount", context

    context = {**context, "amount": str(amount)}
    _render_payment_account_prompt(user, to)
    return "awaiting_payment_account", context


def _handle_awaiting_payment_account(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    try:
        account = account_service.get_account(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Conta inválida. Escolhe uma opção da lista.")
        return "awaiting_payment_account", context

    context = {**context, "account_id": account.id}
    _render_payment_confirmation_prompt(user, to, context)
    return "awaiting_payment_confirmation", context


def _handle_awaiting_payment_confirmation(
    user, context: dict, event: dict
) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip().lower()

    if choice not in ("confirm", "confirmar"):
        whatsapp_client.send_text(to, "Pagamento cancelado.")
        return None, {}

    try:
        if context["payment_type"] == "full":
            invoice = invoice_service.pay_invoice(user.id, context["invoice_id"], context["account_id"])
        else:
            invoice = invoice_service.register_payment(
                user.id, context["invoice_id"], context["account_id"], Decimal(context["amount"])
            )
    except ServiceError:
        logger.exception("Falha ao pagar fatura via bot (user_id=%s).", user.id)
        whatsapp_client.send_text(
            to, "Não consegui registrar o pagamento agora. Responde 'confirmar' pra tentar de novo."
        )
        # Não limpa o estado — mesmo racional de
        # transactions.py._handle_awaiting_confirmation: se o pagamento não
        # foi persistido, uma nova tentativa de "confirmar" refaz
        # exatamente essa mesma chamada, sem duplicar pagamento nenhum.
        return "awaiting_payment_confirmation", context

    try:
        account = account_service.get_account(user.id, context["account_id"])
        status_label = "paga" if invoice.status == "paid" else "com pagamento parcial registrado"
        whatsapp_client.send_text(
            to,
            f"Fatura de {invoice.reference_month.strftime('%m/%Y')} {status_label}! "
            f"Saldo de {account.name}: {money(account.current_balance)}",
        )
    except (ServiceError, WhatsAppApiError):
        logger.exception(
            "Pagamento registrado mas falha ao confirmar por WhatsApp (user_id=%s).", user.id
        )

    return None, {}


_STEP_HANDLERS = {
    "awaiting_card": _handle_awaiting_card,
    "awaiting_invoice": _handle_awaiting_invoice,
    "awaiting_close_confirmation": _handle_awaiting_close_confirmation,
    "awaiting_payment_type": _handle_awaiting_payment_type,
    "awaiting_payment_amount": _handle_awaiting_payment_amount,
    "awaiting_payment_account": _handle_awaiting_payment_account,
    "awaiting_payment_confirmation": _handle_awaiting_payment_confirmation,
}
