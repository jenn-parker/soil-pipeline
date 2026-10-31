import logging
import base64
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from time import perf_counter
from time import time
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from app.api.routes import router
from app.logging_config import (
    actor_id_context,
    configure_logging,
    request_id_context,
)
from app.database import engine
from app.models.batch import SoilSampleBatch  # noqa: F401
from app.models.sample import Party, SampleProvenance  # noqa: F401
from app.models.soil import SoilTestResult  # noqa: F401

logger = logging.getLogger(__name__)
configure_logging()

OAUTH_STATE_COOKIE = "soil_oauth_state"
ACCESS_TOKEN_COOKIE = "soil_access_token"
REFRESH_TOKEN_COOKIE = "soil_refresh_token"
OAUTH_STATE_MAX_AGE = 600


app = FastAPI(
    title="Soil Metric Ingestion Pipeline API",
    description=(
        "Create individual soil samples or upload CSV batches. "
        "Batch uploads validate every row before saving any samples."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "Soil samples", "description": "Create and validate individual soil test records."},
        {"name": "Sample provenance", "description": "Manage sample ownership and collection details."},
        {"name": "Parties", "description": "Manage sample owners and collectors."},
        {"name": "File batches", "description": "Upload CSVs and review batch validation results."},
        {"name": "Reports", "description": "Location-based summaries of soil test results."},
        {"name": "Mapping", "description": "Map-ready GeoJSON for soil sample locations."},
    ],
)
app.include_router(router)


def _cognito_config() -> dict[str, str]:
    required = {
        "login_domain": os.getenv("COGNITO_LOGIN_DOMAIN", "").strip().rstrip("/"),
        "client_id": os.getenv("COGNITO_APP_CLIENT_ID", "").strip(),
        "redirect_uri": os.getenv("COGNITO_REDIRECT_URI", "http://localhost:8000/auth/callback").strip(),
        "session_secret": os.getenv("AUTH_SESSION_SECRET", "").strip(),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Cognito OAuth configuration is missing: {', '.join(missing)}")
    return required


def _oauth_scopes() -> str:
    return os.getenv(
        "COGNITO_SCOPES",
        "openid email https://soil-pipeline.local/soil:read "
        "https://soil-pipeline.local/soil:write https://soil-pipeline.local/batch:upload",
    )


def _url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _sign_oauth_state(payload: dict[str, str | int], secret: str) -> str:
    encoded_payload = _url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_url_encode(signature)}"


def _verify_oauth_state(value: str, secret: str) -> dict[str, str | int]:
    try:
        encoded_payload, encoded_signature = value.split(".", 1)
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        supplied_signature = base64.urlsafe_b64decode(encoded_signature + "===")
        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise ValueError("invalid OAuth state signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded_payload + "===").decode("utf-8"))
        if not isinstance(payload, dict) or int(payload["expires_at"]) < int(time()):
            raise ValueError("expired OAuth state")
        return payload
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("invalid OAuth state") from exc


def _cookie_secure() -> bool:
    return os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"


@app.get("/auth/login", include_in_schema=False)
async def auth_login() -> RedirectResponse:
    if os.getenv("AUTH_PROVIDER", "api_key").strip().lower() != "cognito":
        raise HTTPException(status_code=404, detail="Cognito authentication is not enabled")

    config = _cognito_config()
    state = secrets.token_urlsafe(32)
    verifier = _url_encode(secrets.token_bytes(32))
    challenge = _url_encode(hashlib.sha256(verifier.encode("ascii")).digest())
    signed_state = _sign_oauth_state(
        {
            "state": state,
            "verifier": verifier,
            "expires_at": int(time()) + OAUTH_STATE_MAX_AGE,
        },
        config["session_secret"],
    )
    query = urlencode(
        {
            "response_type": "code",
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "scope": _oauth_scopes(),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    response = RedirectResponse(f"{config['login_domain']}/oauth2/authorize?{query}")
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        signed_state,
        max_age=OAUTH_STATE_MAX_AGE,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/auth",
    )
    return response


@app.get("/auth/callback", include_in_schema=False)
async def auth_callback(request: Request, code: str | None = None, state: str | None = None) -> Response:
    if os.getenv("AUTH_PROVIDER", "api_key").strip().lower() != "cognito":
        raise HTTPException(status_code=404, detail="Cognito authentication is not enabled")
    if not code or not state:
        raise HTTPException(status_code=400, detail="OAuth callback is missing code or state")

    config = _cognito_config()
    state_cookie = request.cookies.get(OAUTH_STATE_COOKIE)
    if not state_cookie:
        raise HTTPException(status_code=400, detail="OAuth state cookie is missing")
    try:
        oauth_state = _verify_oauth_state(state_cookie, config["session_secret"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="OAuth state is invalid or expired") from exc
    if oauth_state.get("state") != state:
        raise HTTPException(status_code=400, detail="OAuth state does not match")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_response = await client.post(
                f"{config['login_domain']}/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": config["client_id"],
                    "code": code,
                    "redirect_uri": config["redirect_uri"],
                    "code_verifier": oauth_state["verifier"],
                },
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        logger.exception("auth.oauth_token_exchange_failed")
        raise HTTPException(status_code=502, detail="Cognito token exchange failed") from exc

    if token_response.is_error:
        logger.warning(
            "auth.oauth_token_exchange_rejected",
            extra={"status_code": token_response.status_code},
        )
        raise HTTPException(status_code=401, detail="Cognito authorization was rejected")
    tokens = token_response.json()
    access_token = tokens.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(status_code=502, detail="Cognito did not return an access token")

    response = RedirectResponse("/map")
    cookie_options = {
        "httponly": True,
        "secure": _cookie_secure(),
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        max_age=int(tokens.get("expires_in", 3600)),
        **cookie_options,
    )
    refresh_token = tokens.get("refresh_token")
    if isinstance(refresh_token, str) and refresh_token:
        response.set_cookie(
            REFRESH_TOKEN_COOKIE,
            refresh_token,
            httponly=True,
            secure=_cookie_secure(),
            samesite="lax",
            path="/auth",
        )
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/auth")
    logger.info("auth.login.completed")
    return response


@app.get("/auth/logout", include_in_schema=False)
async def auth_logout() -> RedirectResponse:
    response = RedirectResponse("/")
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/auth")
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/auth")
    if os.getenv("AUTH_PROVIDER", "api_key").strip().lower() == "cognito":
        try:
            config = _cognito_config()
            query = urlencode(
                {
                    "client_id": config["client_id"],
                    "logout_uri": os.getenv("COGNITO_LOGOUT_URI", "http://localhost:8000/").strip(),
                }
            )
            response = RedirectResponse(f"{config['login_domain']}/logout?{query}")
            response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
            response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/auth")
            response.delete_cookie(OAUTH_STATE_COOKIE, path="/auth")
        except RuntimeError:
            logger.warning("auth.logout_configuration_missing")
    return response


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID")
    if not request_id or len(request_id) > 128:
        request_id = str(uuid4())
    request_token = request_id_context.set(request_id)
    actor_token = actor_id_context.set(None)
    started_at = perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.info(
            "request.completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": getattr(locals().get("response"), "status_code", 500),
                "duration_ms": duration_ms,
            },
        )
        actor_id_context.reset(actor_token)
        request_id_context.reset(request_token)


@app.get("/map", include_in_schema=False)
async def sample_map() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "map.html")


@app.exception_handler(IntegrityError)
async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.info("database.constraint_rejected", extra={"method": request.method, "path": request.url.path})
    return JSONResponse(
        status_code=409,
        content={"detail": "The request conflicts with existing data or a database constraint."},
    )


@app.exception_handler(OperationalError)
async def handle_database_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
    logger.exception("database.unavailable", extra={"method": request.method, "path": request.url.path})
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is temporarily unavailable. Please try again."},
    )


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("database.operation_failed", extra={"method": request.method, "path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"detail": "The request could not be completed because of a database error."},
    )


@app.get("/health/live", include_in_schema=False)
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
async def readiness() -> dict[str, str]:
    started_at = perf_counter()
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception(
            "health.readiness_failed",
            extra={"duration_ms": round((perf_counter() - started_at) * 1000, 2)},
        )
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    logger.info(
        "health.readiness_succeeded",
        extra={"duration_ms": round((perf_counter() - started_at) * 1000, 2)},
    )
    return {"status": "ok"}
