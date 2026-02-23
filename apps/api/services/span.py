"""Evidence span extraction with exact offsets inside section text."""

import re


def _tokenize(text: str) -> set[str]:
    """Lowercase tokens, split on non-alphanumeric."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _score_sentence(sentence: str, query_tokens: set[str]) -> int:
    """Keyword overlap: count of query tokens that appear in sentence."""
    sent_tokens = _tokenize(sentence)
    return len(query_tokens & sent_tokens)


def _split_sentences(text: str) -> list[str]:
    """Split on .?! followed by whitespace, or newlines. Keeps punctuation in sentence."""
    if not text.strip():
        return []
    parts = re.split(r"(?<=[.?!])\s+|\n+", text)
    return [s.strip() for s in parts if s.strip()]


def select_quote_span(
    section_text: str,
    query: str,
    max_len: int = 280,
) -> tuple[str, int, int]:
    """
    Select a quote span from section_text relevant to query.
    Returns (quote_span, start_char, end_char) with quote_span == section_text[start_char:end_char].
    """
    if not section_text:
        return ("", 0, 0)

    query_tokens = _tokenize(query)
    sentences = _split_sentences(section_text)

    selected: str
    if sentences:
        best = max(sentences, key=lambda s: _score_sentence(s, query_tokens))
        if _score_sentence(best, query_tokens) > 0 or len(sentences) == 1:
            selected = best
        else:
            selected = sentences[0]
    else:
        selected = section_text.strip() or section_text[:max_len]

    pos = section_text.find(selected)
    if pos < 0:
        selected = section_text[:max_len].strip() or section_text[:max_len]
        pos = 0

    if len(selected) <= max_len:
        quote_span = selected
        start_char = pos
        end_char = pos + len(quote_span)
    else:
        trim_start = (len(selected) - max_len) // 2
        quote_span = selected[trim_start : trim_start + max_len]
        start_char = pos + trim_start
        end_char = start_char + len(quote_span)

    return (quote_span, start_char, end_char)
