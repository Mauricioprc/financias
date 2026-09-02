from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TimestampMixin


class Budget(db.Model, TimestampMixin):
    """Limite mensal recorrente por categoria — não é "orçamento de
    setembro/2026", é um valor que vale todo mês até o usuário mudar (mesma
    filosofia de RecurringTransaction: um registro só, sem instância por
    mês)."""

    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("monthly_limit > 0", name="ck_budget_monthly_limit_positive"),
        UniqueConstraint("user_id", "category_id", name="uq_budget_user_category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"), nullable=False, index=True
    )
    monthly_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
