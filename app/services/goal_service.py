from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models.goal import Goal
from app.services.exceptions import NotFoundError, ValidationError


def list_goals(user_id: int) -> list[Goal]:
    return db.session.query(Goal).filter_by(user_id=user_id).order_by(Goal.created_at.desc()).all()


def get_goal(user_id: int, goal_id: int) -> Goal:
    goal = db.session.query(Goal).filter_by(id=goal_id, user_id=user_id).first()
    if goal is None:
        raise NotFoundError("Meta não encontrada.")
    return goal


def create_goal(
    user_id: int, name: str, target_amount: Decimal, target_date: date | None
) -> Goal:
    goal = Goal(
        user_id=user_id,
        name=name,
        target_amount=target_amount,
        current_amount=Decimal(0),
        target_date=target_date,
        status="in_progress",
    )
    db.session.add(goal)
    db.session.commit()
    return goal


def update_goal(user_id: int, goal_id: int, **fields) -> Goal:
    goal = get_goal(user_id, goal_id)
    for key, value in fields.items():
        if value is not None:
            setattr(goal, key, value)
    db.session.commit()
    return goal


def delete_goal(user_id: int, goal_id: int) -> None:
    goal = get_goal(user_id, goal_id)
    db.session.delete(goal)
    db.session.commit()


def contribute_to_goal(user_id: int, goal_id: int, amount: Decimal) -> Goal:
    goal = get_goal(user_id, goal_id)
    if goal.status != "in_progress":
        raise ValidationError("Só é possível contribuir para metas em andamento.")

    goal.current_amount += amount
    if goal.current_amount >= goal.target_amount:
        goal.status = "achieved"

    db.session.commit()
    return goal
