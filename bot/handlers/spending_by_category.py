"""Fluxo 'Gastos por categoria' — multi-etapa curto, mesmo padrão de
bot/handlers/goal_contribution.py (voltar/histórico vêm de bot/flow_utils.py).

Passo 1: período (mês atual, mês passado, ou escolher outro mês em texto).
Passo 2: total do mês (todas as categorias) ou uma categoria específica.
Passo 3 (só no caminho "categoria específica"): escolher a categoria. Toda
a soma já vem de report_service.category_breakdown (já usado pelo
dashboard web, já cobre conta e cartão juntos) — este módulo só filtra o
retorno pela categoria escolhida, nunca refaz a soma."""

from datetime import date

from app.services import category_service, report_service
from app.services.exceptions import ServiceError
from app.utils.datetime_utils import add_months
from bot import flow_utils, whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money

_CURRENT_MONTH_CHOICE = "current_month"
_LAST_MONTH_CHOICE = "last_month"
_CUSTOM_MONTH_CHOICE = "custom_month"

_TOTAL_MONTH_CHOICE = "current_month"
_SPECIFIC_CATEGORY_CHOICE = "specific"

_MIN_YEAR = 2000
_MAX_YEAR = 2100


def start(user) -> tuple[str, dict]:
    _render_period_prompt(to_wa_id(user.phone_number))
    return "awaiting_period", {}


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


# ---------- Helpers de período ----------


def _current_month_str() -> str:
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


def _last_month_str() -> str:
    today = date.today()
    year, month = add_months(today.year, today.month, -1)
    return f"{year:04d}-{month:02d}"


def _parse_custom_month(text: str) -> str | None:
    """Espera "MM/AAAA" e devolve "AAAA-MM", ou None se inválido."""
    parts = (text or "").strip().split("/")
    if len(parts) != 2:
        return None
    month_str, year_str = parts
    if not (month_str.isdigit() and year_str.isdigit()):
        return None
    month, year = int(month_str), int(year_str)
    if not (1 <= month <= 12) or not (_MIN_YEAR <= year <= _MAX_YEAR):
        return None
    return f"{year:04d}-{month:02d}"


def _month_label(month: str) -> str:
    year_str, month_str = month.split("-")
    return f"{month_str}/{year_str}"


# ---------- Helpers de dado ----------


def _expense_category_rows(user) -> list[dict]:
    categories = [c for c in category_service.list_categories(user.id) if c.type == "expense"]
    return [{"id": str(c.id), "title": c.name} for c in categories]


# ---------- Renderização de cada pergunta ----------


def _render_period_prompt(to: str) -> None:
    # Primeiro passo do fluxo — nunca tem botão de voltar.
    flow_utils.render_buttons_with_back(
        to,
        "De qual período?",
        [
            {"id": _CURRENT_MONTH_CHOICE, "title": "Mês atual"},
            {"id": _LAST_MONTH_CHOICE, "title": "Mês passado"},
            {"id": _CUSTOM_MONTH_CHOICE, "title": "Escolher mês"},
        ],
        has_history=False,
    )


def _render_custom_period_prompt(to: str) -> None:
    whatsapp_client.send_text(to, "Digite o mês no formato MM/AAAA, ex.: 07/2026")


def _render_mode_prompt(to: str) -> None:
    flow_utils.render_buttons_with_back(
        to,
        "Ver gastos de uma categoria específica, ou o total por categoria do mês?",
        [
            {"id": _SPECIFIC_CATEGORY_CHOICE, "title": "Categoria específica"},
            {"id": _TOTAL_MONTH_CHOICE, "title": "Total do mês"},
        ],
        has_history=True,
    )


def _render_category_prompt(user, to: str) -> None:
    rows = _expense_category_rows(user)
    flow_utils.render_list_with_back(
        to, "Qual categoria?", "Escolher", rows, "Categorias", has_history=True
    )


_RENDERERS = {
    "awaiting_period": lambda user, context: _render_period_prompt(to_wa_id(user.phone_number)),
    "awaiting_custom_period": lambda user, context: _render_custom_period_prompt(
        to_wa_id(user.phone_number)
    ),
    "awaiting_mode": lambda user, context: _render_mode_prompt(to_wa_id(user.phone_number)),
    "awaiting_category": lambda user, context: _render_category_prompt(
        user, to_wa_id(user.phone_number)
    ),
}


# ---------- Processamento de cada passo ----------


def _send_breakdown(to: str, month: str, breakdown: list[dict]) -> None:
    if not breakdown or all(item["total"] == 0 for item in breakdown):
        whatsapp_client.send_text(to, f"Nenhum gasto registrado em {_month_label(month)}.")
        return
    lines = [f"Gastos de {_month_label(month)} por categoria:", ""]
    for item in breakdown:
        if item["total"] == 0:
            continue
        lines.append(f"• {item['category_name']}: {money(item['total'])}")
    whatsapp_client.send_text(to, "\n".join(lines))


def _handle_awaiting_period(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip().lower()

    if choice == _CURRENT_MONTH_CHOICE:
        context = {**context, "month": _current_month_str()}
        _render_mode_prompt(to)
        return "awaiting_mode", context

    if choice == _LAST_MONTH_CHOICE:
        context = {**context, "month": _last_month_str()}
        _render_mode_prompt(to)
        return "awaiting_mode", context

    if choice == _CUSTOM_MONTH_CHOICE:
        _render_custom_period_prompt(to)
        return "awaiting_custom_period", context

    whatsapp_client.send_text(to, "Não entendi. Escolhe uma das opções.")
    return "awaiting_period", context


def _handle_awaiting_custom_period(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    month = _parse_custom_month(event.get("text") or "")
    if month is None:
        whatsapp_client.send_text(
            to, "Formato inválido. Digite o mês como MM/AAAA, ex.: 07/2026."
        )
        return "awaiting_custom_period", context

    context = {**context, "month": month}
    _render_mode_prompt(to)
    return "awaiting_mode", context


def _handle_awaiting_mode(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip().lower()
    month = context["month"]

    if choice == _TOTAL_MONTH_CHOICE:
        breakdown = report_service.category_breakdown(user.id, month, type="expense")
        _send_breakdown(to, month, breakdown)
        return None, {}

    if choice == _SPECIFIC_CATEGORY_CHOICE:
        _render_category_prompt(user, to)
        return "awaiting_category", context

    whatsapp_client.send_text(to, "Não entendi. Escolhe uma das opções.")
    return "awaiting_mode", context


def _handle_awaiting_category(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()
    month = context["month"]

    try:
        category = category_service.get_category(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Categoria inválida. Escolhe uma opção da lista.")
        return "awaiting_category", context
    if category.type != "expense":
        whatsapp_client.send_text(to, "Categoria inválida. Escolhe uma opção da lista.")
        return "awaiting_category", context

    breakdown = report_service.category_breakdown(user.id, month, type="expense")
    total = next(
        (item["total"] for item in breakdown if item["category_id"] == category.id),
        0,
    )
    whatsapp_client.send_text(
        to, f"{category.name} em {_month_label(month)}: {money(total)}"
    )
    return None, {}


_STEP_HANDLERS = {
    "awaiting_period": _handle_awaiting_period,
    "awaiting_custom_period": _handle_awaiting_custom_period,
    "awaiting_mode": _handle_awaiting_mode,
    "awaiting_category": _handle_awaiting_category,
}
