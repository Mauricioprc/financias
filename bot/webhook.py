"""Rotas do webhook do WhatsApp (Meta Cloud API).

Fase D1: só a verificação GET está implementada de verdade — é o suficiente
para configurar o webhook no painel da Meta e confirmar que ele está
acessível. O POST responde 200 imediatamente (Meta espera resposta rápida —
ver ARCHITECTURE.md "Riscos conhecidos") mas ainda não processa nada; isso
entra na Fase D2 junto com a validação de assinatura (X-Hub-Signature-256,
usando WHATSAPP_APP_SECRET) e a resolução do usuário pelo telefone.
"""

from flask import Blueprint, current_app, request

bp = Blueprint("bot_webhook", __name__)


@bp.route("/webhook", methods=["GET"])
def verify_webhook():
    """Confirmação única feita pela Meta ao configurar o webhook no painel:
    ela manda esses três query params e espera o `hub.challenge` de volta,
    em texto puro, só se o `hub.verify_token` bater com o nosso."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge", "")

    expected_token = current_app.config["WHATSAPP_VERIFY_TOKEN"]
    if mode == "subscribe" and expected_token and token == expected_token:
        return challenge, 200

    return "Token de verificação inválido.", 403


@bp.route("/webhook", methods=["POST"])
def receive_webhook():
    """Recebe eventos de mensagem da Meta. Responde 200 de imediato — a
    lógica de negócio (idempotência via BotProcessedMessage, resolução de
    usuário, máquina de estados, chamada aos services) chega na Fase D2."""
    # TODO (Fase D2): validar assinatura X-Hub-Signature-256 com
    # WHATSAPP_APP_SECRET antes de processar qualquer coisa do payload.
    # TODO (temporário, diagnóstico): remover depois de confirmar entrega.
    current_app.logger.warning("bot webhook payload: %s", request.get_json(silent=True))
    return "", 200
