"""Fluxo 'Lançar transação' — o de maior uso, serve de padrão pros demais
fluxos (Fase D3). Cada passo mapeia 1:1 pros campos que
TransactionCreateSchema já exige/aceita — não inventa campo novo, só pede o
que o schema pede e usa default pro que é opcional (credit_card_id fica de
fora por enquanto, é opcional no schema)."""

from datetime import date
from decimal import Decimal

from app.services import account_service, category_service, transaction_service
from app.services.exceptions import ServiceError
from bot import whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money, parse_amount

DEFAULT_DESCRIPTION = "Transação via WhatsApp"


def start(user) -> tuple[str, dict]:
    to = to_wa_id(user.phone_number)
    whatsapp_client.send_buttons(
        to,
        "Vamos lançar uma transação. É receita ou despesa?",
        [
            {"id": "income", "title": "Receita"},
            {"id": "expense", "title": "Despesa"},
        ],
    )
    return "awaiting_type", {}


def handle_step(user, step: str, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    handler = _STEP_HANDLERS.get(step)
    if handler is None:
        whatsapp_client.send_text(to, "Algo deu errado nesse fluxo. Voltando ao menu.")
        return None, {}
    return handler(user, context, event)


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
    whatsapp_client.send_text(to, "Qual o valor? (ex.: 50 ou 50,00)")
    return "awaiting_amount", context


def _handle_awaiting_amount(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    amount = parse_amount(event.get("text") or "")
    if amount is None:
        whatsapp_client.send_text(to, "Valor inválido. Manda só o número, ex.: 50 ou 50,00.")
        return "awaiting_amount", context

    context = {**context, "amount": str(amount)}

    categories = [c for c in category_service.list_categories(user.id) if c.type == context["type"]]
    if not categories:
        return _ask_account(user, {**context, "category_id": None})

    rows = [{"id": str(c.id), "title": c.name} for c in categories[:9]]
    rows.append({"id": "none", "title": "Sem categoria"})
    whatsapp_client.send_list(to, "Qual categoria?", "Escolher", [{"title": "Categorias", "rows": rows}])
    return "awaiting_category", context


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


def _ask_account(user, context: dict) -> tuple[str, dict]:
    to = to_wa_id(user.phone_number)
    accounts = account_service.list_accounts(user.id)
    if not accounts:
        whatsapp_client.send_text(
            to, "Você não tem nenhuma conta cadastrada ainda — cadastre uma no dashboard primeiro."
        )
        return None, {}

    rows = [{"id": str(a.id), "title": a.name} for a in accounts[:10]]
    whatsapp_client.send_list(to, "Em qual conta?", "Escolher", [{"title": "Contas", "rows": rows}])
    return "awaiting_account", context


def _handle_awaiting_account(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    try:
        account = account_service.get_account(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Conta inválida. Escolhe uma opção da lista.")
        return "awaiting_account", context

    context = {**context, "account_id": account.id}
    whatsapp_client.send_text(to, "Descrição? (ou manda '-' para pular)")
    return "awaiting_description", context


def _handle_awaiting_description(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    raw = (event.get("text") or "").strip()
    description = DEFAULT_DESCRIPTION if raw == "-" or not raw else raw
    context = {**context, "description": description}

    type_label = "Receita" if context["type"] == "income" else "Despesa"
    category_label = "Sem categoria"
    if context.get("category_id"):
        try:
            category_label = category_service.get_category(user.id, context["category_id"]).name
        except ServiceError:
            pass
    account = account_service.get_account(user.id, context["account_id"])

    summary = (
        f"Confirma o lançamento?\n\n"
        f"{type_label}: {money(context['amount'])}\n"
        f"Categoria: {category_label}\n"
        f"Conta: {account.name}\n"
        f"Descrição: {description}"
    )
    whatsapp_client.send_buttons(
        to, summary, [{"id": "confirm", "title": "Confirmar"}, {"id": "cancel", "title": "Cancelar"}]
    )
    return "awaiting_confirmation", context


def _handle_awaiting_confirmation(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip().lower()

    if choice not in ("confirm", "confirmar"):
        whatsapp_client.send_text(to, "Lançamento cancelado.")
        return None, {}

    transaction_service.create_transaction(
        user_id=user.id,
        account_id=context["account_id"],
        category_id=context.get("category_id"),
        credit_card_id=None,
        type=context["type"],
        description=context["description"],
        amount=Decimal(context["amount"]),
        date=date.today(),
        is_paid=True,
        notes=None,
    )
    updated_account = account_service.get_account(user.id, context["account_id"])
    whatsapp_client.send_text(
        to,
        f"Lançado! Novo saldo de {updated_account.name}: {money(updated_account.current_balance)}",
    )
    return None, {}


_STEP_HANDLERS = {
    "awaiting_type": _handle_awaiting_type,
    "awaiting_amount": _handle_awaiting_amount,
    "awaiting_category": _handle_awaiting_category,
    "awaiting_account": _handle_awaiting_account,
    "awaiting_description": _handle_awaiting_description,
    "awaiting_confirmation": _handle_awaiting_confirmation,
}
