"""Answer endpoint: POST /answer.

Tenant injected server-side from auth; client-provided tenant_id ignored.
"""

from fastapi import APIRouter

from apps.api.schemas.requests import AnswerRequest
from apps.api.schemas.responses import AnswerResponse
from apps.api.services.answer import answer as answer_service
from apps.api.services.tenant_context import TenantId

router = APIRouter()


@router.post("/answer", response_model=AnswerResponse)
async def answer(body: AnswerRequest, tenant_id: TenantId) -> AnswerResponse:
    """Generate a grounded answer from retrieval. Tenant from auth only.
    If no evidence available, returns refused=true with refusal_reason='no_evidence'."""
    return answer_service(body.query, tenant_id)
