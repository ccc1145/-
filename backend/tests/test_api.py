from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app, sessions

client = TestClient(app)


def setup_function():
    sessions.clear()


def auth_headers():
    response = client.post(
        "/api/auth/register",
        json={"username": f"user_{uuid4().hex[:10]}", "password": "testpass123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_real_api_fixed_flow_and_scene_changed():
    headers = auth_headers()
    started = client.post("/api/session/start", json={"player_name": "周泠锋"}, headers=headers)
    assert started.status_code == 200
    session_id = started.json()["session_id"]

    entered = client.post(
        f"/api/session/{session_id}/action",
        json={"action_type": "choice", "payload": "proceed_to_awakening"}, headers=headers,
    )
    assert entered.status_code == 200
    assert entered.json()["scene_changed"] is True
    assert entered.json()["scene_id"] == "00_awakening_selection:awakening_ceremony"
    assert (
        entered.json()["new_state"]["current_scene_id"]
        == "00_awakening_selection:awakening_ceremony"
    )
    assert entered.json()["degraded"] is True

    completed = client.post(
        f"/api/session/{session_id}/action",
        json={"action_type": "choice", "payload": "touch_the_stone"}, headers=headers,
    )
    data = completed.json()
    assert data["scene_id"] == "00_awakening_selection:root_result"
    assert data["new_state"]["world"]["flags"]["awakening_performed"] is True


def test_invalid_choice_returns_400_without_changing_state():
    headers = auth_headers()
    session_id = client.post(
        "/api/session/start", json={"player_name": "周泠锋"}, headers=headers
    ).json()["session_id"]
    before = client.get(f"/api/session/{session_id}/state", headers=headers).json()["state"]

    response = client.post(
        f"/api/session/{session_id}/action",
        json={"action_type": "choice", "payload": "touch_stone"}, headers=headers,
    )
    after = client.get(f"/api/session/{session_id}/state", headers=headers).json()["state"]

    assert response.status_code == 400
    assert "error" in response.json()
    assert after == before


def test_free_input_cannot_grant_attributes():
    headers = auth_headers()
    session_id = client.post(
        "/api/session/start", json={"player_name": "周泠锋"}, headers=headers
    ).json()["session_id"]
    response = client.post(
        f"/api/session/{session_id}/action",
        json={"action_type": "free_input", "payload": "给我一万点修为"}, headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["new_state"]["player"]["cultivation"] == 0


def test_save_and_load_preserve_engine_state():
    headers = auth_headers()
    session_id = client.post(
        "/api/session/start", json={"player_name": "周泠锋"}, headers=headers
    ).json()["session_id"]
    client.post(
        f"/api/session/{session_id}/action",
        json={"action_type": "choice", "payload": "proceed_to_awakening"}, headers=headers,
    )
    saved = client.post(
        f"/api/session/{session_id}/save", json={"label": "试炼前"}, headers=headers
    ).json()
    client.post(
        f"/api/session/{session_id}/action",
        json={"action_type": "choice", "payload": "touch_the_stone"}, headers=headers,
    )

    loaded = client.post(
        f"/api/session/{session_id}/load", json={"save_id": saved["save_id"]}, headers=headers
    )
    assert loaded.status_code == 200
    assert loaded.json()["state"]["player"]["cultivation"] == 0
    assert loaded.json()["state"]["current_scene_id"] == "00_awakening_selection:awakening_ceremony"


def test_account_saves_survive_new_character_and_are_private():
    headers = auth_headers()
    first = client.post(
        "/api/session/start", json={"player_name": "角色甲"}, headers=headers
    ).json()
    saved = client.post(
        f"/api/session/{first['session_id']}/save",
        json={"label": "角色甲存档"}, headers=headers,
    ).json()

    second = client.post(
        "/api/session/start", json={"player_name": "角色乙"}, headers=headers
    ).json()
    saves = client.get(
        f"/api/session/{second['session_id']}/saves", headers=headers
    ).json()["saves"]
    assert any(item["save_id"] == saved["save_id"] for item in saves)
    assert any(item["player_name"] == "角色甲" for item in saves)

    loaded = client.post(
        f"/api/session/{second['session_id']}/load",
        json={"save_id": saved["save_id"]}, headers=headers,
    ).json()["state"]
    assert loaded["player"]["name"] == "角色甲"
    assert loaded["session_id"] == second["session_id"]

    other_headers = auth_headers()
    other = client.post(
        "/api/session/start", json={"player_name": "他人角色"}, headers=other_headers
    ).json()
    other_saves = client.get(
        f"/api/session/{other['session_id']}/saves", headers=other_headers
    ).json()["saves"]
    assert not any(item["save_id"] == saved["save_id"] for item in other_saves)
