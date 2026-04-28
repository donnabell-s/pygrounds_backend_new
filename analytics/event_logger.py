from minigames.models import QuestionResponse as MinigameResponse
from analytics.models import QuestionResponse as AnalyticsResponse


def log_question_event(
    user,
    game_question,
    user_answer: str,
    is_correct: bool,
    time_taken: int,
    attempt_number: int = None,
) -> None:
    """
    Central logging sink for all minigame question answer events.

    Writes one row to minigames.QuestionResponse and one row to
    analytics.QuestionResponse. For non-coding games, leave attempt_number
    as None. For coding games (hangman, debugging), pass:
        attempt_number = wrong_before + 1
    where wrong_before is the count of incorrect QuestionResponse rows for
    this game_question before the current submission.

    Not used for pre-assessment — PreAssessmentQuestion has no GameQuestion FK.
    """
    MinigameResponse.objects.create(
        question=game_question,
        user=user,
        user_answer=user_answer,
        is_correct=is_correct,
        time_taken=time_taken,
    )
    AnalyticsResponse.objects.create(
        question=game_question.question,
        score=1 if is_correct else 0,
        user_id=user.id,
        response_time=time_taken,
        attempt_number=attempt_number,
    )
