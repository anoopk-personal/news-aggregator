"""Tests for logging configuration."""

import json
import logging

import pytest

from src.logging_config import JsonFormatter, configure_logging


@pytest.fixture(autouse=True)
def _reset_root_logger():
    """Snapshot and restore the root logger so tests don't leak handlers."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in saved_handlers:
        root.addHandler(handler)
    root.setLevel(saved_level)


def _make_record(
    msg: str = "hello",
    level: int = logging.INFO,
    name: str = "test.logger",
) -> logging.LogRecord:
    return logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_json_formatter_emits_required_fields():
    """Standard fields are present in the JSON payload."""
    formatter = JsonFormatter()
    payload = json.loads(formatter.format(_make_record("startup")))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["message"] == "startup"
    assert "timestamp" in payload


def test_json_formatter_includes_extra_fields():
    """extra={...} kwargs are merged into the JSON payload."""
    formatter = JsonFormatter()
    record = _make_record("done")
    record.topic = "ai"
    record.articles = 42

    payload = json.loads(formatter.format(record))

    assert payload["topic"] == "ai"
    assert payload["articles"] == 42


def test_json_formatter_serializes_exception():
    """Exception info is rendered into a single 'exception' string field."""
    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    payload = json.loads(formatter.format(record))
    assert "exception" in payload
    assert "ValueError: boom" in payload["exception"]


def test_configure_logging_uses_human_format_on_tty(monkeypatch, capsys):
    """When stderr is a TTY, lines look like 'INFO: message' rather than JSON."""
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    configure_logging()

    logging.getLogger("aggregator.test").info("hello world")
    captured = capsys.readouterr()

    assert "INFO: hello world" in captured.err
    # Definitely not JSON.
    assert not captured.err.strip().startswith("{")


def test_configure_logging_uses_json_format_when_not_tty(monkeypatch, capsys):
    """When stderr is not a TTY (CI, redirected), each line is a JSON object."""
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)
    configure_logging()

    logging.getLogger("aggregator.test").info("hello world")
    captured = capsys.readouterr()

    line = captured.err.strip()
    payload = json.loads(line)
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "aggregator.test"


def test_configure_logging_writes_to_stderr_not_stdout(monkeypatch, capsys):
    """Logs must go to stderr so stdout stays clean for the dry-run digest."""
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    configure_logging()

    logging.getLogger("aggregator.test").info("log line")
    captured = capsys.readouterr()

    assert "log line" in captured.err
    assert captured.out == ""


def test_configure_logging_is_idempotent(monkeypatch, capsys):
    """Calling configure_logging twice does not duplicate handlers."""
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    configure_logging()
    configure_logging()

    logging.getLogger("aggregator.test").info("once")
    captured = capsys.readouterr()

    # Exactly one log line, not two.
    assert captured.err.count("once") == 1
