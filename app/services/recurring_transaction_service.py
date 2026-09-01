from datetime import date, datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models.account import Account
from app.models.category import Category
from app.models.credit_card import CreditCard
from app.models.recurring_transaction import RecurringTransaction
from app.models.transaction import Transaction
from app.services import invoice_service
from app.services.exceptions import ConflictError, NotFoundError, ServiceError, ValidationError
from app.services.ledger_utils import adjust_account_balance
from app.utils.datetime_utils import add_months, clamped_date


def _signed_amount(type_: str, amount: Decimal) -> Decimal:
    return amount if type_ == "income" else -amount


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


def _get_owned_credit_card(user_id: int, credit_card_id: int | None) -> CreditCard | None:
    if credit_card_id is None:
        return None
    card = db.session.query(CreditCard).filter_by(id=credit_card_id, user_id=user_id).first()
    if card is None:
        raise ValidationError("credit_card_id inválido para este usuário.")
    return card


def _next_occurrence(recurring: RecurringTransaction, after: date | None) -> date:
    if after is None:
        return recurring.start_date

    if recurring.frequency == "weekly":
        return date.fromordinal(after.toordinal() + 7)

    if recurring.frequency == "monthly":
        year, month = add_months(after.year, after.month, 1)
        day = recurring.day_of_month or recurring.start_date.day
        return clamped_date(year, month, day)

    if recurring.frequency == "yearly":
        year = after.year + 1
        return clamped_date(year, recurring.start_date.month, recurring.start_date.day)

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
    credit_card_id: int | None = None,
) -> RecurringTransaction:
    _get_owned_account(user_id, account_id)
    _get_owned_category(user_id, category_id)
    _get_owned_credit_card(user_id, credit_card_id)
    # A combinação credit_card_id + type != expense já é barrada no schema
    # (validate_card_requires_expense); aqui é só a validação de posse.

    recurring = RecurringTransaction(
        user_id=user_id,
        account_id=account_id,
        category_id=category_id,
        credit_card_id=credit_card_id,
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
    if fields.get("credit_card_id") is not None:
        _get_owned_credit_card(user_id, fields["credit_card_id"])
        if recurring.type != "expense":
            raise ValidationError(
                "Só é possível vincular cartão de crédito a recorrências do tipo expense."
            )
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
    """Gera as ocorrências vencidas até `until`. Assinaturas (recurring com
    `credit_card_id`) vão pra fatura do mês de cada ocorrência — mesma regra
    de fechamento usada em qualquer compra de cartão — em vez de debitar a
    conta na hora; o resto (salário, débito automático em conta) continua
    afetando `current_balance` como sempre."""
    recurring = get_recurring_transaction(user_id, recurring_id)
    if not recurring.is_active:
        raise ValidationError("Esta recorrência está inativa.")

    account = _get_owned_account(user_id, recurring.account_id)
    card = _get_owned_credit_card(user_id, recurring.credit_card_id)
    until = until or datetime.now(timezone.utc).date()

    generated: list[Transaction] = []
    cursor = recurring.last_generated

    try:
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
                credit_card_id=recurring.credit_card_id,
                recurring_id=recurring.id,
                type=recurring.type,
                description=recurring.description,
                amount=recurring.amount,
                date=next_date,
                is_paid=True,
                notes=None,
            )

            if card is not None:
                invoice = invoice_service.get_or_create_open_invoice(user_id, card, next_date)
                invoice_service.assert_invoice_open(invoice)
                invoice_service.add_amount(invoice, recurring.amount)
                transaction.invoice_id = invoice.id
            else:
                adjust_account_balance(account.id, _signed_amount(recurring.type, recurring.amount))

            db.session.add(transaction)
            generated.append(transaction)

            cursor = next_date
    except Exception:
        # Mesma lógica de transaction_service.create_installment_purchase:
        # se uma ocorrência cair numa fatura futura já fechada manualmente,
        # não dá pra deixar as ocorrências anteriores desse mesmo "gerar"
        # meio-persistidas — desfaz tudo e não avança last_generated.
        db.session.rollback()
        raise

    if cursor is not None and cursor != recurring.last_generated:
        recurring.last_generated = cursor

    db.session.commit()
    return generated


def generate_due_subscriptions(user_id: int, until: date | None = None) -> dict:
    """Gera automaticamente as ocorrências vencidas de toda assinatura ativa
    (recurring com `credit_card_id`) até `until` (padrão: hoje). Pensado pra
    ser chamado silenciosamente sempre que o app é aberto — por isso nunca
    deixa uma assinatura com problema (ex.: fatura futura fechada na mão)
    travar as demais, nem propaga erro pra quebrar a tela que disparou a
    chamada; cada assinatura é isolada e os erros voltam num relatório."""
    subscriptions = (
        db.session.query(RecurringTransaction)
        .filter_by(user_id=user_id, is_active=True)
        .filter(RecurringTransaction.credit_card_id.isnot(None))
        .all()
    )

    generated_count = 0
    errors: list[dict] = []
    for recurring in subscriptions:
        try:
            generated = generate_due_transactions(user_id, recurring.id, until=until)
            generated_count += len(generated)
        except ServiceError as exc:
            errors.append({"recurring_id": recurring.id, "message": exc.message})

    return {"generated_count": generated_count, "errors": errors}
