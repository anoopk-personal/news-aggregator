"""Deduplicate articles that cover the same event across different feeds."""

import logging
import re
from difflib import SequenceMatcher

from .config import DEDUP_SIMILARITY_THRESHOLD
from .rss_fetcher import Article

logger = logging.getLogger(__name__)


def deduplicate_articles(articles: list[Article]) -> list[Article]:
    """Remove near-duplicate articles, keeping the most informative version.

    Groups articles exceeding a similarity threshold into clusters using
    single-linkage clustering. From each cluster, keeps the article with
    the longest summary and appends "Also covered by" attribution.
    """
    if len(articles) < 2:
        return list(articles)

    cluster_map = {idx: idx for idx in range(len(articles))}

    def find_root(idx: int) -> int:
        while cluster_map[idx] != idx:
            cluster_map[idx] = cluster_map[cluster_map[idx]]
            idx = cluster_map[idx]
        return idx

    def union(a: int, b: int) -> None:
        root_a = find_root(a)
        root_b = find_root(b)
        if root_a != root_b:
            cluster_map[root_b] = root_a

    for i in range(len(articles)):
        text_i = articles[i].title + " " + articles[i].summary
        for j in range(i + 1, len(articles)):
            text_j = articles[j].title + " " + articles[j].summary
            similarity = _compute_similarity(text_i, text_j)
            if similarity >= DEDUP_SIMILARITY_THRESHOLD:
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for idx in range(len(articles)):
        root = find_root(idx)
        clusters.setdefault(root, []).append(idx)

    kept_articles: dict[int, Article] = {}
    for indices in clusters.values():
        best_idx = max(indices, key=lambda idx: len(articles[idx].summary))
        other_sources = sorted({articles[idx].source for idx in indices if idx != best_idx})
        if other_sources:
            best = articles[best_idx]
            attribution = "Also covered by: " + ", ".join(other_sources)
            kept_articles[best_idx] = Article(
                title=best.title,
                link=best.link,
                summary=(best.summary + "\n\n" + attribution) if best.summary else attribution,
                source=best.source,
                published=best.published,
            )
        else:
            kept_articles[best_idx] = articles[best_idx]

    return [kept_articles[idx] for idx in range(len(articles)) if idx in kept_articles]


def _compute_similarity(text_a: str, text_b: str) -> float:
    """Compute normalized text similarity between two strings."""
    norm_a = _normalize_text(text_a)
    norm_b = _normalize_text(text_b)
    if not norm_a and not norm_b:
        return 1.0
    if not norm_a or not norm_b:
        return 0.0
    return SequenceMatcher(None, norm_a, norm_b).ratio()


def _normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, normalize whitespace for comparison."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
