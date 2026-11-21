import asyncio
import json
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app import main
from app.logging_config import request_id_context


def request() -> SimpleNamespace:
    return SimpleNamespace(method="POST", url=SimpleNamespace(path="/api/v1/soil-samples"))


def response_body(response: object) -> dict[str, object]:
    return json.loads(response.body)  # type: ignore[attr-defined]


def test_check_constraint_errors_are_validation_errors_with_request_id() -> None:
    token = request_id_context.set("request-123")
    try:
        error = IntegrityError("INSERT", {}, Exception("violates check constraint ck_soil_samples_soil_ph_range"))
        response = asyncio.run(main.handle_integrity_error(request(), error))
    finally:
        request_id_context.reset(token)

    assert response.status_code == 422
    assert response_body(response) == {
        "detail": "The request contains values that violate a data constraint.",
        "request_id": "request-123",
    }


def test_unique_constraint_errors_remain_conflicts() -> None:
    error = IntegrityError("INSERT", {}, Exception("duplicate key value violates unique constraint"))
    response = asyncio.run(main.handle_integrity_error(request(), error))

    assert response.status_code == 409
    assert response_body(response)["detail"] == "The request conflicts with existing data or a database constraint."
