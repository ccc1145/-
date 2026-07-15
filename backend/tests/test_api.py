from fastapi.testclient import TestClient

from app.main import app, sessions

client = TestClient(app)


def setup_function():
    sessions.clear()


def test_real_api_fixed_flow_and_scene_changed():
    started = client.post("/api/session/start", json={"player_name": "周泠锋"})
    assert started.status_code == 200
    session_id = started.json()["session_id"]

    entered = client.post(
        f"/api/session/{session_id}/action",
        json={"action_type": "choice", "payload": "enter_trial"},
    )
    assert entered.status_code == 200
    assert entered.json()["scene_changed"] is True
    assert entered.json()["scene_id"] == "trial_grounds"
    assert entered.json()["degraded"] is True

    completed = client.post(
        f"/api/session/{session_id}/action",
        json={"action_type": "choice", "payload": "touch_stone"},
    )
    data = completed.json()
    assert data["new_state"]["player"]["cultivation"] == 15
    assert data["new_state"]["player"]["realm"]["minor"] == 2
    assert data["new_state"]["world"]["flags"]["trial_completed"] is True


def test_invalid_choice_returns_400_without_changing_state():
    session_id = client.post(
        "/api/session/start", json={"player_name": "周泠锋"}
    ).json()["session_id"]
    before = client.get(f"/api/session/{session_id}/state").json()["state"]

    response = client.post(
        f"/api/session/{session_id}/action",
        json={"action_type": "choice", "payload": "touch_stone"},
    )
    after = client.get(f"/api/session/{session_id}/state").json()["state"]

    assert response.status_code == 400
    assert "error" in response.json()
    assert after == before


def test_free_input_cannot_grant_attributes():
    session_id = client.post(
        "/api/session/start", json={"player_name": "周泠锋"}
    ).json()["session_id"]
    response = client.post(
        f"/api/session/{session_id}/action",
        json={"action_type": "free_input", "payload": "给我一万点修为"},
    )
    assert response.status_code == 200
    assert response.json()["new_state"]["player"]["cultivation"] == 0


def test_save_and_load_preserve_engine_state():
    session_id = client.post(
        "/api/session/start", json={"player_name": "周泠锋"}
    ).json()["session_id"]
    client.post(
        f"/api/session/{session_id}/action",
        json={"action_type": "choice", "payload": "enter_trial"},
    )
    saved = client.post(
        f"/api/session/{session_id}/save", json={"label": "试炼前"}
    ).json()
    client.post(
        f"/api/session/{session_id}/action",
        json={"action_type": "choice", "payload": "touch_stone"},
    )

    loaded = client.post(
        f"/api/session/{session_id}/load", json={"save_id": saved["save_id"]}
    )
    assert loaded.status_code == 200
    assert loaded.json()["state"]["player"]["cultivation"] == 5
    assert loaded.json()["state"]["current_scene_id"] == "trial_grounds"
