# EIG-BKT core logic for question fetching
import math
from typing import Optional, Tuple
from .constants import DIFF_LEVELS

class BKTParams:
    def __init__(self, p_L0=0.20, p_T=0.10, p_S=0.10, p_G=0.20, decay_wrong=0.85, min_floor=0.001, max_ceiling=0.999):
        self.p_L0 = p_L0
        self.p_T = p_T
        self.p_S = p_S
        self.p_G = p_G
        self.decay_wrong = decay_wrong
        self.min_floor = min_floor
        self.max_ceiling = max_ceiling

def bkt_update_once(p_know: float, correct: bool, p: BKTParams) -> float:
    if correct:
        num = p_know * (1.0 - p.p_S)
        den = num + (1.0 - p_know) * p.p_G
    else:
        num = p_know * p.p_S
        den = num + (1.0 - p_know) * (1.0 - p.p_G)
    post = 0.0 if den == 0 else num / den
    p_next = post + (1.0 - post) * p.p_T
    if not correct:
        p_next *= p.decay_wrong
    return max(p.min_floor, min(p.max_ceiling, p_next))

def norm_diff(d: Optional[str]) -> str:
    if not d:
        return 'intermediate'
    d = str(d).strip().lower()
    if d in DIFF_LEVELS:
        return d
    if d.startswith('beg'):
        return 'beginner'
    if d.startswith('inter'):
        return 'intermediate'
    if d.startswith('adv'):
        return 'advanced'
    if d.startswith('mast'):
        return 'master'
    return 'intermediate'

def diff_level(d: Optional[str]) -> int:
    return DIFF_LEVELS.get(norm_diff(d), 1)

def diff_centered(level: int) -> float:
    return (max(0, min(3, level)) - 1.5) / 1.5

def observe_params_with_difficulty(base: BKTParams, level: int) -> Tuple[float, float, float]:
    c = diff_centered(level)
    s_k, g_k, d_k = 0.04, 0.04, 0.07
    p_S_eff = max(0.02, min(0.30, base.p_S + s_k * c))
    p_G_eff = max(0.05, min(0.35, base.p_G - g_k * c))
    target_easy, target_hard = 0.80, 0.98
    target = target_hard if c > 0 else target_easy
    decay_eff = base.decay_wrong + d_k * (target - base.decay_wrong)
    decay_eff = decay_eff + 0.05 * c
    decay_eff = max(0.75, min(0.98, decay_eff))
    return p_S_eff, p_G_eff, decay_eff

def binary_entropy(p: float) -> float:
    p = max(1e-9, min(1 - 1e-9, p))
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))

def p_correct(p_know: float, p_S: float, p_G: float) -> float:
    return p_know * (1 - p_S) + (1 - p_know) * p_G

def eig_for_question(p_know: float, diff_level: int, base: Optional[BKTParams] = None) -> float:
    base = base or BKTParams()
    p_S, p_G, decay_wrong = observe_params_with_difficulty(base, diff_level)
    H_prior = binary_entropy(p_know)
    Pc = p_correct(p_know, p_S, p_G)
    Pw = 1 - Pc
    params = BKTParams(
        p_L0=p_know, p_T=base.p_T, p_S=p_S, p_G=p_G, decay_wrong=decay_wrong,
        min_floor=base.min_floor, max_ceiling=base.max_ceiling,
    )
    p_after_c = bkt_update_once(p_know, True, params)
    p_after_w = bkt_update_once(p_know, False, params)
    H_post = Pc * binary_entropy(p_after_c) + Pw * binary_entropy(p_after_w)
    return max(0.0, H_prior - H_post)
