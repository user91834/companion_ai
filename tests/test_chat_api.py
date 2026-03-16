# tests/test_chat_api.py
import os
import pytest
from httpx import ASGITransport, AsyncClient

# AUTH_DISABLED=1 and path user_id so no token needed
os.environ["AUTH_DISABLED"] = "1"

@pytest.fixture
def client():
    pytest.importorskip("eng_to_ipa", reason="eng_to_ipa required for server")
    from server import app
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_ping(client):
    r = await client.get("/ping")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert "ts_ms" in data


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True


@pytest.mark.asyncio
async def test_chat_send_requires_auth_or_dev_header(client):
    # With AUTH_DISABLED=1, path user_id is used
    r = await client.post(
        "/chat/test-user-123/send",
        json={"text": "Hello"},
    )
    # 200 = success (user created and message processed)
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert "reply_plan" in data
    assert "messages" in data


@pytest.mark.asyncio
async def test_get_chat(client):
    r = await client.get("/chat/test-user-456")
    assert r.status_code == 200
    data = r.json()
    assert "messages" in data
    assert "emotion_v2" in data


@pytest.mark.asyncio
async def test_v1_prefix(client):
    r = await client.get("/v1/ping")
    assert r.status_code == 200
    assert r.json().get("ok") is True
