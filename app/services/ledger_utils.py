"""Helpers para atualizar campos monetários sem lost update.

Todo incremento/decremento de um campo monetário (current_balance,
total_amount, paid_amount) precisa virar um UPDATE atômico no SQL
(`campo = campo + delta`), nunca um `objeto.campo += delta` em Python
seguido de commit — essa última forma lê o valor, calcula em memória e
escreve de volta, e sob duas requisições concorrentes a segunda escrita
pode sobrescrever a primeira (lost update clássico).

Um UPDATE de linha única com expressão SQL (`col = col + delta`) é
atômico mesmo sem lock explícito: tanto Postgres/MySQL (que tomam lock
de linha implícito no UPDATE) quanto SQLite (que serializa escritas no
nível do arquivo) resolvem duas dessas instruções em sequência, nunca
perdendo uma delas.
"""

from decimal import Decimal

from sqlalchemy import update

from app.extensions import db
from app.models.account import Account
from app.models.invoice import Invoice


def adjust_account_balance(account_id: int, delta: Decimal) -> None:
    """Aplica `current_balance += delta` via UPDATE atômico no banco."""
    db.session.execute(
        update(Account).where(Account.id == account_id).values(current_balance=Account.current_balance + delta)
    )


def adjust_invoice_total(invoice: Invoice, delta: Decimal) -> None:
    """Aplica `total_amount += delta` via UPDATE atômico e recarrega o
    objeto em memória (`session.refresh`) — necessário porque código
    logo em seguida, ainda dentro da mesma transação/antes do commit,
    pode decidir algo com base em `invoice.total_amount`."""
    db.session.execute(
        update(Invoice).where(Invoice.id == invoice.id).values(total_amount=Invoice.total_amount + delta)
    )
    db.session.refresh(invoice)


def adjust_invoice_paid(invoice: Invoice, delta: Decimal) -> None:
    """Idem para `paid_amount`."""
    db.session.execute(
        update(Invoice).where(Invoice.id == invoice.id).values(paid_amount=Invoice.paid_amount + delta)
    )
    db.session.refresh(invoice)
