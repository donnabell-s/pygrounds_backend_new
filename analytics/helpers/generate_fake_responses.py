import random
import math
from django.apps import apps
from django.db import transaction
from minigames.models import QuestionResponse
from analytics.irt_utils import recalibrate_item_irt



def logistic(x):
    return 1 / (1 + math.exp(-x))


def simulate_score(a, b, theta):
    """
    Simulate a binary score (0/1) based on the 2PL model:
    P(correct) = logistic(a * (theta - b))
    """
    p_correct = logistic(a * (theta - b))
    return 1 if random.random() < p_correct else 0


@transaction.atomic
def generate_fake_responses(question_id: int, num_students: int = 50):
    """
    Generate fake responses for a given question.
    This allows you to test IRT recalibration even without real users.
    """
    
    
    QuestionResponse = apps.get_model("analytics", "QuestionResponse")
    Question = apps.get_model("question_generation", "GeneratedQuestion")
    ItemIRTParameters = apps.get_model("analytics", "ItemIRTParameters")


    try:
        q = Question.objects.get(id=question_id)
    except Question.DoesNotExist:
        return f"Question {question_id} not found."

    # Get or create IRT params
    irt_params, created = ItemIRTParameters.objects.get_or_create(
        question=q,
        defaults={"a": 1.0, "b": 0.0}
    )

    print("\n======================================")
    print(f"GENERATING FAKE RESPONSES FOR QUESTION {question_id}")
    print("======================================")

    print(f"Initial a = {irt_params.a:.3f}, b = {irt_params.b:.3f}")
    print(f"Generating {num_students} fake student responses...")

    responses_created = 0

    for i in range(num_students):

        # Simulate student ability theta from a realistic distribution
        theta = random.normalvariate(0, 1)  # mean=0, std=1

        score = simulate_score(irt_params.a, irt_params.b, theta)

        QuestionResponse.objects.create(
            question=q,
            score=score,
            response_time=random.randint(5, 45),  # optional field if you have it
            user_id=None  # safe placeholder
        )

        responses_created += 1

    print(f"{responses_created} responses created successfully.")

    print("\nRunning IRT recalibration...")
    result = recalibrate_item_irt(question_id)

    # Reload updated params
    irt_params.refresh_from_db()

    print("\n======================================")
    print("IRT RECALIBRATION RESULT")
    print("======================================")
    print(result)
    print(f"Updated a = {irt_params.a:.3f}, b = {irt_params.b:.3f}")

    return "Simulation complete."


if __name__ == "__main__":
    # Edit this line if you want to test a specific question
    print(generate_fake_responses(question_id=1, num_students=60))
