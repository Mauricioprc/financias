from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_json
from app.schemas.user import UpdateProfileSchema, UserOutSchema
from app.services import user_service

bp = Blueprint("users", __name__)

update_profile_schema = UpdateProfileSchema()
out_schema = UserOutSchema()


@bp.route("/me", methods=["PATCH"])
@require_user
@validate_json(update_profile_schema)
def update_profile_route(payload, user_id):
    user = user_service.update_profile(user_id, **payload)
    return jsonify({"data": out_schema.dump(user), "meta": {}})
