from datetime import date as date_
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TimestampMixin


class RecurringTransaction(db.Model, TimestampMixin):
    """Origem de assinaturas, salário e parcelas fixas.

    O recurring_service gera as transactions correspondentes sob demanda
    (verificação lazy), usando last_generated para não duplicar ocorrências.
    """

    __tablename__ = "recurring_transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_recurring_transaction_amount_positive"),
        CheckConstraint(
            "day_of_month IS NULL OR day_of_month BETWEEN 1 AND 31",
            name="ck_recurring_transaction_day_of_month",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    day_of_month: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    start_date: Mapped[date_] = mapped_column(nullable=False)
    end_date: Mapped[date_ | None] = mapped_column(nullable=True)
    last_generated: Mapped[date_ | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
