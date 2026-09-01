"""Comandos de manutenção via `flask <comando>`."""

import logging
from decimal import Decimal

import click
from flask import Flask
from sqlalchemy import case, func

from app.extensions import db
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.transfer import Transfer

logger = logging.getLogger(__name__)


def register_cli(app: Flask) -> None:
    app.cli.add_command(reconcile_balances)


def _expected_balance(account: Account) -> Decimal:
    """Recalcula o saldo esperado de `account` a partir do histórico, do
    zero — não confia em `current_balance`.

    Só entram na soma transações "de conta" (`credit_card_id is None`) e
    pagas (`is_paid`): compras no cartão nunca tocam `current_balance`
    diretamente (isso só acontece quando a fatura é paga, o que já gera
    uma `Transaction` de pagamento normal, com `credit_card_id=None`) —
    ver `transaction_service.create_transaction` e
    `invoice_service.register_payment`.
    """
    transactions_sum = (
        db.session.query(
            func.coalesce(
                func.sum(
                    case(
                        (Transaction.type == "income", Transaction.amount),
                        else_=-Transaction.amount,
                    )
                ),
                0,
            )
        )
        .filter(
            Transaction.account_id == account.id,
            Transaction.is_paid.is_(True),
            Transaction.credit_card_id.is_(None),
        )
        .scalar()
    )
    transfers_out = (
        db.session.query(func.coalesce(func.sum(Transfer.amount), 0))
        .filter(Transfer.from_account_id == account.id)
        .scalar()
    )
    transfers_in = (
        db.session.query(func.coalesce(func.sum(Transfer.amount), 0))
        .filter(Transfer.to_account_id == account.id)
        .scalar()
    )
    return (
        Decimal(account.initial_balance)
        + Decimal(transactions_sum)
        - Decimal(transfers_out)
        + Decimal(transfers_in)
    )


@click.command("reconcile-balances")
def reconcile_balances() -> None:
    """Recalcula o saldo esperado de cada Account a partir do histórico de
    transações/transferências e compara com `current_balance`.

    Só loga divergências (account_id + delta) — não corrige nada
    automaticamente, porque uma divergência pode ter causa raiz variada
    (bug de lógica, dado corrompido manualmente, migração antiga) e uma
    correção automática às cegas pode esconder o problema real. Rode
    periodicamente (ex.: cron do PythonAnywhere) e trate divergências
    reportadas investigando o histórico da conta específica.
    """
    accounts = db.session.query(Account).order_by(Account.id).all()
    divergent = 0
    for account in accounts:
        expected = _expected_balance(account)
        delta = account.current_balance - expected
        if delta != 0:
            divergent += 1
            message = (
                f"[reconcile-balances] divergência: account_id={account.id} "
                f"user_id={account.user_id} current_balance={account.current_balance} "
                f"esperado={expected} delta={delta}"
            )
            logger.warning(message)
            click.echo(message)

    if divergent == 0:
        click.echo("[reconcile-balances] nenhuma divergência encontrada.")
    else:
        click.echo(f"[reconcile-balances] {divergent} conta(s) com divergência encontrada(s).")
