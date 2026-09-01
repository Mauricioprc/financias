import os

from flask import jsonify, request
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

# Storage em memória do processo (padrão do Flask-Limiter quando
# storage_uri não é configurado): funciona porque o deploy atual
# (PythonAnywhere, ver ARCHITECTURE.md) é single-process — cada worker
# teria seu próprio contador se isso mudasse pra múltiplos processos, o
# que tornaria o limite efetivo (limite × nº de workers). Se o deploy
# passar a rodar múltiplos processos/workers, trocar pra um storage
# compartilhado (ex.: Redis) via RATELIMIT_STORAGE_URI.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
)


def limit_key_by_attempted_email() -> str:
    """Chave de rate limit por email tentado (além do limite por IP) —
    impede que um atacante distribua tentativas de login/registro de um
    mesmo email entre vários IPs pra escapar do limite por IP."""
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email") or "").strip().lower()
    return email or get_remote_address()


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


@jwt.token_in_blocklist_loader
def _check_if_token_revoked(jwt_header: dict, jwt_payload: dict) -> bool:
    # Import local pra evitar import circular (o model importa `db` daqui).
    from app.models.revoked_token import RevokedToken

    jti = jwt_payload["jti"]
    return db.session.query(RevokedToken.id).filter_by(jti=jti).first() is not None


@jwt.revoked_token_loader
def _handle_revoked_token(jwt_header: dict, jwt_payload: dict):
    return _auth_error("TOKEN_REVOKED", "Este token foi revogado (logout).", 401)
