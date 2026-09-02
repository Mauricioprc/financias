"""Fluxo 'Categorizar assinatura' — multi-etapa curto, mesmo padrão de
bot/handlers/spending_by_category.py (voltar/histórico vêm de
bot/flow_utils.py). Edita só o category_id de uma recorrência já
cadastrada — criar/editar os outros campos continua exclusivo do
dashboard, igual bot/handlers/recurring.py (listagem, só leitura)."""

from app.services import category_service, recurring_transaction_service
from app.services.exceptions import ServiceError
from bot import flow_utils, whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money

_NO_CATEGORY_CHOICE = "none"


def start(user) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    active = _active_recurrences(user)
    if not active:
        whatsapp_client.send_text(to, "Você ainda não tem recorrência cadastrada.")
        return None, {}

    _render_recurring_prompt(user, to)
    return "awaiting_recurring", {}


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


def _active_recurrences(user) -> list:
    return [
        r
        for r in recurring_transaction_service.list_recurring_transactions(user.id)
        if r.is_active
    ]


def _recurring_rows(user) -> list[dict]:
    return [
        {"id": str(r.id), "title": f"{r.description} ({money(r.amount)})"}
        for r in _active_recurrences(user)
    ]


def _category_rows(user, type_: str) -> list[dict]:
    categories = [c for c in category_service.list_categories(user.id) if c.type == type_]
    rows = [{"id": str(c.id), "title": c.name} for c in categories]
    rows.append({"id": _NO_CATEGORY_CHOICE, "title": "Sem categoria"})
    return rows


# ---------- Renderização de cada pergunta ----------


def _render_recurring_prompt(user, to: str) -> None:
    # Primeiro passo do fluxo — nunca tem botão de voltar.
    rows = _recurring_rows(user)
    flow_utils.render_list_with_back(
        to, "Categorizar qual recorrência?", "Escolher", rows, "Recorrências", has_history=False
    )


def _render_category_prompt(user, to: str, context: dict) -> None:
    recurring = recurring_transaction_service.get_recurring_transaction(
        user.id, context["recurring_id"]
    )
    rows = _category_rows(user, recurring.type)
    flow_utils.render_list_with_back(
        to,
        f"Qual categoria pra '{recurring.description}'?",
        "Escolher",
        rows,
        "Categorias",
        has_history=True,
    )


_RENDERERS = {
    "awaiting_recurring": lambda user, context: _render_recurring_prompt(
        user, to_wa_id(user.phone_number)
    ),
    "awaiting_category": lambda user, context: _render_category_prompt(
        user, to_wa_id(user.phone_number), context
    ),
}


# ---------- Processamento de cada passo ----------


def _handle_awaiting_recurring(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    try:
        recurring = recurring_transaction_service.get_recurring_transaction(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Recorrência inválida. Escolhe uma opção da lista.")
        return "awaiting_recurring", context
    if not recurring.is_active:
        whatsapp_client.send_text(to, "Recorrência inválida. Escolhe uma opção da lista.")
        return "awaiting_recurring", context

    context = {**context, "recurring_id": recurring.id}
    _render_category_prompt(user, to, context)
    return "awaiting_category", context


def _handle_awaiting_category(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    recurring = recurring_transaction_service.get_recurring_transaction(
        user.id, context["recurring_id"]
    )

    if choice == _NO_CATEGORY_CHOICE:
        category_id = None
        category_name = "Sem categoria"
    else:
        try:
            category = category_service.get_category(user.id, int(choice))
        except (ValueError, ServiceError):
            whatsapp_client.send_text(to, "Categoria inválida. Escolhe uma opção da lista.")
            return "awaiting_category", context
        if category.type != recurring.type:
            whatsapp_client.send_text(to, "Categoria inválida. Escolhe uma opção da lista.")
            return "awaiting_category", context
        category_id = category.id
        category_name = category.name

    updated = recurring_transaction_service.update_recurring_transaction(
        user.id, recurring.id, category_id=category_id
    )
    whatsapp_client.send_text(
        to, f"Categoria de '{updated.description}' atualizada para {category_name}."
    )
    return None, {}


_STEP_HANDLERS = {
    "awaiting_recurring": _handle_awaiting_recurring,
    "awaiting_category": _handle_awaiting_category,
}
