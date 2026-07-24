def test_register_and_login(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"name": "Ana", "email": "ana@example.com", "password": "senha1234"},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert "access_token" in body["data"]
    assert body["data"]["user"]["email"] == "ana@example.com"

    resp = client.post(
        "/api/v1/auth/login", json={"email": "ana@example.com", "password": "senha1234"}
    )
    assert resp.status_code == 200


def test_register_duplicate_email_is_conflict(client):
    payload = {"name": "Ana", "email": "ana@example.com", "password": "senha1234"}
    client.post("/api/v1/auth/register", json=payload)
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "CONFLICT"


def test_login_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"name": "Ana", "email": "ana@example.com", "password": "senha1234"},
    )
    resp = client.post(
        "/api/v1/auth/login", json={"email": "ana@example.com", "password": "wrong"}
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_me_requires_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "UNAUTHORIZED"


def test_me_with_token(client, auth_headers):
    headers = auth_headers()
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["email"] == "user@example.com"
