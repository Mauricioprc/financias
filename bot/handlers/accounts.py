"""'Contas' — direto, sem passo-a-passo. Complementa 'Ver saldo' (que só
soma os saldos) com mais detalhe por conta: tipo e se está arquivada."""

from app.services import account_service
from bot import whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money

_TYPE_LABELS = {
    "checking": "Conta corrente",
    "savings": "Poupança",
    "wallet": "Carteira",
    "other": "Outra",
}


def handle_accounts(user) -> None:
    accounts = account_service.list_accounts(user.id)
    to = to_wa_id(user.phone_number)

    if not accounts:
        whatsapp_client.send_text(to, "Você ainda não tem nenhuma conta cadastrada.")
        return

    lines = ["Suas contas:", ""]
    for account in accounts:
        type_label = _TYPE_LABELS.get(account.type, account.type)
        archived = " (arquivada)" if account.is_archived else ""
        lines.append(f"• {account.name}{archived} — {type_label}: {money(account.current_balance)}")

    whatsapp_client.send_text(to, "\n".join(lines))
