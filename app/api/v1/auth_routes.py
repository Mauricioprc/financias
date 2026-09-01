from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    decode_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)

from app.api.decorators import require_user, validate_json
from app.extensions import db, limit_key_by_attempted_email, limiter
from app.models.user import User
from app.schemas.user import LoginSchema, RegisterSchema, UserOutSchema
from app.services import auth_service

bp = Blueprint("auth", __name__)

register_schema = RegisterSchema()
login_schema = LoginSchema()
user_out_schema = UserOutSchema()


@bp.route("/register", methods=["POST"])
@limiter.limit("5 per minute")
@limiter.limit("5 per minute", key_func=limit_key_by_attempted_email)
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
@limiter.limit("5 per minute")
@limiter.limit("5 per minute", key_func=limit_key_by_attempted_email)
@validate_json(login_schema)
def login(payload):
    user = auth_service.authenticate_user(email=payload["email"], password=payload["password"])
    tokens = auth_service.issue_tokens(user)
    return jsonify({"data": {"user": user_out_schema.dump(user), **tokens}, "meta": {}})


@bp.route("/refresh", methods=["POST"])
@limiter.limit("30 per minute")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify({"data": {"access_token": access_token}, "meta": {}})


@bp.route("/logout", methods=["POST"])
@jwt_required(refresh=True)
def logout():
    """Revoga o refresh token atual (enviado no header Authorization) e,
    opcionalmente, um access_token passado no corpo — pra logout também
    invalidar a sessão "ativa" na hora, sem esperar ele expirar."""
    claims = get_jwt()
    expires_at = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
    auth_service.revoke_token(
        jti=claims["jti"],
        token_type="refresh",
        user_id=int(get_jwt_identity()),
        expires_at=expires_at,
    )

    payload = request.get_json(silent=True) or {}
    access_token = payload.get("access_token")
    if access_token:
        try:
            access_claims = decode_token(access_token)
        except Exception:
            access_claims = None
        if access_claims is not None and access_claims.get("type") == "access":
            auth_service.revoke_token(
                jti=access_claims["jti"],
                token_type="access",
                user_id=int(access_claims["sub"]),
                expires_at=datetime.fromtimestamp(access_claims["exp"], tz=timezone.utc),
            )

    return jsonify({"data": {"revoked": True}, "meta": {}})


@bp.route("/me", methods=["GET"])
@require_user
def me(user_id):
    user = db.session.get(User, user_id)
    return jsonify({"data": user_out_schema.dump(user), "meta": {}})
