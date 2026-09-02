"""Registra cada fluxo/handler na máquina de estados (bot/conversation.py).

Fase D2: 'new_transaction' (multi-etapa) + 'balance'/'monthly_summary'
(diretos). Fase D3: os demais itens do menu raiz — 'transfers' como
multi-etapa (mesmo padrão de new_transaction) e 'accounts'/'goals'/
'investments'/'credit_cards'/'recurring' como diretos, só leitura por
enquanto (criar/editar essas entidades continua exclusivo do dashboard).
"""

from bot import conversation
from bot.handlers import (
    accounts,
    credit_cards,
    goal_contribution,
    goals,
    insights,
    invoice_action,
    investments,
    recurring,
    reports,
    transactions,
    transfers,
)

conversation.register_flow("new_transaction", transactions)
conversation.register_flow("transfers", transfers)
# Fase C do bot: ações de escrita novas (multi-etapa, mesmo padrão de
# transfers.py) — contribuir pra meta e pagar/fechar fatura.
conversation.register_flow("goal_contribution", goal_contribution)
conversation.register_flow("invoice_action", invoice_action)
conversation.register_direct("balance", reports.handle_balance)
conversation.register_direct("monthly_summary", reports.handle_monthly_summary)
conversation.register_direct("accounts", accounts.handle_accounts)
conversation.register_direct("goals", goals.handle_goals)
conversation.register_direct("investments", investments.handle_investments)
conversation.register_direct("credit_cards", credit_cards.handle_credit_cards)
conversation.register_direct("recurring", recurring.handle_recurring)
# Fase B do bot: expõe o backend de insights que já existe e já é usado
# pelo dashboard web — sem lógica de cálculo nova, só handlers formatando
# o retorno dos services (ver bot/handlers/insights.py).
conversation.register_direct("budget_progress", insights.handle_budget_progress)
conversation.register_direct("balance_forecast", insights.handle_balance_forecast)
conversation.register_direct("upcoming_bills", insights.handle_upcoming_bills)
conversation.register_direct("net_worth", insights.handle_net_worth)
