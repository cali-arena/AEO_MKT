"""Tests for allowed domain enforcement in crawl."""

from unittest.mock import patch

import pytest

from apps.api.services.crawl import fetch_url
from apps.api.tests.conftest import DETERMINISTIC_POLICY


def test_allowed_domain_passes(monkeypatch) -> None:
    """Allowed domain (in policy allowed_domains) fetches successfully."""
    # Patch target: apps.api.services.crawl.load_policy (where crawl uses it).
    monkeypatch.setattr("apps.api.services.crawl.load_policy", lambda: DETERMINISTIC_POLICY)
    mock_response = type("Resp", (), {"url": "https://coasttocoastmovers.com/about", "status_code": 200, "text": "<html></html>"})()

    with patch("apps.api.services.crawl.requests.get", return_value=mock_response) as mock_get:
        with patch("apps.api.services.crawl.datetime") as mock_dt:
            from datetime import datetime, timezone

            mock_dt.now.return_value = datetime.now(timezone.utc)
            result = fetch_url("https://coasttocoastmovers.com/about")

    assert "excluded" not in result or not result.get("excluded")
    assert result.get("final_url") == "https://coasttocoastmovers.com/about"
    assert result.get("status_code") == 200
    mock_get.assert_called_once()


def test_disallowed_domain_raises_error(monkeypatch) -> None:
    """Disallowed domain raises ValueError('domain_not_allowed')."""
    # Patch target: apps.api.services.crawl.load_policy (where crawl uses it).
    monkeypatch.setattr("apps.api.services.crawl.load_policy", lambda: DETERMINISTIC_POLICY)
    with pytest.raises(ValueError, match="domain_not_allowed"):
        fetch_url("https://evil.com/malicious")
