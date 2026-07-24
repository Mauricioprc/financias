from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_json
from app.schemas.category import CategoryCreateSchema, CategoryOutSchema, CategoryUpdateSchema
from app.services import category_service

bp = Blueprint("categories", __name__)

create_schema = CategoryCreateSchema()
update_schema = CategoryUpdateSchema()
out_schema = CategoryOutSchema()


@bp.route("", methods=["GET"])
@require_user
def list_categories_route(user_id):
    categories = category_service.list_categories(user_id)
    return jsonify(
        {"data": out_schema.dump(categories, many=True), "meta": {"total": len(categories)}}
    )


@bp.route("", methods=["POST"])
@require_user
@validate_json(create_schema)
def create_category_route(payload, user_id):
    category = category_service.create_category(
        user_id=user_id,
        name=payload["name"],
        type=payload["type"],
        parent_id=payload["parent_id"],
        icon=payload["icon"],
        color=payload["color"],
    )
    return jsonify({"data": out_schema.dump(category), "meta": {}}), 201


@bp.route("/<int:category_id>", methods=["GET"])
@require_user
def get_category_route(user_id, category_id):
    category = category_service.get_category(user_id, category_id)
    return jsonify({"data": out_schema.dump(category), "meta": {}})


@bp.route("/<int:category_id>", methods=["PATCH"])
@require_user
@validate_json(update_schema)
def update_category_route(payload, user_id, category_id):
    category = category_service.update_category(user_id, category_id, **payload)
    return jsonify({"data": out_schema.dump(category), "meta": {}})


@bp.route("/<int:category_id>", methods=["DELETE"])
@require_user
def delete_category_route(user_id, category_id):
    category_service.delete_category(user_id, category_id)
    return "", 204
