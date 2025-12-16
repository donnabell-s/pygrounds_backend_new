import math
from django.apps import apps


def irt_probability(theta, a, b):
    """2PL logistic function."""
    return 1.0 / (1.0 + math.exp(-a * (theta - b)))


def update_user_theta(user_id):
    """
    Updates user theta based on ALL their past responses.
    Uses a simple gradient-based MAP estimation.
    """

    UserAbility = apps.get_model("analytics", "UserAbility")
    QuestionResponse = apps.get_model("analytics", "QuestionResponse")
    ItemIRTParameters = apps.get_model("analytics", "ItemIRTParameters")
    User = apps.get_model("users", "User")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return "User not found."

    responses = QuestionResponse.objects.filter(user_id=user_id)

    if responses.count() < 5:
        return "Not enough responses to estimate theta (need ≥5)."

    ability_obj, _ = UserAbility.objects.get_or_create(user=user)
    theta = ability_obj.theta  # initial value

    learning_rate = 0.1

    # Gradient ascent for theta estimation
    for r in responses:
        try:
            params = ItemIRTParameters.objects.get(question=r.question)
        except ItemIRTParameters.DoesNotExist:
            continue

        a = params.a
        b = params.b
        u = r.score  # 0/1

        p = irt_probability(theta, a, b)
        gradient = a * (u - p)  # derivative wrt theta

        theta += learning_rate * gradient
        theta = max(-3.0, min(3.0, theta))


    # Save updated theta
    ability_obj.theta = theta
    ability_obj.save()

    return f"Updated theta for user {user.username}: θ={theta:.3f}"
