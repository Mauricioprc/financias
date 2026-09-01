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
    goals,
    investments,
    recurring,
    reports,
    transactions,
    transfers,
)

conversation.register_flow("new_transaction", transactions)
conversation.register_flow("transfers", transfers)
conversation.register_direct("balance", reports.handle_balance)
conversation.register_direct("monthly_summary", reports.handle_monthly_summary)
conversation.register_direct("accounts", accounts.handle_accounts)
conversation.register_direct("goals", goals.handle_goals)
conversation.register_direct("investments", investments.handle_investments)
conversation.register_direct("credit_cards", credit_cards.handle_credit_cards)
conversation.register_direct("recurring", recurring.handle_recurring)
