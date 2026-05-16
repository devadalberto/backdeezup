"""
Project-wide Pydantic v2 schemas.
Use these for input validation in ALL Django views (not just ninja endpoints).

Usage:
    from schemas import PaginationParams, ErrorResponse
    def my_view(request):
        try:
            params = PaginationParams.model_validate(request.GET.dict())
        except ValidationError as e:
            return JsonResponse(ErrorResponse(errors=e.errors()).model_dump(), status=422)
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class StrictSchema(BaseModel):
    """Base schema — forbids extra fields, strips whitespace from strings."""
    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
        "validate_default": True,
    }


class LooseSchema(BaseModel):
    """Base schema — ignores extra fields (safe for external API responses)."""
    model_config = {
        "extra": "ignore",
        "str_strip_whitespace": True,
    }


# ── Common primitives ─────────────────────────────────────────────────────────

class PaginationParams(LooseSchema):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


class ErrorDetail(LooseSchema):
    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ErrorResponse(LooseSchema):
    errors: list[ErrorDetail | dict[str, Any]]
    message: str = "Validation failed"


class SuccessResponse(LooseSchema):
    message: str = "OK"
    data: Optional[dict[str, Any]] = None


# ── Gmail schemas ─────────────────────────────────────────────────────────────

class GmailDiscoverParams(StrictSchema):
    q: str = Field(default="", description="Gmail search query")
    max_pages: int = Field(default=20, ge=1, le=100)
    page_size: int = Field(default=500, ge=1, le=500)


class GmailSyncParams(StrictSchema):
    limit: int = Field(default=100, ge=1, le=1000)


class RuleConditionSchema(StrictSchema):
    field: str
    operator: str
    value: str = ""
    logic: str = "AND"
    order: int = Field(default=0, ge=0)

    @field_validator("logic")
    @classmethod
    def validate_logic(cls, v: str) -> str:
        if v not in ("AND", "OR"):
            raise ValueError("logic must be AND or OR")
        return v


class RuleBuilderPayload(StrictSchema):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    action: str = "trash"
    label_name: str = ""
    min_age_days: int = Field(default=0, ge=0)
    enabled: bool = False
    conditions: list[RuleConditionSchema] = Field(default_factory=list)

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"trash", "star", "label", "archive"}
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}")
        return v


# ── Drive / Media schemas ─────────────────────────────────────────────────────

class DriveDiscoverParams(StrictSchema):
    page_size: int = Field(default=200, ge=1, le=1000)
    max_pages: int = Field(default=10, ge=1, le=100)


class DriveDownloadParams(StrictSchema):
    limit: int = Field(default=100, ge=1, le=1000)


# ── Media Vault schemas ───────────────────────────────────────────────────────

class MediaDecisionPayload(StrictSchema):
    item_type: str
    item_id: int = Field(..., ge=1)
    action: str

    @field_validator("item_type")
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        if v not in ("image", "video", "document"):
            raise ValueError("item_type must be image, video, or document")
        return v

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ("keep", "delete", "undecided"):
            raise ValueError("action must be keep, delete, or undecided")
        return v


class BulkMediaDecisionPayload(StrictSchema):
    decisions: list[MediaDecisionPayload]
    notes: str = ""
