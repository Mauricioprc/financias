"""Fluxo 'Contribuir pra meta' — multi-etapa curto, mesmo padrão de
bot/handlers/transfers.py (voltar/histórico vêm de bot/flow_utils.py).

Passos: meta (só as "in_progress") -> valor -> confirmação. Toda a regra
de negócio (status "achieved", trava de concorrência) já vive em
goal_service.contribute_to_goal — este módulo só orquestra a conversa e
formata mensagem.
"""

import logging
from decimal import Decimal

from app.services import goal_service
from app.services.exceptions import ServiceError
from bot import flow_utils, whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money, parse_amount
from bot.whatsapp_client import WhatsAppApiError

logger = logging.getLogger(__name__)


def start(user) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    goals = [g for g in goal_service.list_goals(user.id) if g.status == "in_progress"]
    if not goals:
        whatsapp_client.send_text(
            to, "Você não tem nenhuma meta em andamento. Cadastre pelo dashboard, em Metas."
        )
        return None, {}

    _render_goal_prompt(user, to)
    return "awaiting_goal", {}


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


def _active_goal_rows(user) -> list[dict]:
    goals = [g for g in goal_service.list_goals(user.id) if g.status == "in_progress"]
    return [{"id": str(g.id), "title": g.name} for g in goals]


def _render_goal_prompt(user, to: str) -> None:
    rows = _active_goal_rows(user)
    whatsapp_client.send_list_paginated(to, "Contribuir pra qual meta?", "Escolher", rows, "Metas")


def _render_amount_prompt(to: str, goal_name: str) -> None:
    whatsapp_client.send_text(
        to, f"Quanto você quer contribuir pra {goal_name}? (ex.: 100 ou 100,00)"
    )


def _confirmation_summary(goal, amount: Decimal) -> str:
    return (
        f"Contribuir {money(amount)} pra {goal.name}? "
        f"Atual: {money(goal.current_amount)} de {money(goal.target_amount)}."
    )


def _render_confirmation_prompt(user, to: str, context: dict) -> None:
    goal = goal_service.get_goal(user.id, context["goal_id"])
    summary = _confirmation_summary(goal, Decimal(context["amount"]))
    whatsapp_client.send_buttons(
        to, summary, [{"id": "confirm", "title": "Confirmar"}, {"id": "cancel", "title": "Cancelar"}]
    )


_RENDERERS = {
    "awaiting_goal": lambda user, context: _render_goal_prompt(user, to_wa_id(user.phone_number)),
    "awaiting_amount": lambda user, context: _render_amount_prompt(
        to_wa_id(user.phone_number), goal_service.get_goal(user.id, context["goal_id"]).name
    ),
    "awaiting_confirmation": lambda user, context: _render_confirmation_prompt(
        user, to_wa_id(user.phone_number), context
    ),
}


# ---------- Processamento de cada passo ----------


def _handle_awaiting_goal(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    try:
        goal = goal_service.get_goal(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Meta inválida. Escolhe uma opção da lista.")
        return "awaiting_goal", context
    if goal.status != "in_progress":
        whatsapp_client.send_text(to, "Meta inválida. Escolhe uma opção da lista.")
        return "awaiting_goal", context

    context = {**context, "goal_id": goal.id}
    _render_amount_prompt(to, goal.name)
    return "awaiting_amount", context


def _handle_awaiting_amount(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    amount = parse_amount(event.get("text") or "")
    if amount is None:
        whatsapp_client.send_text(to, "Valor inválido. Manda só o número, ex.: 100 ou 100,00.")
        return "awaiting_amount", context

    context = {**context, "amount": str(amount)}
    _render_confirmation_prompt(user, to, context)
    return "awaiting_confirmation", context


def _handle_awaiting_confirmation(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip().lower()

    if choice not in ("confirm", "confirmar"):
        whatsapp_client.send_text(to, "Contribuição cancelada.")
        return None, {}

    try:
        goal = goal_service.contribute_to_goal(
            user.id, context["goal_id"], Decimal(context["amount"])
        )
    except ServiceError:
        logger.exception("Falha ao contribuir pra meta via bot (user_id=%s).", user.id)
        whatsapp_client.send_text(
            to, "Não consegui registrar a contribuição agora. Responde 'confirmar' pra tentar de novo."
        )
        # Não limpa o estado — mesmo racional de
        # transactions.py._handle_awaiting_confirmation: se a chamada não
        # foi persistida, uma nova tentativa de "confirmar" refaz
        # exatamente essa mesma chamada, sem duplicar contribuição nenhuma.
        return "awaiting_confirmation", context

    # A contribuição já foi persistida neste ponto — uma falha a partir
    # daqui é só de comunicação, não deve fazer o usuário reenviar
    # "confirmar" (o que duplicaria a contribuição). Por isso o estado é
    # limpo mesmo se o aviso de sucesso não chegar.
    try:
        pct = min(100, round((goal.current_amount / goal.target_amount) * 100))
        text = (
            f"Contribuição registrada! {goal.name} agora está em "
            f"{money(goal.current_amount)} de {money(goal.target_amount)} ({pct}%)."
        )
        if goal.status == "achieved":
            text += "\n\n🎉 Meta atingida!"
        whatsapp_client.send_text(to, text)
    except (ServiceError, WhatsAppApiError):
        logger.exception(
            "Contribuição registrada mas falha ao confirmar por WhatsApp (user_id=%s).", user.id
        )

    return None, {}


_STEP_HANDLERS = {
    "awaiting_goal": _handle_awaiting_goal,
    "awaiting_amount": _handle_awaiting_amount,
    "awaiting_confirmation": _handle_awaiting_confirmation,
}
