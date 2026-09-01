"""Prova de que a atualização de current_balance não perde escritas sob
concorrência (lost update).

Em vez de depender de timing real de threads contra um SQLite compartilhado
(frágil nesse ambiente — o módulo sqlite3 não é seguro para uso simultâneo
da mesma conexão por múltiplas threads, e isso mascararia o que queremos
provar), simulamos a corrida de forma **determinística** empurrando duas
Flask app contexts (cada uma com sua própria sessão de banco, via o
scoping do Flask-SQLAlchemy) e controlando manualmente a ordem de
leitura/escrita/commit entre elas:

1. Contexto/sessão 1 lê o `Account` (saldo 0) — "requisição 1 chegou".
2. Contexto/sessão 2 lê o mesmo `Account` (ainda saldo 0, porque a sessão 1
   não comitou nada ainda) — "requisição 2 chegou antes da 1 terminar".
3. Sessão 2 aplica seu incremento e comita primeiro.
4. Sessão 1 aplica o incremento dela (calculado/decidido antes do passo 3)
   e comita por último.

Com o padrão antigo (`objeto.campo += valor`, calculado em cima do valor
lido no passo 1/2), o commit da sessão 1 no passo 4 sobrescreveria o que a
sessão 2 escreveu — uma das duas escritas seria perdida. Com o UPDATE
atômico (`campo = campo + delta`, resolvido no SQL no momento do UPDATE,
não com o valor lido em Python), as duas escritas se acumulam
corretamente não importa a ordem ou o que foi lido antes.

Usamos um SQLite em arquivo (não o `:memory:` do fixture `app` padrão)
para que as duas sessões tenham conexões de fato independentes — o
`:memory:` do fixture usa `StaticPool` (uma única conexão física
compartilhada), o que mascararia a independência das transações.
"""

from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.account import Account
from app.models.user import User
from app.services.ledger_utils import adjust_account_balance

FIRST_DEPOSIT = Decimal("10.00")
SECOND_DEPOSIT = Decimal("20.00")


def _make_file_db_app(tmp_path):
    app = create_app("testing")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'concurrency.db'}"
    return app


def test_concurrent_balance_updates_do_not_lose_writes(tmp_path):
    app = _make_file_db_app(tmp_path)

    with app.app_context():
        db.create_all()
        user = User(name="Race", email="race@example.com", password_hash="x")
        db.session.add(user)
        db.session.commit()

        account = Account(
            user_id=user.id,
            name="Conta concorrente",
            type="checking",
            initial_balance=Decimal("0.00"),
            current_balance=Decimal("0.00"),
        )
        db.session.add(account)
        db.session.commit()
        account_id = account.id

    # --- Contexto/sessão 1: "requisição 1" chega e lê o saldo ---
    ctx1 = app.app_context()
    ctx1.push()
    account_1 = db.session.get(Account, account_id)
    assert account_1.current_balance == Decimal("0.00")

    # --- Contexto/sessão 2 (empilhado por cima): "requisição 2" chega
    # antes da 1 terminar, lê o mesmo saldo ainda não alterado ---
    ctx2 = app.app_context()
    ctx2.push()
    account_2 = db.session.get(Account, account_id)
    assert account_2.current_balance == Decimal("0.00")

    # Sessão 2 termina primeiro: aplica seu incremento e comita.
    adjust_account_balance(account_id, SECOND_DEPOSIT)
    db.session.commit()
    ctx2.pop()

    # Sessão 1 termina por último, usando o helper de produção com o delta
    # que ela havia decidido aplicar lá no passo de leitura.
    adjust_account_balance(account_id, FIRST_DEPOSIT)
    db.session.commit()
    ctx1.pop()

    with app.app_context():
        refreshed = db.session.get(Account, account_id)
        expected = FIRST_DEPOSIT + SECOND_DEPOSIT
        assert refreshed.current_balance == expected, (
            f"Lost update detectado: esperado {expected}, obtido "
            f"{refreshed.current_balance}."
        )
        db.drop_all()
