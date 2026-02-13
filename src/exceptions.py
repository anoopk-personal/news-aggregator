"""Custom exceptions for the news aggregator."""


class NewsAggregatorError(Exception):
    """Base exception for news aggregator."""


class SummarizationError(NewsAggregatorError):
    """Error during summarization."""
