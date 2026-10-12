from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class LinkCreate(BaseModel):
    url: HttpUrl
    code: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_-]{3,32}$",
        description="Optional custom short code. Generated when omitted.",
    )


class LinkOut(BaseModel):
    code: str
    short_url: str
    target_url: str
    clicks: int
    created_at: datetime
