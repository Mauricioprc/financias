"""Fluxo 'Ver fatura' — multi-etapa, só consulta (diferente de
bot/handlers/invoice_action.py, que é pra AÇÃO — pagar ou fechar). Mostra
qualquer fatura, inclusive já paga. Mesmo padrão de voltar/histórico via
bot/flow_utils.py.

Passos: cartão -> fatura (qualquer status) -> detalhe (invoice_service.
get_invoice_detail, o mesmo usado pelo dashboard web em invoiceDetail.js
— nenhum cálculo novo aqui, só formatação). Sem passo de confirmação —
é só leitura, termina depois de mostrar o detalhe."""

from app.services import credit_card_service, invoice_service
from app.services.exceptions import ServiceError
from bot import flow_utils, whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money

_STATUS_LABELS = {"open": "aberta", "closed": "fechada", "paid": "paga"}

# Limite de transações mostradas antes de cortar — mesmo critério de
# bot/handlers/insights.py::handle_upcoming_bills, pra não estourar o
# limite de caracteres de mensagem do WhatsApp.
MAX_TRANSACTIONS_SHOWN = 20


def start(user) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    cards = _active_cards(user)
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


def _active_cards(user) -> list:
    return [c for c in credit_card_service.list_credit_cards(user.id) if not c.is_archived]


def _card_rows(user) -> list[dict]:
    return [{"id": str(c.id), "title": c.name} for c in _active_cards(user)]


def _invoice_rows(user, card_id: int) -> list[dict]:
    invoices = invoice_service.list_invoices(user.id, credit_card_id=card_id)
    return [
        {
            "id": str(inv.id),
            "title": f"Referência {inv.reference_month.strftime('%m/%Y')} — "
            f"{money(inv.total_amount)} ({_STATUS_LABELS[inv.status]})",
        }
        for inv in invoices
    ]


# ---------- Renderização de cada pergunta ----------


def _render_card_prompt(user, to: str) -> None:
    # Primeiro passo do fluxo — nunca tem botão de voltar.
    rows = _card_rows(user)
    flow_utils.render_list_with_back(
        to, "Ver fatura de qual cartão?", "Escolher", rows, "Cartões", has_history=False
    )


def _render_invoice_prompt(user, to: str, context: dict) -> None:
    rows = _invoice_rows(user, context["card_id"])
    flow_utils.render_list_with_back(
        to, "Qual fatura?", "Escolher", rows, "Faturas", has_history=True
    )


_RENDERERS = {
    "awaiting_card": lambda user, context: _render_card_prompt(user, to_wa_id(user.phone_number)),
    "awaiting_invoice": lambda user, context: _render_invoice_prompt(
        user, to_wa_id(user.phone_number), context
    ),
}


# ---------- Formatação do detalhe ----------


def _installment_suffix(tx) -> str:
    if tx.installment_number and tx.installment_total:
        return f" ({tx.installment_number}/{tx.installment_total})"
    return ""


def _format_detail(card_name: str, detail: dict) -> str:
    invoice = detail["invoice"]
    lines = [
        f"Fatura {invoice.reference_month.strftime('%m/%Y')} — {card_name}",
        f"Status: {_STATUS_LABELS[invoice.status]}",
        f"Total: {money(invoice.total_amount)}",
        f"Pago: {money(invoice.paid_amount)}",
        f"Resta: {money(detail['remaining'])}",
        f"Fecha: {invoice.closing_date.strftime('%d/%m/%Y')}",
        f"Vence: {invoice.due_date.strftime('%d/%m/%Y')}",
        "",
        "Por categoria:",
    ]
    for item in detail["category_summary"]:
        lines.append(f"• {item['category_name']}: {money(item['total_amount'])}")

    transactions = detail["transactions"]
    lines.append("")
    lines.append(f"Transações ({len(transactions)}):")
    shown = transactions[:MAX_TRANSACTIONS_SHOWN]
    for tx in shown:
        lines.append(f"• {tx.description} — {money(tx.amount)}{_installment_suffix(tx)}")
    truncated_count = len(transactions) - len(shown)
    if truncated_count > 0:
        lines.append(f"...e mais {truncated_count} — veja o detalhe completo no dashboard.")

    return "\n".join(lines)


# ---------- Processamento de cada passo ----------


def _handle_awaiting_card(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    try:
        card = credit_card_service.get_credit_card(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Cartão inválido. Escolhe uma opção da lista.")
        return "awaiting_card", context

    invoices = invoice_service.list_invoices(user.id, credit_card_id=card.id)
    if not invoices:
        whatsapp_client.send_text(to, f"{card.name} ainda não tem nenhuma fatura.")
        return None, {}

    context = {**context, "card_id": card.id, "card_name": card.name}
    _render_invoice_prompt(user, to, context)
    return "awaiting_invoice", context


def _handle_awaiting_invoice(user, context: dict, event: dict) -> tuple[str | None, dict]:
    to = to_wa_id(user.phone_number)
    choice = event.get("reply_id") or (event.get("text") or "").strip()

    try:
        detail = invoice_service.get_invoice_detail(user.id, int(choice))
    except (ValueError, ServiceError):
        whatsapp_client.send_text(to, "Fatura inválida. Escolhe uma opção da lista.")
        return "awaiting_invoice", context

    whatsapp_client.send_text(to, _format_detail(context["card_name"], detail))
    return None, {}


_STEP_HANDLERS = {
    "awaiting_card": _handle_awaiting_card,
    "awaiting_invoice": _handle_awaiting_invoice,
}
