from decimal import Decimal

from sqlalchemy import CHAR, Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TimestampMixin


class Account(db.Model, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    initial_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="BRL")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
