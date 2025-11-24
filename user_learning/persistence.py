from .bkt_models import BKTParams, PFACoeffs, bkt_update_once, bkt_update_fractional, pfa_prob, _observe_params_with_difficulty
from .utils import _mistakes_from_entry, _get_mapping_from_question, _norm_diff, _diff_level, _impact_with_difficulty, _game_weight, _time_multiplier
from .config import MASTERY_BANDS, MASTERY_THRESHOLD, CONVERGENCE_EPS, CONVERGENCE_K
from django.db import transaction
from django.db.models import Avg
from user_learning.models import UserZoneProgress, UserTopicProficiency, UserSubtopicMastery, UserSubtopicLearningRate
from content_ingestion.models import Topic, Subtopic, GameZone

# Individualization & persistence helpers

def _ema_update(old: float, new: float, alpha: float) -> float:
    return (1.0 - alpha) * old + alpha * new

def _load_pT_scale(user, subtopic_obj, default=1.0) -> float:
    rec = UserSubtopicLearningRate.objects.filter(user=user, subtopic=subtopic_obj).only('pT_scale').first()
    return float(rec.pT_scale) if rec else float(default)

@transaction.atomic
def _save_pT_scale(user, subtopic_obj, new_scale: float, alpha: float = 0.2):
    rec, _ = UserSubtopicLearningRate.objects.select_for_update().get_or_create(
        user=user, subtopic=subtopic_obj, defaults={'pT_scale': 1.0, 'count': 0}
    )
    new_scale = max(0.5, min(1.5, new_scale))
    if rec.count == 0:
        rec.pT_scale = new_scale
        rec.count = 1
    else:
        rec.pT_scale = _ema_update(rec.pT_scale, new_scale, alpha)
        rec.count += 1
    rec.save()

def _lr_mult_from_practice(wins: float, fails: float) -> float:
    """
    Bounded per-learner learning-rate multiplier in [0.5, 1.5] from practice balance.
    - perf in [-1..+1] where +1 means all wins, -1 all fails.
    """
    n = max(1.0, wins + fails)
    perf = (wins - fails) / n  # [-1..+1]
    alpha = 0.5  # scale
    m = 1.0 + alpha * perf     # [0.5..1.5]
    return max(0.5, min(1.5, m))

def _pfa_seed_prior_or_default(existing_mastery_pct, wins, fails, difficulty, pfa, base_prior):
    """
    Choose an initial p(L0) for BKT:
      1) If we already have an existing mastery percent for this subtopic, use it (scaled 0..1).
      2) Else, if there is any practice signal in this batch (wins/fails), use PFA as a prior.
      3) Else, fall back to the base prior.
    """
    if existing_mastery_pct is not None:
        return max(0.0, min(1.0, float(existing_mastery_pct) / 100.0))
    if (wins + fails) > 0.0:
        return pfa_prob(wins, fails, difficulty, pfa)
    return float(base_prior)
