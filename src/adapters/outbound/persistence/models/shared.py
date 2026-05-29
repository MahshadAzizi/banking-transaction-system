from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)
