"""Mesmo estilo de tests/integration/test_balance_concurrency.py: prova
que `current_amount` de uma `Goal` não perde escritas sob concorrência
(lost update), simulando a corrida de forma **determinística** com duas
Flask app contexts/sessões independentes em vez de threads reais contra
SQLite (frágil nesse ambiente — ver docstring do módulo irmão pro
racional completo).

Nota sobre `with_for_update()`: no SQLAlchemy, o dialeto do SQLite ignora
silenciosamente a cláusula `FOR UPDATE` (não trava a linha de verdade —
isso só tem efeito real em Postgres/MySQL, que é o motivo de usar
`with_for_update()` em `goal_service.contribute_to_goal`, no mesmo
espírito de `invoice_service.register_payment`). Por isso este teste
prova a garantia que **é** verificável em SQLite — a soma de
`current_amount` nunca perde uma escrita, porque o incremento em si é um
UPDATE atômico (`ledger_utils.adjust_goal_amount`), independente de
quando cada sessão leu o valor.
"""

from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.goal import Goal
from app.models.user import User
from app.services.ledger_utils import adjust_goal_amount

FIRST_CONTRIBUTION = Decimal("10.00")
SECOND_CONTRIBUTION = Decimal("20.00")


def _make_file_db_app(tmp_path):
    app = create_app("testing")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'goal_concurrency.db'}"
    return app


def test_concurrent_goal_contributions_do_not_lose_writes(tmp_path):
    app = _make_file_db_app(tmp_path)

    with app.app_context():
        db.create_all()
        user = User(name="Race", email="race-goal@example.com", password_hash="x")
        db.session.add(user)
        db.session.commit()

        goal = Goal(
            user_id=user.id,
            name="Viagem",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("0.00"),
            status="in_progress",
        )
        db.session.add(goal)
        db.session.commit()
        goal_id = goal.id

    # --- Contexto/sessão 1: "requisição 1" chega e lê a meta ---
    ctx1 = app.app_context()
    ctx1.push()
    goal_1 = db.session.get(Goal, goal_id)
    assert goal_1.current_amount == Decimal("0.00")

    # --- Contexto/sessão 2 (empilhado por cima): "requisição 2" chega
    # antes da 1 terminar, lê a mesma meta ainda não alterada ---
    ctx2 = app.app_context()
    ctx2.push()
    goal_2 = db.session.get(Goal, goal_id)
    assert goal_2.current_amount == Decimal("0.00")

    # Sessão 2 termina primeiro: aplica sua contribuição e comita.
    adjust_goal_amount(goal_id, SECOND_CONTRIBUTION)
    db.session.commit()
    ctx2.pop()

    # Sessão 1 termina por último, usando o helper de produção com o valor
    # que ela havia decidido aplicar lá no passo de leitura.
    adjust_goal_amount(goal_id, FIRST_CONTRIBUTION)
    db.session.commit()
    ctx1.pop()

    with app.app_context():
        refreshed = db.session.get(Goal, goal_id)
        expected = FIRST_CONTRIBUTION + SECOND_CONTRIBUTION
        assert refreshed.current_amount == expected, (
            f"Lost update detectado: esperado {expected}, obtido "
            f"{refreshed.current_amount}."
        )
        db.drop_all()
