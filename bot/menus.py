"""Definição declarativa do menu raiz e dos fluxos disponíveis.

Cada item do menu raiz tem um `id` (usado como id da linha na lista
interativa do WhatsApp e como texto alternativo pra quem digitar o número),
um rótulo, e o nome do fluxo que ele dispara em bot/handlers/. Um fluxo sem
handler registrado (bot/handlers/__init__.py) responde com uma mensagem de
"em breve" automaticamente — assim a lista já existe inteira desde já, mesmo
antes de todo item ter handler.
"""

ROOT_MENU_ITEMS = [
    {"id": "1", "flow": "new_transaction", "label": "💸 Lançar transação"},
    {"id": "2", "flow": "balance", "label": "💰 Ver saldo"},
    {"id": "3", "flow": "monthly_summary", "label": "📊 Resumo do mês"},
    {"id": "4", "flow": "accounts", "label": "🏦 Contas"},
    {"id": "5", "flow": "credit_cards", "label": "💳 Cartões"},
    {"id": "6", "flow": "goals", "label": "🎯 Metas"},
    {"id": "7", "flow": "investments", "label": "📈 Investimentos"},
    {"id": "8", "flow": "recurring", "label": "🔁 Recorrências"},
    {"id": "9", "flow": "transfers", "label": "🔀 Transferências"},
    {"id": "10", "flow": "budget_progress", "label": "📋 Orçamentos"},
    {"id": "11", "flow": "balance_forecast", "label": "🔮 Previsão de saldo"},
    {"id": "12", "flow": "upcoming_bills", "label": "🗓️ Próximos vencimentos"},
    {"id": "13", "flow": "net_worth", "label": "💎 Patrimônio"},
    {"id": "14", "flow": "goal_contribution", "label": "🎯 Contribuir pra meta"},
    {"id": "15", "flow": "invoice_action", "label": "💳 Pagar/fechar fatura"},
    {"id": "16", "flow": "spending_by_category", "label": "📂 Gastos por categoria"},
    {"id": "17", "flow": "recurring_category", "label": "🏷️ Categorizar assinatura"},
    {"id": "18", "flow": "invoice_view", "label": "🧾 Ver fatura"},
]

# Fluxos sem passo-a-passo — respondem na hora e não usam BotConversationState.
DIRECT_FLOWS = {
    "balance",
    "monthly_summary",
    "accounts",
    "goals",
    "investments",
    "credit_cards",
    "recurring",
    "budget_progress",
    "balance_forecast",
    "upcoming_bills",
    "net_worth",
}

# Palavras-chave que abortam qualquer fluxo em qualquer ponto e voltam ao menu raiz.
EXIT_KEYWORDS = {"menu", "cancelar", "sair"}


def flow_by_id(item_id: str) -> str | None:
    for item in ROOT_MENU_ITEMS:
        if item["id"] == item_id:
            return item["flow"]
    return None


def root_menu_text() -> str:
    lines = ["O que você quer fazer? Responda com o número:"]
    lines += [f"{item['id']}. {item['label']}" for item in ROOT_MENU_ITEMS]
    return "\n".join(lines)


def root_menu_rows() -> list[dict]:
    """Linhas pra send_list_paginated — o menu raiz já passou de 10 itens, e
    o limite de 10 linhas por mensagem da API do WhatsApp exige paginação
    (bot/conversation.py::send_root_menu usa send_list_paginated com isso)."""
    return [{"id": item["id"], "title": item["label"]} for item in ROOT_MENU_ITEMS]
