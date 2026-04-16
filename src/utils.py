"""Shared utilities for the news aggregator."""

import re

# Regex pattern for emoji removal (compiled once for performance)
EMOJI_PATTERN = re.compile(
    r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
    r"\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001F900-\U0001F9FF]+"
)


def escape_markdown_url(url: str) -> str:
    """Escape characters that would break out of a markdown `(url)` slot.

    `)`, `[`, `]`, `"`, whitespace, and `\\` are percent-encoded so a hostile
    feed link cannot close the markdown link early, introduce nested link
    syntax, or smuggle whitespace that terminates the destination.
    """
    return (
        url.replace("\\", "%5C")
        .replace(")", "%29")
        .replace("(", "%28")
        .replace("[", "%5B")
        .replace("]", "%5D")
        .replace('"', "%22")
        .replace(" ", "%20")
        .replace("\t", "%09")
        .replace("\n", "%0A")
        .replace("\r", "%0D")
    )
