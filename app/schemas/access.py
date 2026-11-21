from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class SampleAccessGrant(BaseModel):
    email: EmailStr
    user_sub: str | None = Field(None, min_length=1, max_length=255)
    role: Literal["viewer", "editor"] = "viewer"


class SampleAccessRead(BaseModel):
    email: EmailStr
    user_sub: str | None = Field(None, max_length=255)
    role: Literal["viewer", "editor"]
    granted_at: datetime
