def _create_goal(client, headers, target_amount=1000.0, target_date=None):
    payload = {"name": "Reserva de emergência", "target_amount": target_amount}
    if target_date is not None:
        payload["target_date"] = target_date
    resp = client.post("/api/v1/goals", json=payload, headers=headers)
    return resp


def test_create_list_get_update_goal(client, auth_headers):
    headers = auth_headers()

    resp = _create_goal(client, headers)
    assert resp.status_code == 201
    goal = resp.get_json()["data"]
    goal_id = goal["id"]
    assert goal["current_amount"] == "0.00"
    assert goal["status"] == "in_progress"

    resp = client.get("/api/v1/goals", headers=headers)
    assert resp.get_json()["meta"]["total"] == 1

    resp = client.get(f"/api/v1/goals/{goal_id}", headers=headers)
    assert resp.status_code == 200

    resp = client.patch(
        f"/api/v1/goals/{goal_id}", json={"name": "Reserva renovada"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["name"] == "Reserva renovada"


def test_contribute_increments_current_amount(client, auth_headers):
    headers = auth_headers()
    goal_id = _create_goal(client, headers, target_amount=1000.0).get_json()["data"]["id"]

    resp = client.post(
        f"/api/v1/goals/{goal_id}/contribute", json={"amount": 300.0}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["current_amount"] == "300.00"
    assert resp.get_json()["data"]["status"] == "in_progress"


def test_contribute_reaching_target_marks_achieved(client, auth_headers):
    headers = auth_headers()
    goal_id = _create_goal(client, headers, target_amount=500.0).get_json()["data"]["id"]

    client.post(
        f"/api/v1/goals/{goal_id}/contribute", json={"amount": 300.0}, headers=headers
    )
    resp = client.post(
        f"/api/v1/goals/{goal_id}/contribute", json={"amount": 300.0}, headers=headers
    )

    body = resp.get_json()["data"]
    assert body["current_amount"] == "600.00"
    assert body["status"] == "achieved"


def test_cannot_contribute_to_non_in_progress_goal(client, auth_headers):
    headers = auth_headers()
    goal_id = _create_goal(client, headers, target_amount=500.0).get_json()["data"]["id"]

    client.patch(f"/api/v1/goals/{goal_id}", json={"status": "abandoned"}, headers=headers)

    resp = client.post(
        f"/api/v1/goals/{goal_id}/contribute", json={"amount": 100.0}, headers=headers
    )
    assert resp.status_code == 422


def test_delete_goal(client, auth_headers):
    headers = auth_headers()
    goal_id = _create_goal(client, headers).get_json()["data"]["id"]

    resp = client.delete(f"/api/v1/goals/{goal_id}", headers=headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/v1/goals/{goal_id}", headers=headers)
    assert resp.status_code == 404


def test_cannot_access_goal_from_another_user(client, auth_headers):
    headers_a = auth_headers(email="a@example.com")
    headers_b = auth_headers(email="b@example.com")
    goal_id = _create_goal(client, headers_a).get_json()["data"]["id"]

    resp = client.get(f"/api/v1/goals/{goal_id}", headers=headers_b)
    assert resp.status_code == 404
