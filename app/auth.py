"""Bearer API-key authentication and scope authorization.

API keys are intentionally a small first-pass auth mechanism for the demo. In
production, this dependency can be replaced with an OIDC/JWT validator (for
example, AWS Cognito) without changing route-level scope declarations.
"""

from __future__ import annotations

import hashlib
import logging
import os
import asyncio
import httpx
from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import DecodeError, InvalidTokenError, PyJWKClient, decode

from app.logging_config import actor_id_context

bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)
_jwk_clients: dict[str, PyJWKClient] = {}


@dataclass(frozen=True)
class Principal:
    subject: str
    scopes: frozenset[str]
    email: str | None = None


def _configured_api_keys() -> dict[str, frozenset[str]]:
    """Read ``key=scope,scope;key2=scope`` from the environment."""

    configured = os.getenv("AUTH_API_KEYS", "")
    keys: dict[str, frozenset[str]] = {}
    for item in configured.split(";"):
        if not item.strip() or "=" not in item:
            continue
        key, raw_scopes = item.split("=", 1)
        key = key.strip()
        scopes = frozenset(scope.strip() for scope in raw_scopes.split(",") if scope.strip())
        if key and scopes:
            keys[key] = scopes
    return keys


def _subject_for_key(api_key: str) -> str:
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]
    return f"api-key:{digest}"


def _auth_provider() -> str:
    return os.getenv("AUTH_PROVIDER", "api_key").strip().lower()


def _cognito_issuer() -> str:
    issuer = os.getenv("COGNITO_ISSUER", "").strip().rstrip("/")
    if not issuer:
        raise RuntimeError("COGNITO_ISSUER is not configured")
    return issuer


def _cognito_jwk_client(issuer: str) -> PyJWKClient:
    client = _jwk_clients.get(issuer)
    if client is None:
        client = PyJWKClient(f"{issuer}/.well-known/jwks.json")
        _jwk_clients[issuer] = client
    return client


def _cognito_scopes(claims: dict[str, object]) -> frozenset[str]:
    raw_scope = claims.get("scope", "")
    if not isinstance(raw_scope, str):
        return frozenset()

    scopes: set[str] = set()
    for scope in raw_scope.split():
        scopes.add(scope)
        scopes.add(scope.rsplit("/", 1)[-1])
    return frozenset(scopes)


async def _authenticate_cognito(token: str) -> Principal:
    issuer = _cognito_issuer()
    app_client_id = os.getenv("COGNITO_APP_CLIENT_ID", "").strip()
    if not app_client_id:
        raise RuntimeError("COGNITO_APP_CLIENT_ID is not configured")

    try:
        signing_key = await asyncio.to_thread(
            _cognito_jwk_client(issuer).get_signing_key_from_jwt,
            token,
        )
        claims = decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={
                "require": ["exp", "iat", "iss", "sub", "token_use"],
                # Cognito access tokens identify the app client with client_id;
                # the aud claim is used by ID tokens instead.
                "verify_aud": False,
            },
        )
    except (DecodeError, InvalidTokenError, ValueError) as exc:
        raise ValueError("invalid Cognito access token") from exc

    if claims.get("token_use") != "access":
        raise ValueError("Cognito token is not an access token")
    if claims.get("client_id") != app_client_id:
        raise ValueError("Cognito token was issued to a different app client")

    email = None
    login_domain = os.getenv("COGNITO_LOGIN_DOMAIN", "").strip().rstrip("/")
    if login_domain:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                userinfo_response = await client.get(
                    f"{login_domain}/oauth2/userInfo",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if userinfo_response.is_success:
                userinfo = userinfo_response.json()
                if isinstance(userinfo.get("email"), str):
                    email = userinfo["email"].strip().lower()
        except (httpx.HTTPError, ValueError):
            logger.info("auth.userinfo.unavailable", extra={"subject": str(claims["sub"])})

    return Principal(
        subject=str(claims["sub"]),
        scopes=_cognito_scopes(claims),
        email=email,
    )


async def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    provider = _auth_provider()
    if provider == "cognito":
        token = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else request.cookies.get("soil_access_token")
        if not token:
            logger.warning("auth.failed", extra={"path": request.url.path, "reason": "missing_bearer_token"})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A Cognito bearer token is required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            principal = await _authenticate_cognito(token)
        except (RuntimeError, ValueError) as exc:
            logger.warning(
                "auth.failed",
                extra={"path": request.url.path, "reason": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Cognito access token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        actor_id_context.set(principal.subject)
        request.state.principal = principal
        return principal

    if provider != "api_key":
        logger.error(
            "auth.unsupported_provider",
            extra={"path": request.url.path, "provider": provider},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication provider is not supported",
        )

    configured_keys = _configured_api_keys()
    if not configured_keys:
        logger.error("auth.not_configured", extra={"path": request.url.path})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        logger.warning("auth.failed", extra={"path": request.url.path, "reason": "missing_bearer_token"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A bearer token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scopes = configured_keys.get(credentials.credentials)
    if scopes is None:
        logger.warning("auth.failed", extra={"path": request.url.path, "reason": "invalid_bearer_token"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    principal = Principal(subject=_subject_for_key(credentials.credentials), scopes=scopes)
    actor_id_context.set(principal.subject)
    request.state.principal = principal
    return principal


def require_scope(scope: str) -> Callable:
    async def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if "*" not in principal.scopes and scope not in principal.scopes:
            logger.warning("authz.denied", extra={"required_scope": scope})
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {scope}",
            )
        return principal

    return dependency
