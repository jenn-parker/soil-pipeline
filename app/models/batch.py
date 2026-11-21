from datetime import datetime, timezone
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SoilSampleBatch(Base):
    __tablename__ = "soil_upload_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'completed', 'rejected', 'failed')",
            name="ck_soil_upload_batches_status",
        ),
        CheckConstraint(
            "archive_status IN ('pending', 'archived', 'failed', 'abandoned')",
            name="ck_soil_upload_batches_archive_status",
        ),
        CheckConstraint(
            "total_rows >= 0 AND accepted_rows >= 0 AND rejected_rows >= 0 "
            "AND accepted_rows + rejected_rows <= total_rows",
            name="ck_soil_upload_batches_row_counts",
        ),
        CheckConstraint(
            "status = 'processing' OR accepted_rows + rejected_rows = total_rows",
            name="ck_soil_upload_batches_final_row_counts",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # Nullable for batches created before ownership tracking was introduced.
    created_by_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    archive_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    archive_generation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    archive_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive_fenced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive_fence_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="processing")
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
