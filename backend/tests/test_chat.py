"""End-to-end chat flow — register → login → chat, agent mocked."""

import pytest


@pytest.fixture
async def auth_token(http_client):
    """Register a user and return a valid JWT."""
    reg = await http_client.post(
        "/auth/register",
        json={"email": "traveller@example.com", "password": "strongpass99"},
    )
    assert reg.status_code == 201

    login = await http_client.post(
        "/auth/login",
        data={"username": "traveller@example.com", "password": "strongpass99"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


async def test_me_returns_authenticated_user(http_client, auth_token):
    res = await http_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "id" in body
    assert body["email"] == "traveller@example.com"
    assert body["is_active"] is True


async def test_chat_returns_expected_shape(http_client, auth_token, mock_agent):
    res = await http_client.post(
        "/chat",
        json={"question": "Plan a trip to Paris"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["answer"] == "Paris is a wonderful destination!"
    assert "session_id" in data
    assert isinstance(data["tool_calls"], list)

    # Agent was invoked exactly once with our question
    mock_agent.ainvoke.assert_called_once()
    call_messages = mock_agent.ainvoke.call_args[0][0]["messages"]
    assert call_messages[-1].content == "Plan a trip to Paris"


async def test_chat_reuses_session(http_client, auth_token, mock_agent):
    # First message — creates a new session
    res1 = await http_client.post(
        "/chat",
        json={"question": "I want to go to Tokyo"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res1.status_code == 200
    session_id = res1.json()["session_id"]

    mock_agent.ainvoke.reset_mock()

    # Second message — reuses the same session
    res2 = await http_client.post(
        "/chat",
        json={"question": "What about the budget?", "session_id": session_id},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res2.status_code == 200
    assert res2.json()["session_id"] == session_id
    mock_agent.ainvoke.assert_called_once()


async def test_chat_rejects_unauthenticated(http_client):
    res = await http_client.post("/chat", json={"question": "Hello"})
    assert res.status_code == 401


async def test_sessions_list_after_chat(http_client, auth_token):
    await http_client.post(
        "/chat",
        json={"question": "Best beaches in Bali?"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    res = await http_client.get("/sessions", headers={"Authorization": f"Bearer {auth_token}"})
    assert res.status_code == 200
    sessions = res.json()
    assert isinstance(sessions, list)
    assert len(sessions) >= 1
    assert "id" in sessions[0]
    assert "title" in sessions[0]
