from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TimestampMixin


class BotConversationState(db.Model, TimestampMixin):
    """Estado da conversa em andamento de um usuário com o bot do WhatsApp.

    O webhook da Meta é stateless (cada mensagem chega como evento isolado),
    então isso é o que permite saber "em que passo do fluxo" aquele usuário
    está (ex.: "Lançar despesa" pede valor, depois categoria, depois conta,
    em mensagens separadas).

    Convenção: só existe uma linha aqui enquanto o usuário está no meio de um
    fluxo. Sem linha = está no menu raiz. `flow`/`step` ficam nulos só no
    instante entre "linha criada" e "primeira pergunta respondida", nunca em
    repouso — em repouso a linha é apagada (ver bot/conversation.py, Fase D2).
    """

    __tablename__ = "bot_conversation_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    flow: Mapped[str | None] = mapped_column(String(50), nullable=True)
    step: Mapped[str | None] = mapped_column(String(50), nullable=True)
    context_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
