from datetime import datetime, timezone

from flask_jwt_extended import create_access_token, create_refresh_token

from app.extensions import db
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.services.exceptions import ConflictError, ValidationError


def register_user(name: str, email: str, password: str) -> User:
    existing = db.session.query(User).filter_by(email=email).first()
    if existing is not None:
        raise ConflictError("Já existe um usuário com este email.")

    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def authenticate_user(email: str, password: str) -> User:
    user = db.session.query(User).filter_by(email=email).first()
    if user is None or not user.check_password(password):
        raise ValidationError("Email ou senha inválidos.")
    if not user.is_active:
        raise ValidationError("Usuário inativo.")
    return user


def issue_tokens(user: User) -> dict[str, str]:
    identity = str(user.id)
    return {
        "access_token": create_access_token(identity=identity),
        "refresh_token": create_refresh_token(identity=identity),
    }


def revoke_token(jti: str, token_type: str, user_id: int, expires_at: datetime) -> None:
    """Adiciona `jti` na blocklist (ver `token_in_blocklist_loader` em
    app/extensions.py). Idempotente: revogar o mesmo token duas vezes não
    é erro."""
    existing = db.session.query(RevokedToken).filter_by(jti=jti).first()
    if existing is not None:
        return
    db.session.add(
        RevokedToken(jti=jti, token_type=token_type, user_id=user_id, expires_at=expires_at)
    )
    db.session.commit()


def cleanup_expired_revoked_tokens() -> int:
    """Remove da blocklist os tokens cujo `expires_at` já passou — depois
    de expirados eles seriam rejeitados de qualquer forma (o próprio JWT
    expira), então mantê-los na blocklist só ocupa espaço. Retorna quantos
    registros foram removidos."""
    now = datetime.now(timezone.utc)
    deleted = (
        db.session.query(RevokedToken).filter(RevokedToken.expires_at < now).delete()
    )
    db.session.commit()
    return deleted
