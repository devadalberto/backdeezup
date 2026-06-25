"""
Project-wide Pydantic v2 schemas. Use these for input validation in ALL Django views,
API endpoints, and task functions. Never construct raw dicts for structured data.
"""
from typing import Optional
from pydantic import BaseModel, field_validator


class LooseSchema(BaseModel):
    """Base schema — ignores extra fields (safe for external API responses)."""
    model_config = {"extra": "ignore", "str_strip_whitespace": True}


class StrictSchema(BaseModel):
    """Base schema — forbids extra fields, strips whitespace from strings."""
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class MetadataSnapshot(LooseSchema):
    """Frozen snapshot of a GmailMessage at deletion time.

    Stored in GmailMessage.metadata_snapshot (JSONField).
    Always use .model_dump() to serialize — never construct raw dicts.
    """
    subject: str = ""
    from_address: str = ""
    to_address: str = ""
    date: Optional[str] = None
    labels: list[str] = []
    size_estimate: int = 0

    @field_validator("labels", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if v is None:
            return []
        return list(v)

    @field_validator("size_estimate", mode="before")
    @classmethod
    def ensure_int(cls, v):
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0


def snapshot_from_message(msg) -> dict:
    """Build a validated MetadataSnapshot dict from a GmailMessage instance."""
    return MetadataSnapshot(
        subject=msg.subject or "",
        from_address=msg.from_address or "",
        to_address=msg.to_address or "",
        date=str(msg.date) if msg.date else None,
        labels=msg.labels or [],
        size_estimate=msg.size_estimate or 0,
    ).model_dump()
