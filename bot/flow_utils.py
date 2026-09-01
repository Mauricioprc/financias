"""Utilitários compartilhados entre fluxos multi-etapa do bot: a keyword
'voltar' e o histórico de passos que ela exige. Extraído de
bot/handlers/transactions.py (o primeiro fluxo multi-etapa) quando
bot/handlers/transfers.py precisou do mesmo comportamento — ambos seguem a
mesma convenção de handle_step(user, step, context, event) descrita em
bot/conversation.py."""

BACK_KEYWORD = "voltar"
HISTORY_KEY = "_history"


def is_back(event: dict) -> bool:
    return (event.get("text") or "").strip().lower() == BACK_KEYWORD


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
