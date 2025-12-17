from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from question_generation.models import GeneratedQuestion, PreAssessmentQuestion
from question_generation.utils.ml_classifier import predict_difficulty


@api_view(["POST"])
@permission_classes([IsAdminUser])
def ml_bulk_predict_difficulty(request, question_type):
    """
    Valid categories:
    - coding
    - non_coding
    - minigame
    - preassessment

    Optional filters (query params):
    - difficulty=beginner|intermediate|advanced|master
    - validation_status=pending|processed      (minigame only)
    """

    difficulty = request.query_params.get("difficulty")
    validation_status = request.query_params.get("validation_status")

    # -------------------------------
    # SELECT BASE QUERYSET
    # -------------------------------
    if question_type == "coding":
        qs = GeneratedQuestion.objects.filter(game_type="coding")

    elif question_type == "non_coding":
        qs = GeneratedQuestion.objects.filter(game_type="non_coding")

    elif question_type in ["minigame", "miniggame"]:
        qs = GeneratedQuestion.objects.all()

    elif question_type == "preassessment":
        qs = PreAssessmentQuestion.objects.all()

    else:
        return Response({"message": f"Invalid question type: {question_type}"}, status=400)

    # -------------------------------
    # APPLY FILTERS
    # -------------------------------
    if difficulty:
        qs = qs.filter(estimated_difficulty=difficulty)

    # Only GeneratedQuestion has validation_status
    if validation_status and question_type != "preassessment":
        qs = qs.filter(validation_status=validation_status)

    total = qs.count()
    updated = 0
    unchanged = 0

    # -------------------------------
    # MAIN LOOP
    # -------------------------------
    for q in qs:
        if isinstance(q, GeneratedQuestion):
            gtype = q.game_type
            new_diff = predict_difficulty(q.question_text, gtype)
            old_diff = q.estimated_difficulty

            if new_diff != old_diff:
                q.estimated_difficulty = new_diff
                q.validation_status = "processed"
                q.save(update_fields=["estimated_difficulty", "validation_status"])
                updated += 1
            else:
                q.validation_status = "processed"
                q.save(update_fields=["validation_status"])
                unchanged += 1

        else:
            # PreAssessmentQuestion
            new_diff = predict_difficulty(q.question_text, "preassessment")
            old_diff = q.estimated_difficulty

            if new_diff != old_diff:
                q.estimated_difficulty = new_diff
                q.save(update_fields=["estimated_difficulty"])
                updated += 1
            else:
                unchanged += 1

    return Response({
        "message": f"Difficulty check completed for `{question_type}`",
        "total_checked": total,
        "updated": updated,
        "unchanged": unchanged
    })
