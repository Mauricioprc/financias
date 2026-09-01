from app.extensions import db
from app.models.account import Account


def test_reconcile_balances_detects_no_divergence_when_consistent(app, client, auth_headers):
    headers = auth_headers()
    client.post(
        "/api/v1/accounts",
        json={"name": "Nubank", "type": "checking", "initial_balance": 100.0},
        headers=headers,
    )
    client.post(
        "/api/v1/accounts",
        json={"name": "Itaú", "type": "checking", "initial_balance": 50.0},
        headers=headers,
    )

    runner = app.test_cli_runner()
    result = runner.invoke(args=["reconcile-balances"])

    assert result.exit_code == 0
    assert "nenhuma divergência encontrada" in result.output


def test_reconcile_balances_detects_purposeful_inconsistency(app, client, auth_headers):
    headers = auth_headers()
    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Nubank", "type": "checking", "initial_balance": 100.0},
        headers=headers,
    )
    account_id = resp.get_json()["data"]["id"]

    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "type": "expense",
            "description": "Mercado",
            "amount": 30.0,
            "date": "2026-07-06",
        },
        headers=headers,
    )
    assert resp.status_code == 201

    # current_balance deveria ser 70.00 (100 - 30). Corrompe o valor
    # diretamente no banco pra simular uma divergência (bug, dado
    # corrompido manualmente, etc.) sem passar pelos services.
    with app.app_context():
        account = db.session.get(Account, account_id)
        account.current_balance = "999.99"
        db.session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(args=["reconcile-balances"])

    assert result.exit_code == 0
    assert f"account_id={account_id}" in result.output
    assert "999.99" in result.output
    assert "esperado=70.00" in result.output
    assert "1 conta(s) com divergência" in result.output

    # Não corrige nada — só reporta.
    with app.app_context():
        account = db.session.get(Account, account_id)
        assert str(account.current_balance) == "999.99"
