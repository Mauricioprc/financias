"""Máquina de estados da conversa — orquestra o parsing do payload da Meta,
idempotência, resolução de usuário e roteamento pro handler do fluxo ativo
(ou pro menu raiz, se não houver fluxo em andamento).

Cada módulo em bot/handlers/ que representa um fluxo multi-etapa implementa:

    def start(user) -> tuple[str, dict]:
        Envia a primeira pergunta do fluxo, retorna (step_inicial, context_inicial).

    def handle_step(user, step, context, event) -> tuple[str | None, dict]:
        Processa a resposta do passo atual, envia a próxima pergunta (ou a
        confirmação final). Retorna (proximo_step, novo_context) — proximo_step
        = None significa "fluxo terminou", o estado é limpo automaticamente.

Fluxos "diretos" (sem passo-a-passo, ex. "ver saldo") só precisam de uma
função `handle(user)` que responde na hora, sem tocar em BotConversationState.
"""

import logging

from app.extensions import db
from app.models.bot_conversation_state import BotConversationState
from app.models.bot_processed_message import BotProcessedMessage
from bot import auth, whatsapp_client
from bot.menus import DIRECT_FLOWS, EXIT_KEYWORDS, flow_by_id, root_menu_sections, root_menu_text

logger = logging.getLogger(__name__)


def to_wa_id(phone_number: str) -> str:
    """+5511999999999 -> 5511999999999 (formato que a API de envio espera)."""
    return phone_number.lstrip("+")


# ---------- Parsing do payload cru da Meta ----------


def extract_events(payload: dict) -> list[dict]:
    """Normaliza o payload do webhook em uma lista de eventos de mensagem
    recebida (ignora eventos de status como 'delivered'/'read'/'failed' —
    esses não têm 'messages' no value, só 'statuses')."""
    events = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                events.append(_normalize_message(message))
    return events


def _normalize_message(message: dict) -> dict:
    event = {
        "message_id": message.get("id"),
        "wa_id": message.get("from"),
        "type": message.get("type"),
        "text": None,
        "reply_id": None,
    }
    if message.get("type") == "text":
        event["text"] = message.get("text", {}).get("body", "")
    elif message.get("type") == "interactive":
        interactive = message.get("interactive", {})
        if interactive.get("type") == "button_reply":
            event["reply_id"] = interactive["button_reply"]["id"]
            event["text"] = interactive["button_reply"]["title"]
        elif interactive.get("type") == "list_reply":
            event["reply_id"] = interactive["list_reply"]["id"]
            event["text"] = interactive["list_reply"]["title"]
    return event


# ---------- Idempotência ----------


def already_processed(message_id: str) -> bool:
    return db.session.get(BotProcessedMessage, message_id) is not None


def mark_processed(message_id: str) -> None:
    db.session.add(BotProcessedMessage(message_id=message_id))
    db.session.commit()


# ---------- Estado da conversa ----------


def get_state(user_id: int) -> BotConversationState | None:
    return db.session.query(BotConversationState).filter_by(user_id=user_id).first()


def set_state(user_id: int, flow: str, step: str, context: dict) -> None:
    state = get_state(user_id)
    if state is None:
        state = BotConversationState(user_id=user_id)
        db.session.add(state)
    state.flow = flow
    state.step = step
    state.context_json = context
    db.session.commit()


def clear_state(user_id: int) -> None:
    state = get_state(user_id)
    if state is not None:
        db.session.delete(state)
        db.session.commit()


# ---------- Envio do menu raiz ----------


def send_root_menu(user) -> None:
    to = to_wa_id(user.phone_number)
    try:
        whatsapp_client.send_list(to, root_menu_text(), "Escolher", root_menu_sections())
    except whatsapp_client.WhatsAppApiError:
        # Lista interativa pode falhar em alguns clientes/números de teste —
        # cai pra texto simples, que sempre funciona.
        whatsapp_client.send_text(to, root_menu_text())


# ---------- Registro de handlers (populado por bot/handlers/__init__.py) ----------

FLOW_HANDLERS: dict[str, object] = {}
DIRECT_HANDLERS: dict[str, object] = {}


def register_flow(name: str, module: object) -> None:
    FLOW_HANDLERS[name] = module


def register_direct(name: str, handle_fn) -> None:
    DIRECT_HANDLERS[name] = handle_fn


# ---------- Orquestração principal ----------


def handle_incoming_payload(payload: dict) -> None:
    for event in extract_events(payload):
        _handle_event(event)


def _handle_event(event: dict) -> None:
    message_id = event.get("message_id")
    if message_id and already_processed(message_id):
        logger.info("Mensagem %s já processada, ignorando (reentrega).", message_id)
        return

    user = auth.resolve_user_by_phone(event["wa_id"])
    if user is None:
        whatsapp_client.send_text(
            event["wa_id"],
            "Esse número ainda não está vinculado a uma conta MR Gestão. "
            "Acesse o dashboard, vá em Perfil e cadastre este número.",
        )
        if message_id:
            mark_processed(message_id)
        return

    text_normalized = (event.get("text") or "").strip().lower()

    if text_normalized in EXIT_KEYWORDS:
        clear_state(user.id)
        send_root_menu(user)
        if message_id:
            mark_processed(message_id)
        return

    state = get_state(user.id)

    if state is None:
        _handle_root_selection(user, event)
    else:
        _handle_flow_step(user, state, event)

    if message_id:
        mark_processed(message_id)


def _handle_root_selection(user, event: dict) -> None:
    selector = event.get("reply_id") or (event.get("text") or "").strip()
    flow = flow_by_id(selector)

    if flow is None:
        send_root_menu(user)
        return

    if flow in DIRECT_FLOWS:
        handler = DIRECT_HANDLERS.get(flow)
        if handler is None:
            whatsapp_client.send_text(to_wa_id(user.phone_number), "Ainda não disponível.")
            return
        handler(user)
        return

    module = FLOW_HANDLERS.get(flow)
    if module is None:
        whatsapp_client.send_text(
            to_wa_id(user.phone_number),
            "Esse recurso ainda não está disponível pelo bot. Em breve! "
            "Digite 'menu' para voltar.",
        )
        return

    step, context = module.start(user)
    set_state(user.id, flow, step, context)


def _handle_flow_step(user, state: BotConversationState, event: dict) -> None:
    module = FLOW_HANDLERS.get(state.flow)
    if module is None:
        # Estado órfão (flow removido/renomeado) — não deveria acontecer, mas
        # não trava o usuário: limpa e volta pro menu.
        clear_state(user.id)
        send_root_menu(user)
        return

    next_step, new_context = module.handle_step(user, state.step, state.context_json, event)
    if next_step is None:
        clear_state(user.id)
    else:
        set_state(user.id, state.flow, next_step, new_context)
