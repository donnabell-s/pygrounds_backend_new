from django.utils import timezone


def recency_weight(last_practiced_at) -> float:
    """
    Returns a weight multiplier based on days since last practice.
    Longer gap = higher weight = larger BKT update in either direction.
    Capped at 2.0 to prevent extreme jumps.
    If never practiced, returns 1.0 (neutral).
    """
    if last_practiced_at is None:
        return 1.0

    days_since = (timezone.now() - last_practiced_at).days
    return min(1.0 + (days_since * 0.05), 2.0)