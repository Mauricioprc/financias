"""Fluxo 'Transferências' — multi-etapa curto, mesmo padrão de
bot/handlers/transactions.py (voltar/histórico vêm de bot/flow_utils.py).

Passos: conta de origem -> conta de destino -> valor -> confirmação.
"""

import logging
from datetime import date
from decimal import Decimal

from app.services import account_service, transfer_service
from app.services.exceptions import ServiceError
from bot import flow_utils, whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money, parse_amount
from bot.whatsapp_client import WhatsAppApiError

logger = logging.getLogger(__name__)


def start(user) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    if len(account_service.list_accounts(user.id)) < 2:
        whatsapp_client.send_text(
            to, "Você precisa de pelo menos duas contas cadastradas para transferir entre elas."
        )
        return None, {}

    _render_from_account_prompt(user, to)
    return "awaiting_from_account", {}


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


# ---------- Renderização de cada pergunta ----------


def _account_rows(user, exclude_id: int | None = None) -> list[dict]:
    accounts = account_service.list_accounts(user.id)
    return [{"id": str(a.id), "title": a.name} for a in accounts if a.id != exclude_id]


def _render_from_account_prompt(user, to: str) -> None:
    rows = _account_rows(user)
    whatsapp_client.send_list_paginated(to, "Transferir de qual conta?", "Escolher", rows, "Contas")


def _render_to_account_prompt(user, to: str, context: dict) -> None:
    rows = _account_rows(user, exclude_id=context.get("from_account_id"))
    whatsapp_client.send_list_paginated(
        to, "Transferir para qual conta?", "Escolher", rows, "Contas"
    )


def _render_amount_prompt(to: str) -> None:
    whatsapp_client.send_text(to, "Qual o valor da transferência? (ex.: 50 ou 50,00)")


def _confirmation_summary(user, context: dict) -> str:
    from_account = account_service.get_account(user.id, context["from_account_id"])
    to_account = account_service.get_account(user.id, context["to_account_id"])
    return (
        f"Confirma a transferência?\n\n"
        f"De: {from_account.name}\n"
        f"Para: {to_account.name}\n"
        f"Valor: {money(context['amount'])}"
    )


def _render_confirmation_prompt(user, to: str, context: dict) -> None:
    summary = _confirmation_summary(user, context)
    whatsapp_client.send_buttons(
        to,
        summary,
        [{"id": "confirm", "title": "Confirmar"}, {"id": "cancel", "title": "Cancelar"}],
    )


_RENDERERS = {
    "awaiting_from_account": lambda user, context: _render_from_account_prompt(
        user, to_wa_id(user.phone_number)
    ),
    "awaiting_to_account": lambda user, context: _render_to_account_prompt(
        user, to_wa_id(user.phone_number), context
    ),
    "awaiting_amount": lambda user, context: _render_amount_prompt(to_wa_id(user.phone_number)),
    "awaiting_confirmation": lambda user, context: _render_confirmation_prompt(
        user, to_wa_id(user.phone_number), context
    ),
}


# ---------- Processamento de cada passo ----------


def _handle_awaiting_from_account(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    try:
        account = account_service.get_account(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Conta inválida. Escolhe uma opção da lista.")
        return "awaiting_from_account", context

    context = {**context, "from_account_id": account.id}
    _render_to_account_prompt(user, to, context)
    return "awaiting_to_account", context


def _handle_awaiting_to_account(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    try:
        account = account_service.get_account(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Conta inválida. Escolhe uma opção da lista.")
        return "awaiting_to_account", context

    if account.id == context["from_account_id"]:
        whatsapp_client.send_text(to, "A conta de destino precisa ser diferente da de origem.")
        return "awaiting_to_account", context

    context = {**context, "to_account_id": account.id}
    _render_amount_prompt(to)
    return "awaiting_amount", context


def _handle_awaiting_amount(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    amount = parse_amount(event.get("text") or "")
    if amount is None:
        whatsapp_client.send_text(to, "Valor inválido. Manda só o número, ex.: 50 ou 50,00.")
        return "awaiting_amount", context

    context = {**context, "amount": str(amount)}
    _render_confirmation_prompt(user, to, context)
    return "awaiting_confirmation", context


def _handle_awaiting_confirmation(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip().lower()

    if choice not in ("confirm", "confirmar"):
        whatsapp_client.send_text(to, "Transferência cancelada.")
        return None, {}

    try:
        transfer_service.create_transfer(
            user_id=user.id,
            from_account_id=context["from_account_id"],
            to_account_id=context["to_account_id"],
            amount=Decimal(context["amount"]),
            date=date.today(),
            description="Transferência via WhatsApp",
        )
    except ServiceError:
        logger.exception("Falha ao criar transferência via bot (user_id=%s).", user.id)
        whatsapp_client.send_text(
            to, "Não consegui fazer a transferência agora. Responde 'confirmar' pra tentar de novo."
        )
        return "awaiting_confirmation", context

    try:
        from_account = account_service.get_account(user.id, context["from_account_id"])
        to_account = account_service.get_account(user.id, context["to_account_id"])
        whatsapp_client.send_text(
            to,
            f"Transferido! {from_account.name}: {money(from_account.current_balance)} | "
            f"{to_account.name}: {money(to_account.current_balance)}",
        )
    except (ServiceError, WhatsAppApiError):
        logger.exception(
            "Transferência criada mas falha ao confirmar por WhatsApp (user_id=%s).", user.id
        )

    return None, {}


_STEP_HANDLERS = {
    "awaiting_from_account": _handle_awaiting_from_account,
    "awaiting_to_account": _handle_awaiting_to_account,
    "awaiting_amount": _handle_awaiting_amount,
    "awaiting_confirmation": _handle_awaiting_confirmation,
}
