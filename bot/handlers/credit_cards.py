"""'Cartões' — direto, só leitura. Mostra cada cartão com a fatura aberta
atual (se houver) — criar cartão/lançar no cartão fica pra outra fase."""

from app.services import credit_card_service, invoice_service
from bot import whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money


def handle_credit_cards(user) -> None:
    cards = credit_card_service.list_credit_cards(user.id)
    to = to_wa_id(user.phone_number)

    if not cards:
        whatsapp_client.send_text(to, "Você ainda não tem nenhum cartão cadastrado.")
        return

    lines = ["Seus cartões:", ""]
    for card in cards:
        archived = " (arquivado)" if card.is_archived else ""
        lines.append(f"• {card.name}{archived} — limite {money(card.credit_limit)}")

        open_invoices = invoice_service.list_invoices(
            user.id, credit_card_id=card.id, status="open"
        )
        if open_invoices:
            invoice = open_invoices[0]
            lines.append(
                f"   Fatura aberta: {money(invoice.total_amount)} "
                f"(vence {invoice.due_date.strftime('%d/%m')})"
            )
        else:
            lines.append("   Sem fatura aberta no momento.")

    whatsapp_client.send_text(to, "\n".join(lines))
