from django.db.models import F
from analytics.models import UserAbility, ItemIRTParameters
from question_generation.models import GeneratedQuestion


def select_question_for_user(user, game_type="coding"):
    """
    Adaptive item selection using:
    θ (user ability) vs. b (item difficulty)
    """

    # 1. Get user theta (default = 0 if no ability yet)
    try:
        theta = user.irt_ability.theta
    except UserAbility.DoesNotExist:
        theta = 0.0

    # 2. Filter questions by game type
    qs = GeneratedQuestion.objects.filter(game_type=game_type)

    if not qs.exists():
        return None
    
    # 3. Join IRT parameters
    qs = qs.annotate(
        diff_b=F("irt_params__b"),
        disc_a=F("irt_params__a"),
    )

    # 4. Compute absolute distance |θ - b|
    qs = qs.order_by(
        (F("irt_params__b") - theta).abs()
    )
    # 5. Return the *closest difficulty question*
    return qs.first()
