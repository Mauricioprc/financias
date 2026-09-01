"""'Investimentos' — direto, só leitura (mesmo raciocínio de goals.py: criar
investimento fica no dashboard por enquanto)."""

from app.services import investment_service
from bot import whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money

_TYPE_LABELS = {
    "fixed_income": "Renda fixa",
    "stock": "Ação",
    "fund": "Fundo",
    "crypto": "Cripto",
    "other": "Outro",
}


def handle_investments(user) -> None:
    investments = investment_service.list_investments(user.id)
    to = to_wa_id(user.phone_number)

    if not investments:
        whatsapp_client.send_text(to, "Você ainda não tem nenhum investimento cadastrado.")
        return

    lines = ["Seus investimentos:", ""]
    total_invested = investments[0].invested_amount * 0
    total_current = investments[0].current_amount * 0
    for inv in investments:
        type_label = _TYPE_LABELS.get(inv.type, inv.type)
        gain = inv.current_amount - inv.invested_amount
        gain_icon = "📈" if gain >= 0 else "📉"
        lines.append(
            f"• {inv.name} ({type_label}): {money(inv.current_amount)} "
            f"{gain_icon} {money(gain)}"
        )
        total_invested += inv.invested_amount
        total_current += inv.current_amount

    total_gain = total_current - total_invested
    lines += [
        "",
        f"Total investido: {money(total_invested)}",
        f"Valor atual: {money(total_current)}",
        f"Rentabilidade: {money(total_gain)}",
    ]
    whatsapp_client.send_text(to, "\n".join(lines))
