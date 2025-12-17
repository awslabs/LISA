from datetime import datetime, timezone


def now(tz=timezone.utc) -> int:
    """Return UTC epoch milliseconds."""
    return int(datetime.now(tz).timestamp() * 1000)


def now_seconds(tz=timezone.utc) -> int:
    """Return UTC epoch seconds."""
    return int(datetime.now(tz).timestamp())


def iso_string(tz=timezone.utc) -> str:
    """Return ISO datetime string with UTC offset."""
    return datetime.now(tz).isoformat()


def utc_now() -> datetime:
    """Return current UTC datetime object."""
    return datetime.now(timezone.utc)