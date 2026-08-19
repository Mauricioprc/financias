"""'Ver saldo' e 'Resumo do mês' — sem passo-a-passo, respondem na hora.
Reaproveita account_service e o report_service da Fase C (mesmo cálculo que
a tela de Relatórios do dashboard usa)."""

from datetime import date

from app.services import account_service, report_service
from bot import whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money


def handle_balance(user) -> None:
    accounts = account_service.list_accounts(user.id)
    to = to_wa_id(user.phone_number)

    if not accounts:
        whatsapp_client.send_text(to, "Você ainda não tem nenhuma conta cadastrada.")
        return

    total = sum((a.current_balance for a in accounts), start=accounts[0].current_balance * 0)
    lines = [f"Saldo total: {money(total)}", ""]
    lines += [f"• {a.name}: {money(a.current_balance)}" for a in accounts]
    whatsapp_client.send_text(to, "\n".join(lines))


def handle_monthly_summary(user) -> None:
    month_label = date.today().strftime("%m/%Y")
    summary = report_service.income_vs_expense_by_month(user.id, months=1)[0]
    income = summary["income"]
    expense = summary["expense"]
    net = income - expense

    balance_icon = "✅" if net >= 0 else "⚠️"
    text = (
        f"Resumo de {month_label}\n\n"
        f"Receitas: {money(income)}\n"
        f"Despesas: {money(expense)}\n"
        f"{balance_icon} Saldo do mês: {money(net)}"
    )
    whatsapp_client.send_text(to_wa_id(user.phone_number), text)
