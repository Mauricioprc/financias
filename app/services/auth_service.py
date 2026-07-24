from flask_jwt_extended import create_access_token, create_refresh_token

from app.extensions import db
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
