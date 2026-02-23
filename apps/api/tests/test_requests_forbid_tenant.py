"""Verify endpoints reject tenant_id and extra fields in request payload."""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_answer_rejects_tenant_id_in_payload() -> None:
    """POST /answer with tenant_id in payload must return 422."""
    resp = client.post(
        "/answer",
        json={"query": "x", "tenant_id": "evil"},
        headers={"Authorization": "Bearer tenant:good"},
    )
    assert resp.status_code == 422


def test_retrieve_ac_rejects_tenant_id_in_payload() -> None:
    """POST /retrieve/ac with tenant_id in payload must return 422."""
    resp = client.post(
        "/retrieve/ac",
        json={"query": "x", "k": 20, "tenant_id": "evil"},
        headers={"Authorization": "Bearer tenant:good"},
    )
    assert resp.status_code == 422
