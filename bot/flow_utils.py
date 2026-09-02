"""Utilitários compartilhados entre fluxos multi-etapa do bot: a keyword
'voltar' (+ botão "◀️ Voltar" tocável) e o histórico de passos que ela
exige. Extraído de bot/handlers/transactions.py (o primeiro fluxo
multi-etapa) quando bot/handlers/transfers.py precisou do mesmo
comportamento — ambos seguem a mesma convenção de
handle_step(user, step, context, event) descrita em bot/conversation.py."""

from bot import whatsapp_client

BACK_KEYWORD = "voltar"
BACK_ID = "back"
BACK_BUTTON = {"id": BACK_ID, "title": "◀️ Voltar"}
HISTORY_KEY = "_history"


def is_back(event: dict) -> bool:
    if event.get("reply_id") == BACK_ID:
        return True
    return (event.get("text") or "").strip().lower() == BACK_KEYWORD


def render_buttons_with_back(to: str, body: str, buttons: list[dict], has_history: bool) -> None:
    """send_buttons, com um botão extra "◀️ Voltar" quando `has_history`
    (nunca no primeiro passo de um fluxo — não há pra onde voltar). A API
    do WhatsApp permite no máximo 3 botões por mensagem; nenhum prompt
    hoje passa de 2, então sempre sobra espaço pro botão de voltar, mas o
    limite é respeitado mesmo assim (não adiciona se já tiver 3)."""
    if has_history and len(buttons) < 3:
        buttons = [*buttons, BACK_BUTTON]
    whatsapp_client.send_buttons(to, body, buttons)


def render_list_with_back(
    to: str,
    body: str,
    button_text: str,
    rows: list[dict],
    section_title: str,
    has_history: bool,
) -> None:
    """send_list_paginated, reservando 1 linha pra "◀️ Voltar" na ÚLTIMA
    página quando `has_history` — no máximo 9 itens reais por página
    nesse caso (o limite de 10 linhas por mensagem da Meta, já respeitado
    por send_list_paginated, continua valendo; aqui só sobra espaço pra
    mais uma linha). Sem histórico (primeiro passo de um fluxo), é
    idêntico a chamar send_list_paginated direto."""
    if not has_history:
        whatsapp_client.send_list_paginated(to, body, button_text, rows, section_title)
        return

    page_size = whatsapp_client.LIST_PAGE_SIZE - 1
    pages = [rows[i : i + page_size] for i in range(0, len(rows), page_size)] or [[]]
    total = len(pages)
    for index, page_rows in enumerate(pages, start=1):
        page_body = body if total == 1 else f"{body} ({index}/{total})"
        final_rows = [*page_rows, BACK_BUTTON] if index == total else page_rows
        whatsapp_client.send_list(
            to, page_body, button_text, [{"title": section_title, "rows": final_rows}]
        )


def split_history(context: dict) -> tuple[list, dict]:
    """Separa o histórico (`_history`) do resto do contexto — os handlers de
    cada passo não precisam saber que ele existe."""
    history = context.get(HISTORY_KEY, [])
    clean_context = {k: v for k, v in context.items() if k != HISTORY_KEY}
    return history, clean_context


def advance(
    history: list, step: str, next_step: str | None, context_before: dict, new_context: dict
) -> dict:
    """Contexto a devolver pro orquestrador depois que um passo processou a
    resposta — empilha `context_before` no histórico só se o passo realmente
    avançou (reprompt no mesmo passo não empilha nada)."""
    if next_step is not None and next_step != step:
        history = [*history, [step, context_before]]
    return {**new_context, HISTORY_KEY: history}


def handle_back(
    user, step: str, context: dict, history: list, renderers: dict, to: str, send_text
) -> tuple[str, dict]:
    if not history:
        send_text(to, "Você já está no primeiro passo.")
        renderers[step](user, context)
        return step, {**context, HISTORY_KEY: history}

    prev_step, prev_context = history[-1]
    remaining_history = history[:-1]
    renderers[prev_step](user, prev_context)
    return prev_step, {**prev_context, HISTORY_KEY: remaining_history}
