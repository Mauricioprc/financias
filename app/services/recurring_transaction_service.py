import calendar
from datetime import date, datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models.account import Account
from app.models.category import Category
from app.models.recurring_transaction import RecurringTransaction
from app.models.transaction import Transaction
from app.services.exceptions import ConflictError, NotFoundError, ValidationError


def _signed_amount(type_: str, amount: Decimal) -> Decimal:
    return amount if type_ == "income" else -amount


def _clamped_date(year: int, month: int, day: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _add_months(year: int, month: int, months: int) -> tuple[int, int]:
    total = (year * 12) + (month - 1) + months
    return total // 12, (total % 12) + 1


def _get_owned_account(user_id: int, account_id: int) -> Account:
    account = db.session.query(Account).filter_by(id=account_id, user_id=user_id).first()
    if account is None:
        raise ValidationError("account_id inválido para este usuário.")
    return account


def _get_owned_category(user_id: int, category_id: int | None) -> Category | None:
    if category_id is None:
        return None
    category = db.session.query(Category).filter_by(id=category_id, user_id=user_id).first()
    if category is None:
        raise ValidationError("category_id inválido para este usuário.")
    return category


def _next_occurrence(recurring: RecurringTransaction, after: date | None) -> date:
    if after is None:
        return recurring.start_date

    if recurring.frequency == "weekly":
        return date.fromordinal(after.toordinal() + 7)

    if recurring.frequency == "monthly":
        year, month = _add_months(after.year, after.month, 1)
        day = recurring.day_of_month or recurring.start_date.day
        return _clamped_date(year, month, day)

    if recurring.frequency == "yearly":
        year = after.year + 1
        return _clamped_date(year, recurring.start_date.month, recurring.start_date.day)

    raise ValidationError(f"Frequência desconhecida: {recurring.frequency}")


def list_recurring_transactions(user_id: int) -> list[RecurringTransaction]:
    return (
        db.session.query(RecurringTransaction)
        .filter_by(user_id=user_id)
        .order_by(RecurringTransaction.created_at.desc())
        .all()
    )


def get_recurring_transaction(user_id: int, recurring_id: int) -> RecurringTransaction:
    recurring = (
        db.session.query(RecurringTransaction).filter_by(id=recurring_id, user_id=user_id).first()
    )
    if recurring is None:
        raise NotFoundError("Transação recorrente não encontrada.")
    return recurring


def create_recurring_transaction(
    user_id: int,
    account_id: int,
    category_id: int | None,
    description: str,
    type: str,
    amount: Decimal,
    frequency: str,
    day_of_month: int | None,
    start_date: date,
    end_date: date | None,
) -> RecurringTransaction:
    _get_owned_account(user_id, account_id)
    _get_owned_category(user_id, category_id)

    recurring = RecurringTransaction(
        user_id=user_id,
        account_id=account_id,
        category_id=category_id,
        description=description,
        type=type,
        amount=amount,
        frequency=frequency,
        day_of_month=day_of_month,
        start_date=start_date,
        end_date=end_date,
        is_active=True,
    )
    db.session.add(recurring)
    db.session.commit()
    return recurring


def update_recurring_transaction(
    user_id: int, recurring_id: int, **fields
) -> RecurringTransaction:
    recurring = get_recurring_transaction(user_id, recurring_id)
    if fields.get("category_id") is not None:
        _get_owned_category(user_id, fields["category_id"])
    for key, value in fields.items():
        if value is not None:
            setattr(recurring, key, value)
    db.session.commit()
    return recurring


def delete_recurring_transaction(user_id: int, recurring_id: int) -> None:
    recurring = get_recurring_transaction(user_id, recurring_id)

    has_transactions = (
        db.session.query(Transaction).filter_by(recurring_id=recurring_id, user_id=user_id).first()
        is not None
    )
    if has_transactions:
        raise ConflictError(
            "Esta recorrência já gerou transações e não pode ser excluída. "
            "Desative-a (is_active=False) em vez de excluí-la."
        )

    db.session.delete(recurring)
    db.session.commit()


def generate_due_transactions(
    user_id: int, recurring_id: int, until: date | None = None
) -> list[Transaction]:
    recurring = get_recurring_transaction(user_id, recurring_id)
    if not recurring.is_active:
        raise ValidationError("Esta recorrência está inativa.")

    account = _get_owned_account(user_id, recurring.account_id)
    until = until or datetime.now(timezone.utc).date()

    generated: list[Transaction] = []
    cursor = recurring.last_generated

    while True:
        next_date = _next_occurrence(recurring, cursor)
        if next_date > until:
            break
        if recurring.end_date is not None and next_date > recurring.end_date:
            break

        transaction = Transaction(
            user_id=user_id,
            account_id=recurring.account_id,
            category_id=recurring.category_id,
            recurring_id=recurring.id,
            type=recurring.type,
            description=recurring.description,
            amount=recurring.amount,
            date=next_date,
            is_paid=True,
            notes=None,
        )
        db.session.add(transaction)
        account.current_balance += _signed_amount(recurring.type, recurring.amount)
        generated.append(transaction)

        cursor = next_date

    if cursor is not None and cursor != recurring.last_generated:
        recurring.last_generated = cursor

    db.session.commit()
    return generated
