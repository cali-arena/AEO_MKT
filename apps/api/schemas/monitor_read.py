"""Monitor read endpoints response schemas."""

from pydantic import BaseModel, ConfigDict, Field


class LeakageLatestResponse(BaseModel):
    """Response for leakage latest check endpoint."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    ok: bool
    last_checked_at: str
    details_json: dict | list | None = Field(None, description="Optional details from last check")
