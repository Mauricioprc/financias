from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_query
from app.schemas.upcoming_bill import UpcomingBillItemSchema, UpcomingBillsQuerySchema
from app.services import upcoming_bills_service

bp = Blueprint("upcoming_bills", __name__)

query_schema = UpcomingBillsQuerySchema()
item_schema = UpcomingBillItemSchema()


@bp.route("", methods=["GET"])
@require_user
@validate_query(query_schema)
def list_upcoming_bills_route(query, user_id):
    bills = upcoming_bills_service.list_upcoming_bills(user_id, days=query["days"])
    return jsonify({"data": item_schema.dump(bills, many=True), "meta": {"total": len(bills)}})
