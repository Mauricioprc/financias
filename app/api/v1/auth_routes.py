from flask import Blueprint, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required

from app.api.decorators import require_user, validate_json
from app.extensions import db
from app.models.user import User
from app.schemas.user import LoginSchema, RegisterSchema, UserOutSchema
from app.services import auth_service

bp = Blueprint("auth", __name__)

register_schema = RegisterSchema()
login_schema = LoginSchema()
user_out_schema = UserOutSchema()


@bp.route("/register", methods=["POST"])
@validate_json(register_schema)
def register(payload):
    user = auth_service.register_user(
        name=payload["name"], email=payload["email"], password=payload["password"]
    )
    tokens = auth_service.issue_tokens(user)
    return (
        jsonify({"data": {"user": user_out_schema.dump(user), **tokens}, "meta": {}}),
        201,
    )


@bp.route("/login", methods=["POST"])
@validate_json(login_schema)
def login(payload):
    user = auth_service.authenticate_user(email=payload["email"], password=payload["password"])
    tokens = auth_service.issue_tokens(user)
    return jsonify({"data": {"user": user_out_schema.dump(user), **tokens}, "meta": {}})


@bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify({"data": {"access_token": access_token}, "meta": {}})


@bp.route("/me", methods=["GET"])
@require_user
def me(user_id):
    user = db.session.get(User, user_id)
    return jsonify({"data": user_out_schema.dump(user), "meta": {}})
