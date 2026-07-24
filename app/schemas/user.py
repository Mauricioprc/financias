from marshmallow import Schema, fields, validate


class RegisterSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    email = fields.Email(required=True)
    password = fields.String(
        required=True, validate=validate.Length(min=8, max=128), load_only=True
    )


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)


class UserOutSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    email = fields.Email()
    phone_number = fields.String(allow_none=True)
    timezone = fields.String()
    created_at = fields.DateTime()
