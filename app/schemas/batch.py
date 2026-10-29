from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BatchRowError(BaseModel):
    row: int
    errors: list[dict[str, str]]


class SoilSampleBatchRead(BaseModel):
    id: int
    filename: str
    source_bucket: str | None = None
    source_key: str | None = None
    status: str
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    errors: list[BatchRowError]
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
