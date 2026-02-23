"""Request schemas for API endpoints. tenant_id is never accepted in payload."""

from pydantic import BaseModel, ConfigDict, Field


class RetrieveRequest(BaseModel):
    """Request body for POST /retrieve/ac."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., description="Search query")
    k: int = Field(20, description="Number of candidates to return")


class RetrieveECRequest(BaseModel):
    """Request body for POST /retrieve/ec."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., description="Search query")
    k: int = Field(20, description="Number of entities to return")
    n: int = Field(5, ge=0, le=20, description="Max mentions per entity")


class AnswerRequest(BaseModel):
    """Request body for POST /answer."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., description="Question to answer")
