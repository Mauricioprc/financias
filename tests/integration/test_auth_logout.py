from app import create_app
from app.extensions import db
from app.services.auth_service import cleanup_expired_revoked_tokens


def _register_and_login(client):
    client.post(
        "/api/v1/auth/register",
        json={"name": "Ana", "email": "ana@example.com", "password": "senha1234"},
    )
    resp = client.post(
        "/api/v1/auth/login", json={"email": "ana@example.com", "password": "senha1234"}
    )
    data = resp.get_json()["data"]
    return data["access_token"], data["refresh_token"]


def test_logout_revokes_refresh_token_and_blocks_future_refresh(client):
    access_token, refresh_token = _register_and_login(client)

    resp = client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["revoked"] is True

    resp = client.post(
        "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "TOKEN_REVOKED"


def test_logout_can_also_revoke_access_token(client):
    access_token, refresh_token = _register_and_login(client)

    resp = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {refresh_token}"},
        json={"access_token": access_token},
    )
    assert resp.status_code == 200

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "TOKEN_REVOKED"


def test_refresh_still_works_before_logout(client):
    _, refresh_token = _register_and_login(client)

    resp = client.post(
        "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.get_json()["data"]


def test_cleanup_expired_revoked_tokens_removes_only_expired():
    from datetime import datetime, timedelta, timezone

    from app.models.revoked_token import RevokedToken
    from app.models.user import User

    app = create_app("testing")
    with app.app_context():
        db.create_all()
        user = User(name="Ana", email="ana2@example.com", password_hash="x")
        db.session.add(user)
        db.session.commit()

        expired = RevokedToken(
            jti="expired-jti",
            token_type="refresh",
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        still_valid = RevokedToken(
            jti="valid-jti",
            token_type="refresh",
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        db.session.add_all([expired, still_valid])
        db.session.commit()

        deleted = cleanup_expired_revoked_tokens()
        assert deleted == 1

        remaining = db.session.query(RevokedToken).all()
        assert len(remaining) == 1
        assert remaining[0].jti == "valid-jti"

        db.session.remove()
        db.drop_all()
