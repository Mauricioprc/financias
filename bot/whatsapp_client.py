"""Wrapper fino da API de envio da Meta (WhatsApp Cloud API).

Não tem regra de negócio nenhuma aqui — só monta o payload certo pra cada
tipo de mensagem e chama a Graph API. Erros de rede/HTTP sobem como
exceção (WhatsAppApiError) pro chamador decidir o que fazer.
"""

import logging

import requests
from flask import current_app

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v20.0"


class WhatsAppApiError(Exception):
    def __init__(self, message: str, response_body: dict | None = None) -> None:
        super().__init__(message)
        self.response_body = response_body or {}


def _post(payload: dict) -> dict:
    phone_number_id = current_app.config["WHATSAPP_PHONE_NUMBER_ID"]
    access_token = current_app.config["WHATSAPP_ACCESS_TOKEN"]
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"

    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        json={"messaging_product": "whatsapp", **payload},
        timeout=10,
    )
    body = resp.json() if resp.content else {}
    if not resp.ok:
        logger.warning("Falha ao enviar mensagem WhatsApp: %s", body)
        raise WhatsAppApiError(f"Erro {resp.status_code} da API do WhatsApp.", body)
    return body


def send_text(to: str, body: str) -> dict:
    """Mensagem de texto simples."""
    return _post({"to": to, "type": "text", "text": {"body": body}})


def send_buttons(to: str, body: str, buttons: list[dict]) -> dict:
    """Até 3 botões de resposta rápida. `buttons` = [{"id": "...", "title": "..."}]."""
    if len(buttons) > 3:
        raise ValueError("WhatsApp permite no máximo 3 botões por mensagem.")
    return _post(
        {
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                        for b in buttons
                    ]
                },
            },
        }
    )


def send_list(to: str, body: str, button_text: str, sections: list[dict]) -> dict:
    """Lista interativa nativa (até 10 opções no total). `sections` = [{"title": "...",
    "rows": [{"id": "...", "title": "...", "description": "..."}]}]."""
    return _post(
        {
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body},
                "action": {"button": button_text, "sections": sections},
            },
        }
    )
