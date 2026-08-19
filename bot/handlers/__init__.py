"""Registra cada fluxo/handler na máquina de estados (bot/conversation.py).

Fase D2: 'new_transaction' (multi-etapa) + 'balance'/'monthly_summary'
(diretos). Os demais itens do menu raiz (contas, cartões, metas,
investimentos, recorrências, transferências) ficam para a Fase D3 — seguem
não registrados aqui, então respondem com a mensagem de 'em breve'.
"""

from bot import conversation
from bot.handlers import reports, transactions

conversation.register_flow("new_transaction", transactions)
conversation.register_direct("balance", reports.handle_balance)
conversation.register_direct("monthly_summary", reports.handle_monthly_summary)
