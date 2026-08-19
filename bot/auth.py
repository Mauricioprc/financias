"""Autenticação do lado do bot (ver ARCHITECTURE.md seção 3.2):

1. Verificação do webhook (GET) — feita em bot/webhook.py, token simples.
2. Autenticação das mensagens recebidas (POST) — a Meta assina o corpo da
   requisição com HMAC-SHA256 usando o App Secret; validamos aqui pra ter
   certeza de que quem está chamando o webhook é realmente a Meta.
3. Resolução de usuário — extrai o telefone de quem mandou a mensagem e
   busca o User com esse phone_number. Se não achar, não tenta adivinhar
   nem criar usuário novo.
"""

import hashlib
import hmac

from flask import current_app

from app.models.user import User


def verify_signature(payload_body: bytes, signature_header: str | None) -> bool:
    """`signature_header` é o valor do header X-Hub-Signature-256, formato
    'sha256=<hex>'. Retorna False se o header estiver ausente/malformado ou
    não bater com o HMAC calculado com WHATSAPP_APP_SECRET."""
    app_secret = current_app.config["WHATSAPP_APP_SECRET"]
    if not app_secret or not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(app_secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


def resolve_user_by_phone(wa_id: str) -> User | None:
    """`wa_id` vem da Meta sem o '+' (ex.: '5511999999999'). phone_number no
    nosso banco é E.164 com '+' (ex.: '+5511999999999'), então normalizamos
    antes de buscar."""
    from app.extensions import db

    phone_number = wa_id if wa_id.startswith("+") else f"+{wa_id}"
    return db.session.query(User).filter_by(phone_number=phone_number).first()
