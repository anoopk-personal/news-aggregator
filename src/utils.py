"""Shared utilities for the news aggregator."""

import ipaddress
import re
from urllib.parse import urlparse

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


def is_non_routable_host(hostname: str) -> bool:
    """Check if a hostname is a non-globally-routable IP or localhost.

    Defends against SSRF by rejecting loopback, link-local, private, CGN,
    documentation, and benchmarking ranges. Also catches numeric-encoding
    bypasses (hex, C-style octal, bare integer) that glibc resolves as IPs.
    """
    if not hostname:
        return True
    hostname = hostname.rstrip(".")
    if hostname.lower() in ("localhost", "localhost.localdomain"):
        return True
    # Strip IPv6 zone ID (e.g. fe80::1%eth0)
    if "%" in hostname:
        hostname = hostname.split("%")[0]
    try:
        return not ipaddress.ip_address(hostname).is_global
    except ValueError:
        pass
    # Bare integers, hex (0x7f000001), and C-style octal (017700000001) are resolved
    # as IPs by glibc on Linux. Python's int(x, 0) handles hex/0o-octal/decimal but
    # not C-style octal (leading zero without 'o'), so we detect that separately.
    try:
        if hostname.startswith(("0x", "0X")):
            numeric = int(hostname, 16)
        elif len(hostname) > 1 and hostname[0] == "0" and hostname.isdigit():
            numeric = int(hostname, 8)
        else:
            numeric = int(hostname)
        return not ipaddress.ip_address(numeric).is_global
    except (ValueError, OverflowError):
        return False  # regular domain name, allow it


def is_valid_url(url: str, allowed_schemes: frozenset[str] | set[str]) -> bool:
    """Validate that a URL has an allowed scheme and routable host.

    Two-layer SSRF defense: scheme check + non-routable host rejection.
    Caller passes the allowed schemes (typically ``frozenset({"https"})``).
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in allowed_schemes or not parsed.netloc:
            return False
        if is_non_routable_host(parsed.hostname or ""):
            return False
        return True
    except (ValueError, AttributeError):
        return False
