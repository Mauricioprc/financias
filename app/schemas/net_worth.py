from marshmallow import Schema, fields


class NetWorthHistoryQuerySchema(Schema):
    months = fields.Integer(required=False, load_default=12)


class NetWorthHistoryItemSchema(Schema):
    month = fields.String()
    total_accounts_balance = fields.Decimal(as_string=True)


class NetWorthTodaySchema(Schema):
    accounts_total = fields.Decimal(as_string=True)
    investments_total = fields.Decimal(as_string=True)
    unpaid_invoices_total = fields.Decimal(as_string=True)
    net_worth = fields.Decimal(as_string=True)
