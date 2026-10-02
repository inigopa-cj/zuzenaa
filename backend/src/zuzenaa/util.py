"""Small shared helpers."""

from datetime import UTC, datetime


def now_epoch() -> int:
    """Current UTC time as epoch seconds."""
    return int(datetime.now(UTC).timestamp())
