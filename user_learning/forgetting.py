from django.utils import timezone


def apply_forgetting(mastery: float, last_practiced_at, p_forget: float) -> float:
    """
    Decays mastery based on days since last practice.
    Only applies if last_practiced_at is not None.
    Decay is linear per day, clamped to a floor of 0.05.
    mastery is expected in [0, 1].
    """
    if last_practiced_at is None:
        return mastery

    days_since = (timezone.now() - last_practiced_at).days
    decayed = mastery - (p_forget * days_since)
    return max(0.05, decayed)
