import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api import routes
from app.auth import Principal
from app.models.soil import SoilTestResult
from app.schemas.access import SampleAccessGrant
from app.schemas.soil import SoilTestResultCreate


def request_for(principal: Principal) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(principal=principal))


def sample(
    *,
    owner: str = "owner-sub",
    archived: bool = False,
) -> SoilTestResult:
    return SoilTestResult(
        id=7,
        sample_id="FIELD-7",
        created_by_sub=owner,
        archived_at=datetime(2026, 1, 1, tzinfo=timezone.utc) if archived else None,
        archived_by_sub="owner-sub" if archived else None,
        sampled_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        latitude=42.7,
        longitude=-92.4,
    )


def test_make_wgs84_point_handles_missing_coordinates() -> None:
    assert routes.make_wgs84_point(None, -92.4) is None
    assert str(routes.make_wgs84_point(42.7, -92.4)) == "POINT(-92.4 42.7)"


def test_owned_sample_helper_returns_sample_and_rejects_missing_or_foreign() -> None:
    owner = Principal(subject="owner-sub", scopes=frozenset())

    db = MagicMock()
    db.scalar = AsyncMock(return_value=sample())
    assert asyncio.run(routes._get_owned_sample("FIELD-7", owner, db)).sample_id == "FIELD-7"

    db.scalar = AsyncMock(return_value=None)
    with pytest.raises(HTTPException, match="was not found") as missing:
        asyncio.run(routes._get_owned_sample("FIELD-7", owner, db))
    assert missing.value.status_code == 404

    db.scalar = AsyncMock(return_value=sample(owner="other-sub"))
    with pytest.raises(HTTPException, match="Only the sample owner") as foreign:
        asyncio.run(routes._get_owned_sample("FIELD-7", owner, db))
    assert foreign.value.status_code == 403


def test_editable_sample_allows_owner_and_shared_editor() -> None:
    owner = Principal(subject="owner-sub", scopes=frozenset())
    editor = Principal(subject="editor-sub", scopes=frozenset(), email="editor@example.com")

    owner_db = MagicMock()
    owner_db.scalar = AsyncMock(return_value=sample())
    assert asyncio.run(routes._get_editable_sample("FIELD-7", owner, owner_db)).sample_id == "FIELD-7"

    editor_db = MagicMock()
    editor_db.scalar = AsyncMock(side_effect=[sample(), 1])
    assert asyncio.run(routes._get_editable_sample("FIELD-7", editor, editor_db)).sample_id == "FIELD-7"


def test_editable_sample_rejects_archived_and_unauthorized_users() -> None:
    principal = Principal(subject="other-sub", scopes=frozenset(), email="other@example.com")

    archived_db = MagicMock()
    archived_db.scalar = AsyncMock(return_value=sample(archived=True))
    with pytest.raises(HTTPException, match="archived") as archived:
        asyncio.run(routes._get_editable_sample("FIELD-7", principal, archived_db))
    assert archived.value.status_code == 409

    denied_db = MagicMock()
    denied_db.scalar = AsyncMock(side_effect=[sample(), None])
    with pytest.raises(HTTPException, match="edit access") as denied:
        asyncio.run(routes._get_editable_sample("FIELD-7", principal, denied_db))
    assert denied.value.status_code == 403


def test_list_owned_samples_can_include_archived_records() -> None:
    principal = Principal(subject="owner-sub", scopes=frozenset())
    records = [sample(), sample(archived=True)]
    db = MagicMock()
    db.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: records))

    result = asyncio.run(routes.list_owned_soil_samples(request=request_for(principal), db=db))

    assert result == records
    db.scalars.assert_awaited_once()


def test_create_update_read_and_delete_sample_paths() -> None:
    principal = Principal(subject="owner-sub", scopes=frozenset())
    request = request_for(principal)
    create_request = SoilTestResultCreate(
        sample_id="FIELD-7",
        sampled_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        latitude=42.7,
        longitude=-92.4,
        soil_ph=6.5,
    )

    db = MagicMock()
    db.scalar = AsyncMock(side_effect=[None, None])
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    created = asyncio.run(routes.create_soil_test_result(request, create_request, db))
    assert created.created_by_sub == "owner-sub"
    db.add.assert_called_once()

    db.scalar = AsyncMock(return_value=created)
    updated_request = create_request.model_copy(update={"field_name": "North Field", "soil_ph": Decimal("6.8")})
    updated = asyncio.run(routes.update_soil_test_result(request, "FIELD-7", updated_request, db))
    assert updated.field_name == "North Field"
    assert updated.soil_ph == Decimal("6.8")

    db.scalar = AsyncMock(return_value=created)
    fetched = asyncio.run(routes.get_soil_test_result("FIELD-7", db, request))
    assert fetched.sample_id == "FIELD-7"

    db.delete = AsyncMock()
    response = asyncio.run(routes.delete_soil_test_result(request, "FIELD-7", db))
    assert response.status_code == 204
    db.delete.assert_awaited_once_with(created)

    with pytest.raises(HTTPException, match="must match"):
        asyncio.run(routes.update_soil_test_result(request, "OTHER", create_request, db))


def test_create_sample_rejects_duplicate_id() -> None:
    principal = Principal(subject="owner-sub", scopes=frozenset())
    db = MagicMock()
    db.scalar = AsyncMock(return_value=1)
    with pytest.raises(HTTPException, match="already exists"):
        asyncio.run(
            routes.create_soil_test_result(
                request_for(principal),
                SoilTestResultCreate(sample_id="FIELD-7"),
                db,
            )
        )


def test_archive_and_restore_are_owner_only_and_archive_is_idempotent() -> None:
    principal = Principal(subject="owner-sub", scopes=frozenset())
    db = MagicMock()
    db.scalar = AsyncMock(return_value=sample())
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    archived = asyncio.run(routes.archive_soil_test_result(request_for(principal), "FIELD-7", db))
    assert archived.archived_at is not None
    assert archived.archived_by_sub == "owner-sub"
    db.flush.assert_awaited_once()

    db.scalar = AsyncMock(return_value=sample(archived=True))
    db.flush.reset_mock()
    asyncio.run(routes.archive_soil_test_result(request_for(principal), "FIELD-7", db))
    db.flush.assert_not_awaited()

    restored = asyncio.run(routes.restore_soil_test_result(request_for(principal), "FIELD-7", db))
    assert restored.archived_at is None
    assert restored.archived_by_sub is None


def test_access_grant_list_and_revoke_cover_new_existing_and_missing_records() -> None:
    principal = Principal(subject="owner-sub", scopes=frozenset(), email="owner@example.com")
    created_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    db = MagicMock()
    db.scalar = AsyncMock(side_effect=[sample(), None])
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()

    async def refresh(record: object) -> None:
        if getattr(record, "created_at", None) is None:
            record.created_at = created_at

    db.refresh = AsyncMock(side_effect=refresh)

    granted = asyncio.run(
        routes.grant_sample_access(
            request_for(principal),
            "FIELD-7",
            SampleAccessGrant(email="Viewer@Example.com", role="viewer"),
            db,
        )
    )
    assert granted.email == "viewer@example.com"
    db.add.assert_called_once()

    existing = SimpleNamespace(
        soil_sample_id=7,
        user_email="viewer@example.com",
        role="viewer",
        granted_by_sub="old-owner",
        created_at=created_at,
    )
    db.scalar = AsyncMock(side_effect=[sample(), existing])
    updated = asyncio.run(
        routes.grant_sample_access(
            request_for(principal),
            "FIELD-7",
            SampleAccessGrant(email="viewer@example.com", role="editor"),
            db,
        )
    )
    assert updated.role == "editor"
    assert existing.granted_by_sub == "owner-sub"

    db.scalar = AsyncMock(return_value=sample())
    db.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: [existing]))
    access = asyncio.run(routes.list_sample_access(request_for(principal), "FIELD-7", db))
    assert access[0].email == "viewer@example.com"

    db.scalar = AsyncMock(side_effect=[sample(), existing])
    response = asyncio.run(routes.revoke_sample_access(request_for(principal), "FIELD-7", "VIEWER@example.com", db))
    assert response.status_code == 204
    db.delete.assert_called_once_with(existing)

    db.scalar = AsyncMock(side_effect=[sample(), None])
    asyncio.run(routes.revoke_sample_access(request_for(principal), "FIELD-7", "missing@example.com", db))
    assert db.delete.call_count == 1

    db.scalar = AsyncMock(side_effect=[sample(), None])
    with pytest.raises(HTTPException, match="owner already has access"):
        asyncio.run(
            routes.grant_sample_access(
                request_for(principal),
                "FIELD-7",
                SampleAccessGrant(email="OWNER@example.com"),
                db,
            )
        )
