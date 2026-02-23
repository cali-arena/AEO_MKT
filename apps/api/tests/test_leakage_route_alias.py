"""Contract tests for /leakage/latest alias and /monitor/leakage/latest."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.main import app

LEAKAGE_LATEST_FIELDS = {"tenant_id", "ok", "last_checked_at", "details_json"}

client = TestClient(app)


@patch("apps.api.routes.monitor.list_monitor_events")
def test_leakage_latest_alias_same_schema_as_monitor(mock_list) -> None:
    """Both /leakage/latest and /monitor/leakage/latest return identical LeakageLatestResponse shape."""
    mock_list.return_value = []  # no events -> ok=True, last_checked_at=now, details_json=None

    auth = {"Authorization": "Bearer tenant:alias_test"}

    r_monitor = client.get("/monitor/leakage/latest", headers=auth)
    r_alias = client.get("/leakage/latest", headers=auth)

    assert r_monitor.status_code == 200
    assert r_alias.status_code == 200

    m = r_monitor.json()
    a = r_alias.json()

    assert set(m) == LEAKAGE_LATEST_FIELDS
    assert set(a) == LEAKAGE_LATEST_FIELDS
    assert set(m) == set(a), "Both endpoints must return same keys"

    assert isinstance(m["tenant_id"], str)
    assert isinstance(m["ok"], bool)
    assert isinstance(m["last_checked_at"], str)
    assert m["details_json"] is None or isinstance(m["details_json"], (dict, list))

    assert isinstance(a["tenant_id"], str)
    assert isinstance(a["ok"], bool)
    assert isinstance(a["last_checked_at"], str)
    assert a["details_json"] is None or isinstance(a["details_json"], (dict, list))

    assert m["tenant_id"] == a["tenant_id"]
    assert m["ok"] == a["ok"]
    assert m["details_json"] == a["details_json"]
