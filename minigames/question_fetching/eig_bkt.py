import math
from typing import Dict


def eig_for_question(
    prior_knowledge: float,
    question_difficulty: float = 0.5,
    guess: float = 0.25,
    slip: float = 0.15
) -> float:

    #clamp
    K = max(0.0, min(1.0, prior_knowledge))
    d = max(0.0, min(1.0, question_difficulty))
    g = max(0.0, min(0.5, guess))
    s = max(0.0, min(0.5, slip))
    
    #adjust guess/slip based on difficulty
    g_adj = g * (1 - 0.3 * d)  
    s_adj = s * (1 + 0.5 * d)  
    
    #probability of correct answer
    p_correct = K * (1 - s_adj) + (1 - K) * g_adj
    p_correct = max(0.01, min(0.99, p_correct))  # avoid log(0)
    
    #posterior if answer correct
    K_if_correct = (K * (1 - s_adj)) / p_correct
    K_if_correct = max(0.0, min(1.0, K_if_correct))
    
    #posterior if answer incorrect
    p_incorrect = 1 - p_correct
    K_if_incorrect = (K * s_adj) / p_incorrect if p_incorrect > 0 else K
    K_if_incorrect = max(0.0, min(1.0, K_if_incorrect))
    
    #if user knows a subtopic
    def entropy(p):
        p = max(0.001, min(0.999, p))
        return -p * math.log2(p) - (1 - p) * math.log2(1 - p)
    
    H_prior = entropy(K)
    
    #expected posterior entropy
    H_posterior = p_correct * entropy(K_if_correct) + p_incorrect * entropy(K_if_incorrect)
    
    eig = H_prior - H_posterior
    
    return max(0.0, eig)


def compute_eig_scores(
    user_ability: float,
    mastery_map: Dict[int, float],
    question_subtopic_map: Dict[int, int],
    question_difficulty_map: Dict[int, float]
) -> Dict[int, float]:

    eig_scores = {}
    
    for q_id, subtopic_id in question_subtopic_map.items():

        mastery_level = mastery_map.get(subtopic_id, 0.0)
        K_s = mastery_level / 100.0
        
        #personal prior
        prior = 0.7 * K_s + 0.3 * user_ability
        prior = max(0.0, min(1.0, prior))
        
        difficulty = question_difficulty_map.get(q_id, 0.5)
        
        eig = eig_for_question(prior, difficulty)
        eig_scores[q_id] = eig
    
    return eig_scores
