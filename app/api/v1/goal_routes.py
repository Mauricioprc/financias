from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_json
from app.schemas.goal import GoalContributeSchema, GoalCreateSchema, GoalOutSchema, GoalUpdateSchema
from app.services import goal_service

bp = Blueprint("goals", __name__)

create_schema = GoalCreateSchema()
update_schema = GoalUpdateSchema()
contribute_schema = GoalContributeSchema()
out_schema = GoalOutSchema()


@bp.route("", methods=["GET"])
@require_user
def list_goals_route(user_id):
    goals = goal_service.list_goals(user_id)
    return jsonify({"data": out_schema.dump(goals, many=True), "meta": {"total": len(goals)}})


@bp.route("", methods=["POST"])
@require_user
@validate_json(create_schema)
def create_goal_route(payload, user_id):
    goal = goal_service.create_goal(
        user_id=user_id,
        name=payload["name"],
        target_amount=payload["target_amount"],
        target_date=payload["target_date"],
    )
    return jsonify({"data": out_schema.dump(goal), "meta": {}}), 201


@bp.route("/<int:goal_id>", methods=["GET"])
@require_user
def get_goal_route(user_id, goal_id):
    goal = goal_service.get_goal(user_id, goal_id)
    return jsonify({"data": out_schema.dump(goal), "meta": {}})


@bp.route("/<int:goal_id>", methods=["PATCH"])
@require_user
@validate_json(update_schema)
def update_goal_route(payload, user_id, goal_id):
    goal = goal_service.update_goal(user_id, goal_id, **payload)
    return jsonify({"data": out_schema.dump(goal), "meta": {}})


@bp.route("/<int:goal_id>", methods=["DELETE"])
@require_user
def delete_goal_route(user_id, goal_id):
    goal_service.delete_goal(user_id, goal_id)
    return "", 204


@bp.route("/<int:goal_id>/contribute", methods=["POST"])
@require_user
@validate_json(contribute_schema)
def contribute_to_goal_route(payload, user_id, goal_id):
    goal = goal_service.contribute_to_goal(user_id, goal_id, amount=payload["amount"])
    return jsonify({"data": out_schema.dump(goal), "meta": {}})
