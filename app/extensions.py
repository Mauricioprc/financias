from flask import jsonify
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()


def _auth_error(code: str, message: str, status_code: int):
    return jsonify({"error": {"code": code, "message": message, "details": {}}}), status_code


@jwt.unauthorized_loader
def _handle_missing_token(reason: str):
    return _auth_error("UNAUTHORIZED", "Token de autenticação ausente.", 401)


@jwt.invalid_token_loader
def _handle_invalid_token(reason: str):
    return _auth_error("UNAUTHORIZED", "Token de autenticação inválido.", 401)


@jwt.expired_token_loader
def _handle_expired_token(jwt_header, jwt_payload):
    return _auth_error("TOKEN_EXPIRED", "Token de autenticação expirado.", 401)
