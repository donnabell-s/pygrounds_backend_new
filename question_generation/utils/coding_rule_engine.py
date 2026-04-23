# question_generation/utils/coding_rule_engine.py

import re

# AST parsing is best if questions contain real code snippets.
# We keep it safe: if ast fails, we fallback to regex.
try:
    import ast
except Exception:
    ast = None


def _extract_code(text: str) -> str:
    """
    Extract code from markdown code blocks if present; otherwise return original text.
    """
    if not text:
        return ""
    blocks = re.findall(r"```(?:python)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if blocks:
        return "\n".join(blocks).strip()
    return text


def _regex_has(pat: str, text: str) -> bool:
    return re.search(pat, text, flags=re.IGNORECASE) is not None


def _regex_count(pat: str, text: str) -> int:
    return len(re.findall(pat, text, flags=re.IGNORECASE))


def _ast_features(code: str) -> dict:
    """
    Extract structural features from Python code using AST.
    Returns a dict of feature counts / flags.
    """
    feats = {
        "has_function": False,
        "has_class": False,
        "has_try": False,
        "has_with": False,
        "has_lambda": False,
        "has_comprehension": False,
        "has_recursion": False,
        "has_async": False,
        "has_yield": False,
        "loop_count": 0,
        "if_count": 0,
        "nested_loop": False,
        "nested_if": False,
    }

    if not ast:
        return feats

    try:
        tree = ast.parse(code)
    except Exception:
        return feats

    current_func = []

    class LoopDepthVisitor(ast.NodeVisitor):
        def __init__(self):
            self.loop_depth = 0
            self.if_depth = 0

        def visit_FunctionDef(self, node):
            feats["has_function"] = True
            current_func.append(node.name)
            self.generic_visit(node)
            current_func.pop()

        def visit_AsyncFunctionDef(self, node):
            feats["has_function"] = True
            feats["has_async"] = True
            current_func.append(node.name)
            self.generic_visit(node)
            current_func.pop()

        def visit_ClassDef(self, node):
            feats["has_class"] = True
            self.generic_visit(node)

        def visit_For(self, node):
            feats["loop_count"] += 1
            self.loop_depth += 1
            if self.loop_depth >= 2:
                feats["nested_loop"] = True
            self.generic_visit(node)
            self.loop_depth -= 1

        def visit_While(self, node):
            feats["loop_count"] += 1
            self.loop_depth += 1
            if self.loop_depth >= 2:
                feats["nested_loop"] = True
            self.generic_visit(node)
            self.loop_depth -= 1

        def visit_If(self, node):
            feats["if_count"] += 1
            self.if_depth += 1
            if self.if_depth >= 2:
                feats["nested_if"] = True
            self.generic_visit(node)
            self.if_depth -= 1

        def visit_Try(self, node):
            feats["has_try"] = True
            self.generic_visit(node)

        def visit_With(self, node):
            feats["has_with"] = True
            self.generic_visit(node)

        def visit_Lambda(self, node):
            feats["has_lambda"] = True
            self.generic_visit(node)

        def visit_ListComp(self, node):
            feats["has_comprehension"] = True
            self.generic_visit(node)

        def visit_DictComp(self, node):
            feats["has_comprehension"] = True
            self.generic_visit(node)

        def visit_SetComp(self, node):
            feats["has_comprehension"] = True
            self.generic_visit(node)

        def visit_GeneratorExp(self, node):
            feats["has_comprehension"] = True
            self.generic_visit(node)

        def visit_Yield(self, node):
            feats["has_yield"] = True
            self.generic_visit(node)

        def visit_YieldFrom(self, node):
            feats["has_yield"] = True
            self.generic_visit(node)

        def visit_Call(self, node):
            # Detect recursion: function calls itself inside its own body
            if current_func and isinstance(node.func, ast.Name):
                if node.func.id == current_func[-1]:
                    feats["has_recursion"] = True
            self.generic_visit(node)

    LoopDepthVisitor().visit(tree)
    return feats


def _coding_score(text: str) -> tuple:
    """
    Returns: (score, reasons[])
    Score is based on structure and task demand, not keyword difficulty lists.
    """
    reasons = []
    t = (text or "").strip()
    low = t.lower()
    code = _extract_code(t)

    score = 0

    # -------- Task intent (what student must do) --------
    if _regex_has(r"\b(trace|predict the output|what is the output|what will be printed)\b", low):
        score += 3
        reasons.append("Task: output tracing (+3)")

    if _regex_has(r"\b(debug|fix|correct|why|explain why)\b", low):
        score += 3
        reasons.append("Task: debug/analyze (+3)")

    if _regex_has(r"\b(implement|write|create|program)\b", low):
        score += 2
        reasons.append("Task: implement/create (+2)")

    # -------- Structural signals (AST first, regex fallback) --------
    feats = _ast_features(code)

    ast_used = ast is not None and (
        feats["has_function"] or feats["loop_count"] > 0 or feats["if_count"] > 0 or feats["has_class"]
    )

    if ast_used:
        if feats["has_recursion"]:
            score += 5
            reasons.append("Structure: recursion detected (AST) (+5)")

        if feats["has_async"]:
            score += 5
            reasons.append("Structure: async detected (AST) (+5)")

        if feats["has_yield"]:
            score += 4
            reasons.append("Structure: yield/generator detected (AST) (+4)")

        if feats["has_class"]:
            score += 3
            reasons.append("Structure: class detected (AST) (+3)")

        if feats["has_try"]:
            score += 3
            reasons.append("Structure: try/except detected (AST) (+3)")

        if feats["has_with"]:
            score += 2
            reasons.append("Structure: context manager (with) detected (AST) (+2)")

        if feats["has_comprehension"]:
            score += 2
            reasons.append("Structure: comprehension detected (AST) (+2)")

        if feats["nested_loop"]:
            score += 3
            reasons.append("Structure: nested loops detected (AST) (+3)")
        else:
            if feats["loop_count"] >= 1:
                score += 2
                reasons.append("Structure: loop detected (AST) (+2)")

        if feats["nested_if"]:
            score += 2
            reasons.append("Structure: nested if detected (AST) (+2)")
        else:
            if feats["if_count"] >= 1:
                score += 1
                reasons.append("Structure: if detected (AST) (+1)")

        if feats["has_lambda"]:
            score += 2
            reasons.append("Structure: lambda detected (AST) (+2)")

    else:
        # Regex fallback (less accurate, lower weights)
        if _regex_has(r"\brecurs(ion|ive)\b", low):
            score += 4
            reasons.append("Structure: recursion hint (regex) (+4)")

        if _regex_has(r"\basync\b|\bawait\b", code):
            score += 4
            reasons.append("Structure: async/await hint (regex) (+4)")

        if _regex_has(r"\byield\b", code):
            score += 3
            reasons.append("Structure: yield hint (regex) (+3)")

        if _regex_has(r"\bclass\b", code):
            score += 3
            reasons.append("Structure: class hint (regex) (+3)")

        if _regex_has(r"\btry\b.*\bexcept\b", code):
            score += 3
            reasons.append("Structure: try/except hint (regex) (+3)")

        if _regex_count(r"\bfor\b|\bwhile\b", code) >= 2:
            score += 3
            reasons.append("Structure: nested loops hint (regex) (+3)")
        elif _regex_has(r"\bfor\b|\bwhile\b", code):
            score += 2
            reasons.append("Structure: loop hint (regex) (+2)")

        if _regex_count(r"\bif\b", code) >= 2:
            score += 2
            reasons.append("Structure: nested if hint (regex) (+2)")
        elif _regex_has(r"\bif\b", code):
            score += 1
            reasons.append("Structure: if hint (regex) (+1)")

        if _regex_has(r"\[.*for.+in.+\]", code) or _regex_has(r"\{.*for.+in.+\}", code):
            score += 2
            reasons.append("Structure: comprehension hint (regex) (+2)")

    return score, reasons


def _score_to_label(score: int) -> str:
    """
    Map score to difficulty level for CODING rule suggestions.
    """
    if score >= 10:
        return "master"
    if score >= 7:
        return "advanced"
    if score >= 4:
        return "intermediate"
    return "beginner"


def refined_coding_rule_engine(text: str):
    """
    Returns:
      - "hard_master" / "hard_advanced" / "hard_intermediate" for must-not-miss constructs
      - otherwise: 'intermediate'/'advanced'/'master' conservatively
      - or None

    Notes:
    - hard_* are special tags handled by ml_classifier (converted to real labels).
    - We support BOTH:
        (1) structural detection via AST (best)
        (2) task-intent detection when prompt explicitly requires recursion, etc.
    """
    t = (text or "").strip()
    if not t:
        return None

    score, reasons = _coding_score(t)
    label = _score_to_label(score)
    low = t.lower()

    # -----------------------
    # HARD MASTER
    # -----------------------
    hard_master_patterns = [
        "recursion detected (AST)",
        "async detected (AST)",
        "yield/generator detected (AST)",
    ]
    for r in reasons:
        for p in hard_master_patterns:
            if p in r:
                return "hard_master"

    # Task-intent: explicitly requires recursion (even without code snippet)
    if _regex_has(r"\b(using recursion|use recursion|recursive|recursion)\b", low):
        return "hard_master"

    # -----------------------
    # HARD INTERMEDIATE (trace tasks with real code)
    # -----------------------
    if _regex_has(r"\b(trace|predict the output|what is the output|what will be printed)\b", low) and "```" in t:
        return "hard_intermediate"

    # -----------------------
    # HARD ADVANCED
    # -----------------------
    hard_advanced_patterns = [
        "nested loops detected (AST)",
        "try/except detected (AST)",
        "class detected (AST)",
    ]
    for r in reasons:
        for p in hard_advanced_patterns:
            if p in r:
                return "hard_advanced"

    # -----------------------
    # Conservative suggestions (non-hard)
    # -----------------------
    if label in ("advanced", "master"):
        return label

    if label == "intermediate" and score >= 5:
        return "intermediate"

    return None


def refined_coding_rule_engine_debug(text: str) -> dict:
    score, reasons = _coding_score(text or "")
    return {
        "score": score,
        "suggested": _score_to_label(score),
        "reasons": reasons,
    }
