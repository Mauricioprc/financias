from marshmallow import Schema, fields, validate

CATEGORY_TYPES = ("income", "expense")


class CategoryCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=80))
    type = fields.String(required=True, validate=validate.OneOf(CATEGORY_TYPES))
    parent_id = fields.Integer(required=False, load_default=None, allow_none=True)
    icon = fields.String(required=False, load_default=None, allow_none=True)
    color = fields.String(
        required=False, load_default=None, allow_none=True, validate=validate.Length(max=7)
    )


class CategoryUpdateSchema(Schema):
    name = fields.String(required=False, validate=validate.Length(min=1, max=80))
    icon = fields.String(required=False, allow_none=True)
    color = fields.String(required=False, allow_none=True, validate=validate.Length(max=7))


class CategoryOutSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    type = fields.String()
    parent_id = fields.Integer(allow_none=True)
    icon = fields.String(allow_none=True)
    color = fields.String(allow_none=True)
    is_system = fields.Boolean()
    created_at = fields.DateTime()
