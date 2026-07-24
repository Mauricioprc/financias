from flask import Flask


def register_v1_blueprints(app: Flask) -> None:
    from app.api.v1.account_routes import bp as account_bp
    from app.api.v1.auth_routes import bp as auth_bp
    from app.api.v1.category_routes import bp as category_bp
    from app.api.v1.credit_card_routes import bp as credit_card_bp
    from app.api.v1.invoice_routes import bp as invoice_bp
    from app.api.v1.recurring_transaction_routes import bp as recurring_transaction_bp
    from app.api.v1.transaction_routes import bp as transaction_bp
    from app.api.v1.transfer_routes import bp as transfer_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(account_bp, url_prefix="/api/v1/accounts")
    app.register_blueprint(category_bp, url_prefix="/api/v1/categories")
    app.register_blueprint(credit_card_bp, url_prefix="/api/v1/credit-cards")
    app.register_blueprint(invoice_bp, url_prefix="/api/v1/invoices")
    app.register_blueprint(
        recurring_transaction_bp, url_prefix="/api/v1/recurring-transactions"
    )
    app.register_blueprint(transaction_bp, url_prefix="/api/v1/transactions")
    app.register_blueprint(transfer_bp, url_prefix="/api/v1/transfers")
