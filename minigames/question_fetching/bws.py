# Bayesian Weighted Sampling (BWS) for question selection
import math
import random
from typing import List, Dict, Tuple
from .constants import SOFTMAX_TEMPERATURE, EVAL_CANDIDATES_PER_BUCKET
from .eig_bkt import eig_for_question, diff_level, BKTParams
from .helpers import sample_random_by_offsets
from question_generation.models import GeneratedQuestion

def softmax(xs: List[float], temperature: float) -> List[float]:
    if not xs:
        return []
    t = max(1e-6, float(temperature))
    m = max(xs)
    exps = [math.exp((x - m) / t) for x in xs]
    s = sum(exps)
    if s <= 0:
        n = len(xs)
        return [1.0 / n] * n
    return [e / s for e in exps]

def bws_pick_ids_by_eig(
    user,
    qs,
    take: int,
    mastery_by_sub: Dict[int, float],
    temperature: float = SOFTMAX_TEMPERATURE,
    eval_cap: int = EVAL_CANDIDATES_PER_BUCKET,
) -> List[int]:
    if take <= 0:
        return []
    cand_ids = sample_random_by_offsets(qs.only('id'), min(eval_cap, take * 8))
    if not cand_ids:
        return []
    fields = ['id', 'subtopic_id', 'estimated_difficulty']
    objs = list(GeneratedQuestion.objects.filter(id__in=cand_ids).only(*fields))
    base = BKTParams()
    eig_scores: List[float] = []
    ordered_ids: List[int] = []
    for o in objs:
        sid = getattr(o, 'subtopic_id', None)
        if sid is None:
            continue
        p_know = (mastery_by_sub.get(sid, 0.0) or 0.0) / 100.0
        if p_know <= 0.0:
            p_know = base.p_L0
        dlevel = diff_level(getattr(o, 'estimated_difficulty', None))
        eig = eig_for_question(p_know, dlevel, base)
        eig_scores.append(float(eig))
        ordered_ids.append(int(o.id))
    if not ordered_ids:
        return []
    if max(eig_scores) <= 1e-9:
        k = min(take, len(ordered_ids))
        return random.sample(ordered_ids, k)
    probs = softmax(eig_scores, temperature)
    chosen: List[int] = []
    pool: List[Tuple[int, float]] = list(zip(ordered_ids, probs))
    for _ in range(min(take, len(pool))):
        r = random.random()
        cum = 0.0
        pick_idx = 0
        for i, (_id, p) in enumerate(pool):
            cum += p
            if r <= cum:
                pick_idx = i
                break
        chosen_id = pool[pick_idx][0]
        chosen.append(chosen_id)
        del pool[pick_idx]
        s = sum(p for _, p in pool)
        if s > 0:
            pool = [(i, p / s) for (i, p) in pool]
        else:
            break
    return chosen
