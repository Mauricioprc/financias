"""'Orçamentos', 'Previsão de saldo', 'Próximos vencimentos' e 'Patrimônio'
— diretos, só leitura. Reaproveita os services de insights que já existem
e já são usados pelo dashboard web (app/services/insights_service.py,
budget_service.py, net_worth_service.py, upcoming_bills_service.py) —
nenhum cálculo novo aqui, só formatação de texto."""

from app.services import (
    account_service,
    budget_service,
    insights_service,
    net_worth_service,
    upcoming_bills_service,
)
from bot import whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money

# Limite de itens antes de cortar a lista de vencimentos — o wrapper da
# API do WhatsApp (bot/whatsapp_client.py) não trata texto longo, então
# evitamos estourar o limite de caracteres de mensagem cortando aqui.
MAX_UPCOMING_BILLS_SHOWN = 15


def handle_budget_progress(user) -> None:
    to = to_wa_id(user.phone_number)
    progress = budget_service.get_budget_progress(user.id)

    if not progress:
        whatsapp_client.send_text(
            to,
            "Você ainda não tem orçamento cadastrado. Cadastre pelo dashboard, em Orçamentos.",
        )
        return

    lines = ["Orçamentos do mês:", ""]
    for item in progress:
        pct = item["pct_used"]
        if item["is_over_budget"]:
            icon = "⚠️ "
        elif pct >= 80:
            icon = "🟡 "
        else:
            icon = ""
        lines.append(
            f"{icon}{item['category_name']}: {money(item['current_month_total'])} de "
            f"{money(item['monthly_limit'])} ({pct:.0f}%)"
        )
    whatsapp_client.send_text(to, "\n".join(lines))


def handle_balance_forecast(user) -> None:
    to = to_wa_id(user.phone_number)
    active_accounts = [a for a in account_service.list_accounts(user.id) if not a.is_archived]

    if not active_accounts:
        whatsapp_client.send_text(to, "Você ainda não tem nenhuma conta cadastrada.")
        return

    lines = ["Previsão de saldo:", ""]
    for account in active_accounts:
        forecast = insights_service.forecast_account_balance(user.id, account.id)
        if forecast["days_remaining"] == 0:
            # Hoje já é o último dia do mês — não tem sentido mostrar uma
            # "previsão" pro mesmo dia, só o saldo atual mesmo.
            lines.append(f"• {account.name}: {money(forecast['current_balance'])}")
        else:
            lines.append(
                f"• {account.name}: {money(forecast['current_balance'])} agora → previsão de "
                f"{money(forecast['projected_end_of_month_balance'])} no fim do mês"
            )
    whatsapp_client.send_text(to, "\n".join(lines))


def handle_upcoming_bills(user) -> None:
    to = to_wa_id(user.phone_number)
    bills = upcoming_bills_service.list_upcoming_bills(user.id, days=30)

    if not bills:
        whatsapp_client.send_text(to, "Nenhuma conta prevista para os próximos 30 dias. 🎉")
        return

    truncated_count = max(0, len(bills) - MAX_UPCOMING_BILLS_SHOWN)
    shown = bills[:MAX_UPCOMING_BILLS_SHOWN]

    # Agrupa por data — mesma lógica simples de reduce por chave que
    # static/js/views/upcomingBills.js usa, só que virando texto em vez de
    # marcos numa linha do tempo. `shown` já vem ordenado por data (o
    # service devolve assim), então não precisa reordenar aqui.
    grouped: dict[str, list[dict]] = {}
    for bill in shown:
        key = bill["date"].strftime("%d/%m")
        grouped.setdefault(key, []).append(bill)

    lines = []
    for date_label, day_bills in grouped.items():
        lines.append(f"📅 {date_label}")
        for bill in day_bills:
            lines.append(f"  • {bill['label']} — {money(abs(bill['amount']))}")
        lines.append("")

    if truncated_count:
        lines.append(
            f"...e mais {truncated_count} vencimento(s) — veja a lista completa no dashboard."
        )

    whatsapp_client.send_text(to, "\n".join(lines).strip())


def handle_net_worth(user) -> None:
    to = to_wa_id(user.phone_number)
    data = net_worth_service.compute_net_worth_today(user.id)
    text = (
        f"💎 Patrimônio líquido: {money(data['net_worth'])}\n\n"
        f"Contas: {money(data['accounts_total'])}\n"
        f"Investimentos: {money(data['investments_total'])}\n"
        f"Faturas em aberto: -{money(data['unpaid_invoices_total'])}"
    )
    whatsapp_client.send_text(to, text)
