from dataclasses import dataclass
import math
from typing import Optional, Tuple
from .utils import DIFF_ONEHOT, _norm_diff, _diff_centered

@dataclass
class BKTParams:
    p_L0: float = 0.20
    p_T: float = 0.10
    p_T_wrong: float = 0.02
    p_S: float = 0.10
    p_G: float = 0.20
    decay_wrong: float = 0.90
    min_floor: float = 0.001
    max_ceiling: float = 0.999

@dataclass
class PFACoeffs:
    beta0: float = -1.00
    beta_win: float = 0.35
    beta_fail: float = -0.60
    b_beg: float = +0.30
    b_int: float = 0.00
    b_adv: float = -0.25
    b_mas: float = -0.45

def bkt_update_once(p_know: float, correct: bool, p: BKTParams) -> float:
    if correct:
        num = p_know * (1.0 - p.p_S)
        den = num + (1.0 - p_know) * p.p_G
    else:
        num = p_know * p.p_S
        den = num + (1.0 - p_know) * (1.0 - p.p_G)
    post = 0.0 if den == 0 else num / den
    pT_use = p.p_T if correct else p.p_T_wrong
    p_next = post + (1.0 - post) * pT_use
    if not correct:
        p_next *= p.decay_wrong
    return max(p.min_floor, min(p.max_ceiling, p_next))

def bkt_update_fractional(p_know: float, correct: bool, p: BKTParams, impact: float) -> float:
    rounds = int(max(0, math.floor(impact)))
    for _ in range(rounds):
        p_know = bkt_update_once(p_know, correct, p)
    frac = max(0.0, impact - rounds)
    if frac > 1e-6:
        p_soft = BKTParams(
            p_L0=p.p_L0,
            p_T=max(1e-6, min(0.95, p.p_T * frac)),
            p_S=p.p_S,
            p_G=p.p_G,
            decay_wrong=1.0 - (1.0 - p.decay_wrong) * frac,
            min_floor=p.min_floor,
            max_ceiling=p.max_ceiling,
        )
        p_know = bkt_update_once(p_know, correct, p_soft)
    return p_know

def pfa_prob(wins: float, fails: float, difficulty: str, c: PFACoeffs) -> float:
    beg, inter, adv, mas = DIFF_ONEHOT[_norm_diff(difficulty)]
    z = (
        c.beta0
        + c.beta_win * wins
        + c.beta_fail * fails
        + c.b_beg * beg
        + c.b_int * inter
        + c.b_adv * adv
        + c.b_mas * mas
    )
    return 1.0 / (1.0 + math.exp(-z))

def _observe_params_with_difficulty(base: BKTParams, level: int) -> Tuple[float, float, float]:
    c = _diff_centered(level)
    s_k, g_k, d_k = 0.04, 0.04, 0.07
    p_S_eff = max(0.06, min(0.14, base.p_S + s_k * c))
    p_G_eff = max(0.12, min(0.28, base.p_G - g_k * c))
    target_easy, target_hard = 0.80, 0.98
    target = target_hard if c > 0 else target_easy
    decay_eff = base.decay_wrong + d_k * (target - base.decay_wrong)
    decay_eff = decay_eff + 0.05 * c
    decay_eff = max(0.80, min(0.98, decay_eff))
    return p_S_eff, p_G_eff, decay_eff
