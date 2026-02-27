"""Generate markdown output files."""

import re
from datetime import UTC, datetime
from pathlib import Path

import nh3

from .config import DANGEROUS_LINK_SCHEMES, OUTPUT_DATE_FORMAT, OUTPUT_FILENAME_PREFIX
from .utils import EMOJI_PATTERN

# Case-insensitive pattern to neutralize dangerous URL schemes in markdown links
_DANGEROUS_LINK_RE = re.compile(
    r"\]\((" + "|".join(re.escape(s) for s in DANGEROUS_LINK_SCHEMES) + r")",
    re.IGNORECASE,
)


def get_output_path(output_dir: Path, date: datetime | None = None) -> Path:
    """Generate output path with date-based filename, handling duplicates."""
    if date is None:
        date = datetime.now(UTC)

    base_name = f"{OUTPUT_FILENAME_PREFIX}{date.strftime(OUTPUT_DATE_FORMAT)}"
    output_dir.mkdir(parents=True, exist_ok=True)

    target = output_dir / f"{base_name}.md"
    if not target.exists():
        return target

    counter = 2
    while True:
        target = output_dir / f"{base_name}({counter}).md"
        if not target.exists():
            return target
        counter += 1


def write_markdown(content: str, output_path: Path) -> None:
    """Write sanitized markdown content to file."""
    sanitized = _sanitize_markdown(content)
    output_path.write_text(sanitized, encoding="utf-8")


def _sanitize_markdown(text: str) -> str:
    """Sanitize markdown: remove XSS vectors (HTML, dangerous URLs) and emojis."""
    if not text:
        return ""
    # Remove emojis
    sanitized = EMOJI_PATTERN.sub("", text)
    # Strip embedded HTML (XSS vector)
    sanitized = nh3.clean(sanitized, tags=set())
    # Neutralize dangerous URL schemes in markdown links (case-insensitive)
    sanitized = _DANGEROUS_LINK_RE.sub("](#", sanitized)
    return sanitized.strip()
