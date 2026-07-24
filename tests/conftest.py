import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture()
def app():
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(client):
    def _register(email: str = "user@example.com", password: str = "senha1234"):
        resp = client.post(
            "/api/v1/auth/register",
            json={"name": "Test User", "email": email, "password": password},
        )
        token = resp.get_json()["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _register
