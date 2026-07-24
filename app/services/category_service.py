from app.extensions import db
from app.models.category import Category
from app.services.exceptions import NotFoundError, ValidationError


def list_categories(user_id: int) -> list[Category]:
    return db.session.query(Category).filter_by(user_id=user_id).order_by(Category.name).all()


def get_category(user_id: int, category_id: int) -> Category:
    category = db.session.query(Category).filter_by(id=category_id, user_id=user_id).first()
    if category is None:
        raise NotFoundError("Categoria não encontrada.")
    return category


def create_category(
    user_id: int,
    name: str,
    type: str,
    parent_id: int | None,
    icon: str | None,
    color: str | None,
) -> Category:
    if parent_id is not None:
        get_category(user_id, parent_id)

    category = Category(
        user_id=user_id, name=name, type=type, parent_id=parent_id, icon=icon, color=color
    )
    db.session.add(category)
    db.session.commit()
    return category


def update_category(user_id: int, category_id: int, **fields) -> Category:
    category = get_category(user_id, category_id)
    for key, value in fields.items():
        if value is not None:
            setattr(category, key, value)
    db.session.commit()
    return category


def delete_category(user_id: int, category_id: int) -> None:
    category = get_category(user_id, category_id)
    if category.is_system:
        raise ValidationError("Categorias padrão do sistema não podem ser removidas.")
    db.session.delete(category)
    db.session.commit()
