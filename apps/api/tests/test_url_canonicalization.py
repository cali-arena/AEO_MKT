"""Tests for URL canonicalization."""

import pytest

from apps.api.services.url_utils import canonicalize_url


def test_fragment_stripped() -> None:
    """Fragment (#...) is removed from canonical URL."""
    url = "https://Example.COM/path#section1"
    canonical, domain = canonicalize_url(url)
    assert "#" not in canonical
    assert canonical == "https://example.com/path"


def test_host_lowercased() -> None:
    """Hostname is lowercased."""
    url = "https://Example.COM/Path"
    canonical, domain = canonicalize_url(url)
    assert domain == "example.com"
    assert "example.com" in canonical
    assert "Example" not in canonical


def test_trailing_slash_normalized() -> None:
    """Trailing slash removed for non-root paths."""
    url = "https://example.com/path/"
    canonical, _ = canonicalize_url(url)
    assert canonical == "https://example.com/path"

    url2 = "https://example.com/foo/bar/"
    canonical2, _ = canonicalize_url(url2)
    assert canonical2 == "https://example.com/foo/bar"


def test_root_preserved() -> None:
    """Root path (/) is preserved."""
    url = "https://example.com/"
    canonical, _ = canonicalize_url(url)
    assert canonical == "https://example.com/"

    url2 = "https://example.com"
    canonical2, _ = canonicalize_url(url2)
    assert canonical2 == "https://example.com/"


def test_default_ports_removed() -> None:
    """Default ports (80, 443) are removed from canonical URL."""
    url_https = "https://example.com:443/path"
    canonical, _ = canonicalize_url(url_https)
    assert ":443" not in canonical
    assert canonical == "https://example.com/path"

    url_http = "http://example.com:80/path"
    canonical2, _ = canonicalize_url(url_http)
    assert ":80" not in canonical2
    assert canonical2 == "http://example.com/path"
