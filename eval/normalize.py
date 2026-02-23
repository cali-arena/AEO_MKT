"""Normalize /answer responses to a stable shape for eval. Handles missing/malformed fields with safe defaults."""

from typing import Any


def normalize_answer_response(resp_json: dict[str, Any] | None) -> dict[str, Any]:
    """
    Normalize an /answer response to a stable dict shape.
    Returns dict with keys: refused, refusal_reason, answer, claims, citations, evidence_ids, scores, debug.
    Missing fields get safe defaults (empty lists, None); never fabricates correctness.
    """
    if resp_json is None:
        return _default_output()

    refused = _safe_bool(resp_json.get("refused"), False)
    refusal_reason = resp_json.get("refusal_reason")
    if refused and refusal_reason is None:
        refusal_reason = None  # present but unknown; do not fabricate

    answer = resp_json.get("answer")
    if answer is None:
        answer = ""

    claims = resp_json.get("claims")
    if not isinstance(claims, list):
        claims = []

    citations = resp_json.get("citations")
    if citations is None:
        citations = {}
    elif not isinstance(citations, dict):
        citations = {}

    evidence_ids: list[str] = []
    for c in claims:
        if isinstance(c, dict):
            eids = c.get("evidence_ids")
            if isinstance(eids, list):
                evidence_ids.extend(e for e in eids if isinstance(e, str))
    evidence_ids = list(dict.fromkeys(evidence_ids))

    debug = resp_json.get("debug")
    scores: dict[str, float] | None = None
    if isinstance(debug, dict):
        scores = {}
        t = debug.get("threshold")
        if t is not None and isinstance(t, (int, float)):
            scores["threshold"] = float(t)
        s = debug.get("top_score")
        if s is not None and isinstance(s, (int, float)):
            scores["top_score"] = float(s)
        if not scores:
            scores = None
    elif debug is not None and not isinstance(debug, dict):
        debug = None

    return {
        "refused": refused,
        "refusal_reason": refusal_reason,
        "answer": answer,
        "claims": claims,
        "citations": citations,
        "evidence_ids": evidence_ids,
        "scores": scores,
        "debug": debug,
    }


def _default_output() -> dict[str, Any]:
    return {
        "refused": False,
        "refusal_reason": None,
        "answer": "",
        "claims": [],
        "citations": {},
        "evidence_ids": [],
        "scores": None,
        "debug": None,
    }


def _safe_bool(val: Any, default: bool) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return default
