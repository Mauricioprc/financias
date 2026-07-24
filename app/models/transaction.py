import uuid
from datetime import date as date_
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TimestampMixin


class Transaction(db.Model, TimestampMixin):
    """Receita ou despesa.

    credit_card_id, invoice_id e recurring_id fazem parte do DER completo
    (ver ARCHITECTURE.md) mas só serão adicionados quando as tabelas
    credit_cards, invoices e recurring_transactions existirem (fases futuras).
    """

    __tablename__ = "transactions"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_transaction_amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    date: Mapped[date_] = mapped_column(nullable=False, index=True)
    is_paid: Mapped[bool] = mapped_column(nullable=False, default=True)
    installment_number: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    installment_total: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    purchase_group_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
