import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.auth import _cognito_scopes
from app.database import get_db_session


def make_client(api_keys: str, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AUTH_API_KEYS", api_keys)
    app = FastAPI()
    app.include_router(router)

    async def override_db_session():
        yield object()

    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app)


def test_api_requires_a_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    with make_client("read-key=soil:read", monkeypatch) as client:
        response = client.get("/api/v1/reports/soil-ranges")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_api_rejects_invalid_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    with make_client("read-key=soil:read", monkeypatch) as client:
        response = client.get(
            "/api/v1/reports/soil-ranges",
            headers={"Authorization": "Bearer wrong-key"},
        )

    assert response.status_code == 401


def test_write_route_requires_write_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    with make_client("read-key=soil:read", monkeypatch) as client:
        response = client.post(
            "/api/v1/soil-samples",
            headers={"Authorization": "Bearer read-key"},
            json={"sample_id": "SAMPLE-1"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing required scope: soil:write"


def test_cognito_scopes_include_short_custom_scope_names() -> None:
    scopes = _cognito_scopes(
        {"scope": "openid https://soil-pipeline.local/soil:read batch:upload"}
    )

    assert "openid" in scopes
    assert "https://soil-pipeline.local/soil:read" in scopes
    assert "soil:read" in scopes
    assert "batch:upload" in scopes
