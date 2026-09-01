"""'Recorrências' — direto, só leitura (assinaturas, salário, parcelas
fixas). Criar/editar recorrência fica no dashboard por enquanto."""

from app.services import recurring_transaction_service
from bot import whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money

_FREQUENCY_LABELS = {
    "monthly": "Mensal",
    "weekly": "Semanal",
    "yearly": "Anual",
}


def handle_recurring(user) -> None:
    recurrences = recurring_transaction_service.list_recurring_transactions(user.id)
    to = to_wa_id(user.phone_number)

    active = [r for r in recurrences if r.is_active]
    if not active:
        whatsapp_client.send_text(to, "Você não tem nenhuma recorrência ativa no momento.")
        return

    lines = ["Suas recorrências ativas:", ""]
    for r in active:
        type_label = "Receita" if r.type == "income" else "Despesa"
        frequency_label = _FREQUENCY_LABELS.get(r.frequency, r.frequency)
        lines.append(f"• {r.description} ({type_label}, {frequency_label}): {money(r.amount)}")

    whatsapp_client.send_text(to, "\n".join(lines))
