"""Single extraction tool: main text and title from HTML. Uses trafilatura with BS4 fallback."""

import re

from bs4 import BeautifulSoup
import trafilatura


def extract_main_text(html: str) -> str:
    """
    Extract main text from HTML.
    Primary: trafilatura.extract(include_comments=False, include_tables=False).
    Fallback: BeautifulSoup get_text if trafilatura returns None/empty.
    """
    result = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
    )
    if result and result.strip():
        return result.strip()

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def extract_title(html: str) -> str | None:
    """Extract <title> from HTML using BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    return title_tag.get_text(strip=True) if title_tag else None
