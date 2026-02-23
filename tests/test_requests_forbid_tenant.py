"""Verify request schemas reject tenant_id in payload."""

import pytest
from pydantic import ValidationError

from apps.api.schemas.requests import AnswerRequest, RetrieveRequest


def test_retrieve_request_rejects_tenant_id() -> None:
    with pytest.raises(ValidationError):
        RetrieveRequest(query="q", k=10, tenant_id="t1")


def test_retrieve_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        RetrieveRequest(query="q", k=10, extra="x")


def test_answer_request_rejects_tenant_id() -> None:
    with pytest.raises(ValidationError):
        AnswerRequest(query="q", tenant_id="t1")


def test_retrieve_request_accepts_valid_payload() -> None:
    r = RetrieveRequest(query="q", k=5)
    assert r.query == "q"
    assert r.k == 5


def test_answer_request_accepts_valid_payload() -> None:
    r = AnswerRequest(query="q")
    assert r.query == "q"
