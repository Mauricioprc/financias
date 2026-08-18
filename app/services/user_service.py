from app.extensions import db
from app.models.user import User
from app.services.exceptions import ConflictError, NotFoundError


def get_user(user_id: int) -> User:
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError("Usuário não encontrado.")
    return user


def update_profile(user_id: int, **fields) -> User:
    user = get_user(user_id)

    if "phone_number" in fields:
        phone_number = fields["phone_number"]
        if phone_number is not None:
            existing = (
                db.session.query(User)
                .filter(User.phone_number == phone_number, User.id != user_id)
                .first()
            )
            if existing is not None:
                raise ConflictError("Este número já está vinculado a outra conta.")
        user.phone_number = phone_number

    db.session.commit()
    return user
