from marshmallow import Schema, fields, validate


class BalanceHistoryQuerySchema(Schema):
    days = fields.Integer(required=False, load_default=30, validate=validate.Range(min=1, max=365))
    account_id = fields.Integer(required=False, load_default=None, allow_none=True)


class BalanceHistoryPointSchema(Schema):
    date = fields.Date()
    balance = fields.Decimal(as_string=True)


class CategoryBreakdownQuerySchema(Schema):
    month = fields.String(required=True, validate=validate.Regexp(r"^\d{4}-\d{2}$"))
    type = fields.String(
        required=False, load_default="expense", validate=validate.OneOf(("income", "expense"))
    )
    account_id = fields.Integer(required=False, load_default=None, allow_none=True)


class CategoryBreakdownItemSchema(Schema):
    category_id = fields.Integer(allow_none=True)
    category_name = fields.String()
    total = fields.Decimal(as_string=True)


class IncomeVsExpenseQuerySchema(Schema):
    months = fields.Integer(required=False, load_default=12, validate=validate.Range(min=1, max=24))


class IncomeVsExpenseItemSchema(Schema):
    month = fields.String()
    income = fields.Decimal(as_string=True)
    expense = fields.Decimal(as_string=True)
