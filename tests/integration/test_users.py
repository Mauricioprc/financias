def test_update_profile_sets_phone_number(client, auth_headers):
    headers = auth_headers()

    resp = client.patch("/api/v1/users/me", json={"phone_number": "+5511999999999"}, headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["phone_number"] == "+5511999999999"

    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.get_json()["data"]["phone_number"] == "+5511999999999"


def test_update_profile_rejects_invalid_format(client, auth_headers):
    headers = auth_headers()

    resp = client.patch("/api/v1/users/me", json={"phone_number": "11999999999"}, headers=headers)
    assert resp.status_code == 422

    resp = client.patch("/api/v1/users/me", json={"phone_number": "not-a-phone"}, headers=headers)
    assert resp.status_code == 422


def test_update_profile_rejects_phone_already_linked_to_another_user(client, auth_headers):
    headers_a = auth_headers(email="a@example.com")
    headers_b = auth_headers(email="b@example.com")

    client.patch("/api/v1/users/me", json={"phone_number": "+5511999999999"}, headers=headers_a)

    resp = client.patch("/api/v1/users/me", json={"phone_number": "+5511999999999"}, headers=headers_b)
    assert resp.status_code == 409


def test_update_profile_can_clear_phone_number(client, auth_headers):
    headers = auth_headers()
    client.patch("/api/v1/users/me", json={"phone_number": "+5511999999999"}, headers=headers)

    resp = client.patch("/api/v1/users/me", json={"phone_number": None}, headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["phone_number"] is None


def test_update_profile_requires_auth(client):
    resp = client.patch("/api/v1/users/me", json={"phone_number": "+5511999999999"})
    assert resp.status_code == 401
