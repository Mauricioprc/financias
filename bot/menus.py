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


def root_menu_sections() -> list[dict]:
    return [
        {
            "title": "MR Gestão",
            "rows": [
                {"id": item["id"], "title": item["label"]} for item in ROOT_MENU_ITEMS
            ],
        }
    ]
