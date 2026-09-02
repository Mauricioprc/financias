from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TimestampMixin


class CategorySuggestionPattern(db.Model, TimestampMixin):
    """Aprendizado por padrão description -> category, não uma "regra" que
    o usuário cadastra manualmente — é só contagem de quantas vezes uma
    descrição normalizada foi lançada numa certa categoria, sem nenhum
    machine learning envolvido. Ver
    `app/services/category_suggestion_service.py` (normalize_description,
    record_pattern, suggest_category)."""

    __tablename__ = "category_suggestion_patterns"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "normalized_description",
            "category_id",
            name="uq_category_suggestion_user_description_category",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    normalized_description: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"), nullable=False, index=True
    )
    match_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
