import math
from django.apps import apps
from analytics.models import ItemIRTParameters
from question_generation.models import GeneratedQuestion


# 2PL IRT Probability Function: P(correct | theta, a, b)
def irt_probability(theta, a, b):
    """Logistic function for the 2PL IRT model."""
    exponent = a * (theta - b)
    return 1.0 / (1.0 + math.exp(-exponent))


# MAP Priors (Bayesian regularization)
def prior_a(a):
    # log-normal prior for discrimination
    mean = 0
    std = 0.5
    return -((math.log(a) - mean) ** 2) / (2 * std * std)


def prior_b(b):
    # normal prior for difficulty
    mean = 0
    std = 1.0
    return -(b - mean) ** 2 / (2 * std * std)


# Newton–Raphson Updating for 2PL Parameters
def update_parameters(a, b, responses, theta_values, max_iter=10):
    """Estimates updated parameters a & b with Newton–Raphson iterations."""
    
    for _ in range(max_iter):

        d1_a = d1_b = 0
        d2_a = d2_b = 0

        for r in responses:
            theta = theta_values[r.user_id]
            u = r.score  # correctness (0 or 1)

            p = irt_probability(theta, a, b)
            q = 1 - p

            diff = u - p

            # First derivatives (gradient)
            d1_a += diff * (theta - b)
            d1_b += -diff * a

            # Second derivatives (Hessian)
            d2_a += -p * q * (theta - b) ** 2
            d2_b += -p * q * a ** 2

        # Add priors
        d1_a += prior_a(a)
        d1_b += prior_b(b)

        # Newton update
        if d2_a != 0:
            a_new = a - d1_a / d2_a
        else:
            a_new = a

        if d2_b != 0:
            b_new = b - d1_b / d2_b
        else:
            b_new = b

        # Prevent invalid values
        if a_new <= 0:
            a_new = 0.2

        a, b = a_new, b_new

    return a, b


# TOP-LEVEL FUNCTION: Perform IRT recalibration
def recalibrate_item_irt(question_id):

    # Load analytics.QuestionResponse dynamically (NOT minigames)
    QuestionResponse = apps.get_model("analytics", "QuestionResponse")

    # Load the question
    try:
        question = GeneratedQuestion.objects.get(id=question_id)
    except GeneratedQuestion.DoesNotExist:
        return f"Question {question_id} not found."

    # Fetch all responses for this question
    responses = QuestionResponse.objects.filter(question=question)

    if responses.count() < 5:
        return "Not enough responses for IRT recalibration (need ≥10)."

    # Theta estimation (simple placeholder: mean scores)
    theta_values = {}
    for r in responses:
        if r.user_id not in theta_values:
            theta_values[r.user_id] = r.score

    # Load or create IRT params
    params, _ = ItemIRTParameters.objects.get_or_create(question=question)

    a = params.a
    b = params.b

    # Compute new parameters
    new_a, new_b = update_parameters(a, b, responses, theta_values)

    # Save updated values
    params.a = new_a
    params.b = new_b
    params.save()

    return f"IRT recalibration done → a={new_a:.3f}, b={new_b:.3f}"