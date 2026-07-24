from datetime import date as date_
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TimestampMixin


class Invoice(db.Model, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint(
            "credit_card_id", "reference_month", name="uq_invoice_card_reference_month"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    credit_card_id: Mapped[int] = mapped_column(
        ForeignKey("credit_cards.id"), nullable=False, index=True
    )
    reference_month: Mapped[date_] = mapped_column(Date, nullable=False)
    closing_date: Mapped[date_] = mapped_column(Date, nullable=False)
    due_date: Mapped[date_] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
