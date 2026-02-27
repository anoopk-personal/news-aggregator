"""Tests for article deduplication module."""

from datetime import UTC, datetime, timedelta

from src.deduplicator import _normalize_text, deduplicate_articles
from src.rss_fetcher import Article


def _make_article(
    title: str = "Test",
    link: str = "https://example.com/1",
    summary: str = "Summary",
    source: str = "Source",
    published_hours_ago: int = 1,
) -> Article:
    """Build an Article with sensible defaults for testing."""
    return Article(
        title=title,
        link=link,
        summary=summary,
        source=source,
        published=datetime.now(UTC) - timedelta(hours=published_hours_ago),
    )


def test_deduplicate_identical_articles():
    """Two identical articles from different sources: one removed, attribution added."""
    article_a = _make_article(
        title="OpenAI launches GPT-5",
        link="https://a.com/1",
        summary="OpenAI announced GPT-5 today with major improvements.",
        source="TechCrunch",
    )
    article_b = _make_article(
        title="OpenAI launches GPT-5",
        link="https://b.com/1",
        summary="OpenAI announced GPT-5 today with major improvements.",
        source="VentureBeat",
    )
    result = deduplicate_articles([article_a, article_b])
    assert len(result) == 1
    assert "Also covered by: VentureBeat" in result[0].summary


def test_deduplicate_similar_articles():
    """Two articles about the same event with different wording should be deduped."""
    article_a = _make_article(
        title="Google announces Gemini 3.0 AI model",
        link="https://a.com/1",
        summary="Google today unveiled Gemini 3.0, its most capable AI model yet.",
        source="Ars Technica",
    )
    article_b = _make_article(
        title="Google announces Gemini 3.0 AI model launch",
        link="https://b.com/1",
        summary="Google today unveiled Gemini 3.0, the most capable AI model from the company.",
        source="Wired",
    )
    result = deduplicate_articles([article_a, article_b])
    assert len(result) == 1


def test_deduplicate_dissimilar_articles():
    """Two unrelated articles should both be kept."""
    article_a = _make_article(
        title="New breakthrough in quantum computing",
        link="https://a.com/1",
        summary="Researchers achieve quantum supremacy with 1000-qubit processor.",
        source="MIT News",
    )
    article_b = _make_article(
        title="Python 3.14 released with pattern matching improvements",
        link="https://b.com/1",
        summary="The Python team released version 3.14 with enhanced pattern matching syntax.",
        source="InfoQ",
    )
    result = deduplicate_articles([article_a, article_b])
    assert len(result) == 2


def test_deduplicate_keeps_longest_summary():
    """From a cluster of similar articles, keep the one with the longest summary."""
    short = _make_article(
        title="Meta releases Llama 4",
        link="https://a.com/1",
        summary="Meta released Llama 4.",
        source="A",
    )
    medium = _make_article(
        title="Meta releases Llama 4 open source model",
        link="https://b.com/1",
        summary="Meta released Llama 4, an open source model with improved performance.",
        source="B",
    )
    longest = _make_article(
        title="Meta releases Llama 4 open source model today",
        link="https://c.com/1",
        summary="Meta released Llama 4, an open source large language model with significantly "
        "improved performance across benchmarks. The model is available for download.",
        source="C",
    )
    result = deduplicate_articles([short, medium, longest])
    assert len(result) == 1
    assert result[0].source == "C"
    assert "Also covered by: A, B" in result[0].summary


def test_deduplicate_preserves_order():
    """Articles should maintain their original relative order after dedup."""
    articles = [
        _make_article(
            title="New breakthrough in quantum computing",
            link="https://a.com/1",
            summary="Researchers achieve quantum supremacy milestone.",
            source="A",
        ),
        _make_article(
            title="Python 3.14 released with major improvements",
            link="https://b.com/1",
            summary="The Python team shipped version 3.14 today.",
            source="B",
        ),
        _make_article(
            title="SpaceX launches new satellite constellation",
            link="https://c.com/1",
            summary="SpaceX deployed 60 new satellites into orbit.",
            source="C",
        ),
    ]
    result = deduplicate_articles(articles)
    assert len(result) == 3
    assert result[0].title == "New breakthrough in quantum computing"
    assert result[1].title == "Python 3.14 released with major improvements"
    assert result[2].title == "SpaceX launches new satellite constellation"


def test_deduplicate_empty_list():
    """Empty input returns empty output."""
    assert deduplicate_articles([]) == []


def test_deduplicate_single_article():
    """Single article returned unchanged."""
    article = _make_article(title="Sole article", link="https://a.com/1")
    result = deduplicate_articles([article])
    assert len(result) == 1
    assert result[0].title == "Sole article"


def test_normalize_text_strips_punctuation_and_case():
    """Verify normalization: lowercase, no punctuation, normalized whitespace."""
    assert _normalize_text("Hello, World!  How's it  going?") == "hello world hows it going"
    assert _normalize_text("ALL CAPS TEXT") == "all caps text"
    assert _normalize_text("") == ""


# --- Large feed handling tests ---


def test_deduplicate_large_cluster_keeps_best():
    """12 near-identical articles from different sources collapse to a single result."""
    articles = [
        _make_article(
            title="Major breakthrough in AI safety announced today",
            link=f"https://source{i}.com/article",
            summary=(
                "Researchers announced a major breakthrough in AI safety. " + "Extra detail. " * i
            ),
            source=f"Source{i}",
            published_hours_ago=1,
        )
        for i in range(12)
    ]
    result = deduplicate_articles(articles)
    assert len(result) == 1
    assert "Also covered by:" in result[0].summary


def test_deduplicate_mixed_clusters_with_many_articles():
    """25 articles: two clusters of 5 + 15 unique = 17 results."""
    cluster_a = [
        _make_article(
            title="SpaceX launches new rocket to Mars",
            link=f"https://space{i}.com/article",
            summary=f"SpaceX successfully launched a new rocket to Mars today. {'More info. ' * i}",
            source=f"SpaceNews{i}",
            published_hours_ago=1,
        )
        for i in range(5)
    ]
    cluster_b = [
        _make_article(
            title="Apple releases new iPhone model with AI features",
            link=f"https://tech{i}.com/article",
            summary=f"Apple released a new iPhone model with AI features today. {'Details. ' * i}",
            source=f"TechSite{i}",
            published_hours_ago=2,
        )
        for i in range(5)
    ]
    unique_data = [
        (
            "Python 3.15 adds pattern guards",
            "The Python team shipped version 3.15 with guard clauses.",
        ),
        (
            "Rust foundation announces governance changes",
            "The Rust foundation restructured its board today.",
        ),
        (
            "EU passes comprehensive data privacy regulation",
            "European parliament voted to adopt new data privacy rules.",
        ),
        (
            "Tesla recalls 50000 vehicles over brake sensor",
            "Tesla issued a voluntary recall for Model Y vehicles.",
        ),
        (
            "Netflix reports record quarterly subscriber growth",
            "Netflix added 19 million subscribers in Q4.",
        ),
        (
            "Bitcoin reaches new all time high above 150k",
            "Bitcoin surged past 150 thousand driven by ETF inflows.",
        ),
        (
            "NASA confirms water ice on lunar surface",
            "Artemis data confirms water ice in shadowed craters.",
        ),
        (
            "DeepMind achieves protein folding milestone",
            "AlphaFold 4 predicts protein interactions accurately.",
        ),
        (
            "Amazon opens fully automated warehouse",
            "The Texas facility uses robots from receiving to shipping.",
        ),
        (
            "CRISPR therapy approved for sickle cell",
            "FDA granted full approval for gene editing treatment.",
        ),
        (
            "India launches reusable space vehicle",
            "ISRO tested its pushpak vehicle with autonomous landing.",
        ),
        (
            "GitHub introduces AI code review tool",
            "Copilot review analyzes pull requests inline.",
        ),
        (
            "Scientists report record ocean temperatures",
            "Sea surface temps exceeded records for eighth month.",
        ),
        (
            "Samsung unveils foldable laptop at CES",
            "The 17 inch OLED display folds in half under one kg.",
        ),
        (
            "WHO declares mpox outbreak contained",
            "WHO downgraded its mpox emergency classification.",
        ),
    ]
    unique = [
        _make_article(
            title=title,
            link=f"https://unique{i}.com/article",
            summary=summary,
            source=f"UniqueSrc{i}",
            published_hours_ago=3,
        )
        for i, (title, summary) in enumerate(unique_data)
    ]
    result = deduplicate_articles(cluster_a + cluster_b + unique)
    assert len(result) == 17
