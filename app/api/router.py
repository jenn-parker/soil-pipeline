from fastapi import APIRouter, Depends

from app.auth import require_scope

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_scope("soil:read"))])

from app.api import access, batches, maps, provenance, reports, samples  # noqa: E402,F401

