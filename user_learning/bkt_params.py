BKT_PARAMS = {
    "proficient": {
        "p_slip":    0.05,
        "p_guess":   0.20,
        "p_transit": 0.10,
        "p_forget":  0.02,
    },
    "mid": {
        "p_slip":    0.10,
        "p_guess":   0.25,
        "p_transit": 0.10,
        "p_forget":  0.03,
    },
    "novice": {
        "p_slip":    0.15,
        "p_guess":   0.30,
        "p_transit": 0.10,
        "p_forget":  0.05,
    },
}

DEFAULT_PARAMS = BKT_PARAMS["mid"]
