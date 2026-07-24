from datetime import date as date_
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TimestampMixin


class Transfer(db.Model, TimestampMixin):
    """Movimentação de saldo entre duas contas do mesmo usuário.

    Não gera linhas em transactions e não entra em relatórios de
    receita/despesa — apenas afeta current_balance das duas contas.
    """

    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transfer_amount_positive"),
        CheckConstraint("from_account_id <> to_account_id", name="ck_transfer_distinct_accounts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    from_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"), nullable=False, index=True
    )
    to_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    date: Mapped[date_] = mapped_column(nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
