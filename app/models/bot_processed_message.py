from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import utcnow


class BotProcessedMessage(db.Model):
    """Registro de idempotência para mensagens recebidas do webhook do WhatsApp.

    A Meta reentrega mensagens quando o webhook não responde 200 a tempo
    (risco documentado em ARCHITECTURE.md, seção "Riscos conhecidos"). Antes
    de processar qualquer mensagem, o handler verifica se `message_id` já
    está aqui; se sim, responde 200 e ignora — evita processar a mesma
    mensagem (e, por exemplo, lançar a mesma transação) duas vezes.

    Sem TimestampMixin de propósito: só interessa quando foi processada, não
    quando foi atualizada (nunca é atualizada). Registros com mais de ~7 dias
    podem ser limpos periodicamente — não é crítico reter isso por muito
    tempo.
    """

    __tablename__ = "bot_processed_messages"

    message_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
