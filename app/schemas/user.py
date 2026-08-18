from marshmallow import Schema, fields, validate

# E.164: + seguido de 8 a 15 dígitos, sem espaços/traços (ex.: +5511999999999)
E164_REGEX = r"^\+[1-9]\d{7,14}$"


class RegisterSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    email = fields.Email(required=True)
    password = fields.String(
        required=True, validate=validate.Length(min=8, max=128), load_only=True
    )


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)


class UpdateProfileSchema(Schema):
    phone_number = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Regexp(
            E164_REGEX, error="Telefone deve estar no formato internacional E.164, ex.: +5511999999999."
        ),
    )


class UserOutSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    email = fields.Email()
    phone_number = fields.String(allow_none=True)
    timezone = fields.String()
    created_at = fields.DateTime()
