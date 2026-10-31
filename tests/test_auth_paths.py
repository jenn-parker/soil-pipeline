import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app import auth
from app.auth import Principal


def request() -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(),
        cookies={},
        url=SimpleNamespace(path="/api/v1/test"),
    )


def test_api_key_configuration_and_subject_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_API_KEYS", " key = soil:read ;bad;write-key=soil:write")
    assert auth._configured_api_keys() == {
        "key": frozenset({"soil:read"}),
        "write-key": frozenset({"soil:write"}),
    }
    assert auth._subject_for_key("secret") == auth._subject_for_key("secret")


def test_api_key_authentication_success_and_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_PROVIDER", "api_key")
    monkeypatch.setenv("AUTH_API_KEYS", "read-key=soil:read,soil:write")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="read-key")
    principal = asyncio.run(auth.get_current_principal(request(), credentials))
    assert principal.scopes == frozenset({"soil:read", "soil:write"})

    monkeypatch.delenv("AUTH_API_KEYS")
    with pytest.raises(HTTPException, match="not configured") as not_configured:
        asyncio.run(auth.get_current_principal(request(), credentials))
    assert not_configured.value.status_code == 503

    monkeypatch.setenv("AUTH_API_KEYS", "read-key=soil:read")
    with pytest.raises(HTTPException, match="bearer token"):
        asyncio.run(auth.get_current_principal(request(), None))
    with pytest.raises(HTTPException, match="Invalid bearer"):
        asyncio.run(
            auth.get_current_principal(
                request(),
                HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong"),
            )
        )


def test_auth_provider_and_scope_failures() -> None:
    principal = Principal(subject="subject", scopes=frozenset({"soil:read"}))
    dependency = auth.require_scope("soil:write")
    with pytest.raises(HTTPException, match="Missing required scope"):
        asyncio.run(dependency(principal))


def test_unsupported_auth_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_PROVIDER", "unknown")
    with pytest.raises(HTTPException, match="not supported") as unsupported:
        asyncio.run(auth.get_current_principal(request(), None))
    assert unsupported.value.status_code == 503
