"""Phase 9: searchable registry — reuse components instead of rediscovering them.

Keyword overlap with light plural handling; no embeddings, no new deps.
The planner calls this before spending a single LLM token on discovery.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlmodel import select

from tau_agent.webhermes.db import Component, default_db, session

_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "something",
        "that",
        "this",
        "those",
        "these",
        "for",
        "with",
        "from",
        "into",
        "onto",
        "upon",
        "to",
        "of",
        "in",
        "on",
        "at",
        "and",
        "or",
        "but",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "it",
        "its",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "they",
        "them",
        "his",
        "her",
        "their",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "can",
        "may",
        "might",
        "must",
        "shall",
        "please",
        "just",
        "now",
        "then",
        "than",
        "so",
        "such",
        "very",
        "really",
        "how",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "whose",
        "want",
        "need",
        "like",
        "get",
        "use",
        "using",
        "used",
        "via",
        "per",
        "over",
        "under",
        "again",
        "once",
        "here",
        "there",
    ]
)


def _tokens(text: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    out = set()
    for w in words:
        if w in _STOPWORDS or len(w) < 3:
            continue
        out.add(w)
        if w.endswith("es") and len(w) > 4:
            out.add(w[:-2])
        elif w.endswith("s") and len(w) > 3:
            out.add(w[:-1])
    return out


def _score(query: set[str], name: str, description: str) -> float:
    if not query:
        return 0.0
    hay = _tokens(f"{name} {description}")
    hit = len(query & hay)
    name_hit = 1 if _tokens(name) & query else 0
    return min(1.0, (hit + name_hit) / len(query))


def find_matching_component(
    description: str,
    domain: str = "",
    *,
    action: str | None = None,
    min_score: float = 0.3,
    db_path: Path | str | None = None,
) -> Component | None:
    """Best keyword match (same domain preferred), or None below `min_score`."""
    db_path = db_path or default_db()
    query = _tokens(description)
    with session(db_path) as s:
        rows = s.exec(select(Component)).all()
    # Strict scoping: a named domain only reuses its own components (locators are
    # page-specific); unscoped queries ("") may match anything.
    candidates = [r for r in rows if r.domain == domain] if domain else list(rows)
    best: Component | None = None
    best_score = 0.0
    for row in candidates:
        if action is not None and row.action_type != action:
            continue
        sc = _score(query, row.name, row.description)
        if sc > best_score:
            best, best_score = row, sc
    return best if best is not None and best_score >= min_score else None
