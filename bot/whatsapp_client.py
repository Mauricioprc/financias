"""Wrapper fino da API de envio da Meta (WhatsApp Cloud API).

Não tem regra de negócio nenhuma aqui — só monta o payload certo pra cada
tipo de mensagem e chama a Graph API. Erros de rede/HTTP sobem como
exceção (WhatsAppApiError) pro chamador decidir o que fazer.
"""

import logging
import time

import requests
from flask import current_app

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v20.0"

# Só erro de rede/timeout é retentado — é transitório por natureza. Erro 4xx/5xx
# da própria API (token inválido, número fora da allowlist, payload malformado
# etc.) é definitivo: tentar de novo não muda o resultado, só atrasa a resposta
# ao usuário.
NETWORK_RETRY_ATTEMPTS = 3
NETWORK_RETRY_BACKOFF_SECONDS = 0.5


class WhatsAppApiError(Exception):
    def __init__(self, message: str, response_body: dict | None = None) -> None:
        super().__init__(message)
        self.response_body = response_body or {}


def _post(payload: dict) -> dict:
    phone_number_id = current_app.config["WHATSAPP_PHONE_NUMBER_ID"]
    access_token = current_app.config["WHATSAPP_ACCESS_TOKEN"]
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"

    resp = _post_with_retry(url, access_token, payload)
    body = resp.json() if resp.content else {}
    if not resp.ok:
        logger.warning("Falha ao enviar mensagem WhatsApp: %s", body)
        raise WhatsAppApiError(f"Erro {resp.status_code} da API do WhatsApp.", body)
    return body


def _post_with_retry(url: str, access_token: str, payload: dict) -> requests.Response:
    last_error: requests.exceptions.RequestException | None = None
    for attempt in range(1, NETWORK_RETRY_ATTEMPTS + 1):
        try:
            return requests.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json={"messaging_product": "whatsapp", **payload},
                timeout=10,
            )
        except requests.exceptions.RequestException as exc:
            last_error = exc
            if attempt == NETWORK_RETRY_ATTEMPTS:
                break
            logger.warning(
                "Falha de rede ao chamar a API do WhatsApp (tentativa %d/%d): %s",
                attempt,
                NETWORK_RETRY_ATTEMPTS,
                exc,
            )
            time.sleep(NETWORK_RETRY_BACKOFF_SECONDS * attempt)

    logger.warning(
        "Falha de rede ao chamar a API do WhatsApp após %d tentativas.", NETWORK_RETRY_ATTEMPTS
    )
    raise WhatsAppApiError(
        f"Erro de rede ao chamar a API do WhatsApp: {last_error}"
    ) from last_error


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


LIST_PAGE_SIZE = 10  # limite de linhas por mensagem de lista interativa da Meta


def send_list_paginated(
    to: str, body: str, button_text: str, rows: list[dict], section_title: str
) -> None:
    """Manda `rows` em quantas mensagens de lista forem necessárias — o
    WhatsApp permite no máximo `LIST_PAGE_SIZE` linhas por mensagem, então
    listas maiores viram várias mensagens em sequência, não um corte
    silencioso. Qualquer uma delas aceita a resposta do usuário, já que o
    `reply_id` identifica a linha escolhida independente de em qual mensagem
    ela apareceu."""
    pages = [rows[i : i + LIST_PAGE_SIZE] for i in range(0, len(rows), LIST_PAGE_SIZE)] or [[]]
    total = len(pages)
    for index, page_rows in enumerate(pages, start=1):
        page_body = body if total == 1 else f"{body} ({index}/{total})"
        send_list(to, page_body, button_text, [{"title": section_title, "rows": page_rows}])
