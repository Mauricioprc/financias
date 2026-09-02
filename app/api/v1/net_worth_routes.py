from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_query
from app.schemas.net_worth import (
    NetWorthHistoryItemSchema,
    NetWorthHistoryQuerySchema,
    NetWorthTodaySchema,
)
from app.services import net_worth_service

bp = Blueprint("net_worth", __name__)

history_query_schema = NetWorthHistoryQuerySchema()
history_item_schema = NetWorthHistoryItemSchema()
today_schema = NetWorthTodaySchema()


@bp.route("/history", methods=["GET"])
@require_user
@validate_query(history_query_schema)
def net_worth_history_route(query, user_id):
    history = net_worth_service.compute_net_worth_history(user_id, months=query["months"])
    return jsonify(
        {"data": history_item_schema.dump(history, many=True), "meta": {"total": len(history)}}
    )


@bp.route("/today", methods=["GET"])
@require_user
def net_worth_today_route(user_id):
    today = net_worth_service.compute_net_worth_today(user_id)
    return jsonify({"data": today_schema.dump(today), "meta": {}})
