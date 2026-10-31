from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr


class SampleAccessGrant(BaseModel):
    email: EmailStr
    role: Literal["viewer", "editor"] = "viewer"


class SampleAccessRead(BaseModel):
    email: EmailStr
    role: Literal["viewer", "editor"]
    granted_at: datetime
