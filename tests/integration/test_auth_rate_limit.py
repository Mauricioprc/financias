"""RATELIMIT_ENABLED fica False por padrão em testing (ver app/config.py)
pra não quebrar os outros testes de auth, que batem em /login e /register
várias vezes por execução. Aqui reativamos explicitamente."""

import pytest

from app import create_app
from app.extensions import db as _db
from app.extensions import limiter


@pytest.fixture()
def rate_limited_app():
    application = create_app("testing")
    application.config["RATELIMIT_ENABLED"] = True
    with application.app_context():
        _db.create_all()
        # `limiter` é um singleton de módulo compartilhado por todo o
        # processo de teste; re-inicializa pra esta app (pega
        # RATELIMIT_ENABLED=True) e limpa contadores de execuções
        # anteriores antes de cada teste.
        limiter.init_app(application)
        limiter.storage.reset()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def rl_client(rate_limited_app):
    return rate_limited_app.test_client()


def test_login_is_rate_limited_after_five_attempts_per_minute(rl_client):
    payload = {"email": "victim@example.com", "password": "senhaerrada"}

    responses = [rl_client.post("/api/v1/auth/login", json=payload) for _ in range(5)]
    for resp in responses:
        assert resp.status_code != 429

    resp = rl_client.post("/api/v1/auth/login", json=payload)
    assert resp.status_code == 429
    body = resp.get_json()
    assert body["error"]["code"] == "RATE_LIMITED"


def test_register_is_rate_limited_after_five_attempts_per_minute(rl_client):
    for i in range(5):
        rl_client.post(
            "/api/v1/auth/register",
            json={"name": "Teste", "email": f"user{i}@example.com", "password": "senha1234"},
        )

    resp = rl_client.post(
        "/api/v1/auth/register",
        json={"name": "Teste", "email": "user_excedente@example.com", "password": "senha1234"},
    )
    assert resp.status_code == 429
    assert resp.get_json()["error"]["code"] == "RATE_LIMITED"


def test_login_rate_limit_also_keys_by_attempted_email_across_ips(rate_limited_app):
    """Mesmo email, IPs diferentes — não deveria escapar do limite."""
    payload = {"email": "victim2@example.com", "password": "senhaerrada"}

    hit_429 = False
    for i in range(6):
        client = rate_limited_app.test_client()
        resp = client.post(
            "/api/v1/auth/login",
            json=payload,
            environ_overrides={"REMOTE_ADDR": f"10.0.0.{i}"},
        )
        if resp.status_code == 429:
            hit_429 = True
            assert resp.get_json()["error"]["code"] == "RATE_LIMITED"
            break

    assert hit_429, "esperava 429 por causa do limite por email, mesmo variando o IP"
