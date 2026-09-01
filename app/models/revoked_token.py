from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TimestampMixin


class RevokedToken(db.Model, TimestampMixin):
    """Blocklist de JWTs revogados (logout). Checada em todo request via
    `@jwt.token_in_blocklist_loader` (app/extensions.py) — se o `jti` do
    token estiver aqui, o request é rejeitado com 401 mesmo que o token
    ainda não tenha expirado."""

    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    token_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "access" | "refresh"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
