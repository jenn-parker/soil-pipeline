from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from app.api.routes import router
from app.database import Base, engine
from app.models.batch import SoilSampleBatch  # noqa: F401
from app.models.sample import Party, SampleProvenance  # noqa: F401
from app.models.soil import SoilTestResult  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


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
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/map", include_in_schema=False)
async def sample_map() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "map.html")


@app.exception_handler(IntegrityError)
async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.info("Database constraint rejected request %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=409,
        content={"detail": "The request conflicts with existing data or a database constraint."},
    )


@app.exception_handler(OperationalError)
async def handle_database_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
    logger.exception("Database unavailable while handling %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is temporarily unavailable. Please try again."},
    )


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database operation failed while handling %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "The request could not be completed because of a database error."},
    )


@app.get("/health/live", include_in_schema=False)
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
async def readiness() -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return {"status": "ok"}
