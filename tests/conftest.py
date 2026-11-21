from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.database import get_db_session


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("AUTH_PROVIDER", "api_key")
    monkeypatch.setenv("AUTH_API_KEYS", "test-key=soil:read,soil:write,batch:upload")
    app = FastAPI()
    app.include_router(router)

    async def override_db_session():
        yield object()

    app.dependency_overrides[get_db_session] = override_db_session
    with TestClient(app, headers={"Authorization": "Bearer test-key"}) as test_client:
        yield test_client
