"""Rotas do webhook do WhatsApp (Meta Cloud API).

GET: verificação única feita pela Meta ao configurar o webhook no painel.
POST: recebe eventos de mensagem/status. Valida a assinatura, ignora eventos
de status (delivered/read/failed — não são mensagem recebida), processa
mensagens de forma síncrona (sem fila/worker nesta stack) e sempre responde
200 no final — mesmo em erro, pra Meta não ficar reentregando em loop; o
erro fica logado pra investigação.
"""

import logging

from flask import Blueprint, current_app, request

from bot import auth, conversation
from bot import handlers  # noqa: F401  (garante que os fluxos se registrem)

logger = logging.getLogger(__name__)

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
    signature = request.headers.get("X-Hub-Signature-256")
    if not auth.verify_signature(request.get_data(), signature):
        logger.warning("Webhook do bot recebeu payload com assinatura inválida.")
        return "", 403

    payload = request.get_json(silent=True) or {}
    try:
        conversation.handle_incoming_payload(payload)
    except Exception:
        logger.exception("Erro processando payload do webhook do bot.")

    return "", 200
