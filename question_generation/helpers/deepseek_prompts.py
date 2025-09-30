from typing import Dict, Any, Callable

class DeepSeekPromptManager:
    def __init__(self, max_rag_chars: int = 2400):
        self.max_rag_chars = max_rag_chars

    # -------- Utilities --------
    def _clip(self, s: str, n: int) -> str:
        if not s:
            return ""
        s = s.strip()
        return (s[: n - 1] + "…") if len(s) > n else s

    def _ctx(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # Safe access + clipping for rag_context
        c = dict(context)
        c["rag_context"] = self._clip(str(c.get("rag_context", "")), self.max_rag_chars)
        return c
    
    def _calc_difficulty_split(self, n: int) -> Dict[str, int]:
        """
        Ratio: 50% beginner, 40% intermediate, 10% advanced, and ONLY 1 master.
        - If n <= 0: all zeros.
        - If n >= 1: master = 1, remaining distributed by 50/40/10 with integer rounding.
        """
        if n <= 0:
            return {"beginner": 0, "intermediate": 0, "advanced": 0, "master": 0}

        master = 1
        rem = max(0, n - master)
        beginner = rem * 50 // 100
        intermediate = rem * 40 // 100
        advanced = rem - beginner - intermediate  # remainder goes to advanced

        # Final sanity (sum must equal n)
        total = beginner + intermediate + advanced + master
        if total < n:  # give leftovers to beginner, then intermediate, then advanced
            for k in ("beginner", "intermediate", "advanced"):
                if total >= n:
                    break
                if k == "beginner":
                    beginner += 1
                elif k == "intermediate":
                    intermediate += 1
                else:
                    advanced += 1
                total += 1
        elif total > n:  # trim from advanced, then intermediate, then beginner
            for k in ("advanced", "intermediate", "beginner"):
                if total <= n:
                    break
                if k == "advanced" and advanced > 0:
                    advanced -= 1
                elif k == "intermediate" and intermediate > 0:
                    intermediate -= 1
                elif k == "beginner" and beginner > 0:
                    beginner -= 1
                total -= 1

        return {
            "beginner": beginner,
            "intermediate": intermediate,
            "advanced": advanced,
            "master": master,
        }
    # -------- Router --------
    def get_prompt_for_minigame(self, game_type: str, context: Dict[str, Any]) -> str:
        routes: Dict[str, Callable[[Dict[str, Any]], str]] = {
            "coding": self.get_coding_prompt,
            "non_coding": self.get_non_coding_prompt,
            "pre_assessment": self.get_pre_assessment_prompt,
        }
        if game_type not in routes:
            raise ValueError(f"Unknown game_type: {game_type}")
        return routes[game_type](self._ctx(context))

    # -------- Prompts --------
    def get_coding_prompt(self, context: Dict[str, Any]) -> str:
        return (
                f"""OUTPUT ONLY VALID JSON ARRAY. NO prose, NO markdown, NO backticks.

                TASK: Generate {context['num_questions']} Python DEBUGGING questions for {context['subtopic_name']} ({context['difficulty']}).

                RAG_CONTEXT:
                <<<
                {context['rag_context']}
                >>>

                RULES (MUST):
                - Simple, real-world tasks; no external libs; < 20 lines/code.
                - snake_case function names.
                - Keep texts short and specific.

                ITEM SCHEMA (ALL FIELDS REQUIRED):
                {{
                  "question_text": "brief task (≤12 words)",
                  "buggy_question_text": "visible symptom (8–20 words)",
                  "explanation": "clear explanation of the main task/problem (20–40 words)",
                  "buggy_explanation": "explanation of the bug and debugging approach (20–40 words)",
                  "function_name": "snake_case",
                  "sample_input": "(example,)",
                  "sample_output": "expected",
                  "hidden_tests": [{{"input": "(test,)", "expected_output": "result"}}],
                  "buggy_code": "def name():\\n    # buggy version",
                  "correct_code": "def name():\\n    # working solution",
                  "buggy_correct_code": "def name():\\n    # fixed buggy version",
                  "difficulty": "{context['difficulty']}"
                }}

                RETURN: JSON array ONLY."""
                        ).strip()

    def get_non_coding_prompt(self, context: Dict[str, Any]) -> str:
          return (
            f"""OUTPUT ONLY VALID JSON ARRAY. NO prose, NO markdown, NO backticks.

            TASK: Create {context['num_questions']} Python concept CLUES for {context['subtopic_name']} ({context['difficulty']}).

            RAG_CONTEXT:
            <<<
            {context['rag_context']}
            >>>

            STYLE (CROSSWORD / WORD-SEARCH CLUES):
            - Write each question_text as a terse clue (glossary-style), natural and friendly.
            - No question marks, no quotes, no colons, no punctuation; letters/spaces only.
            - Avoid exam-y stems like Identify/Select/Name/Spot/Predict/Choose.
            - Keep clues ≤ 18 words; concise, definitional, or hint-like.
            - If a concept has multiple words, target the normalized single token (e.g., snakecase, shortcircuit).

            STRICT RULES:
            - Answer MUST be ONE domain term, lowercase letters only (a–z), 4–13 chars, no spaces/hyphens.
            - Use domain-specific targets from context (e.g., generator, decorator, iterator, docstring, sentinel, ducktyping, mutability).
            - Avoid generic answers (code, variable, python, function).
            - No True/False (unless the answer term itself is boolean-related, e.g., truthiness).

            GOOD CLUE EXAMPLES (style guide):
            - Inline comment should not duplicate this documentation block → docstring
            - Preferred python naming for functions and variables → snakecase
            - Benefit of data that cannot change after creation → immutability

            AVOID (too stiff / exam-like):
            - Identifies lazily produced sequence objects → generator
            - Name the feature enabling with-block resource control → contextmanager
            - Select the term for metadata-preserving wrapper → decorator

            ITEM SCHEMA:
            {{
              "question_text": "<terse clue (≤18 words, letters/spaces only, no punctuation)>",
              "answer": "<single domain term, lowercase, 4–13 letters>",
              "explanation": "<brief concept note, 20–40 words, friendly and clear>",
              "difficulty": "{context['difficulty']}"
            }}

            VALIDATION HINTS:
            - If the best candidate feels generic, choose a more specific technical term from RAG_CONTEXT.
            - Keep JSON compact. RETURN: JSON array ONLY."""
                ).strip()

    def get_pre_assessment_prompt(self, context: Dict[str, Any]) -> str:
        c = self._ctx(context)
        n = int(c["num_questions"])
        split = self._calc_difficulty_split(n)
        return f"""OUTPUT ONLY VALID JSON ARRAY. No prose, no markdown, no backticks.

                ROLE: Friendly Python educator creating a BEGINNER PRE-ASSESSMENT (zero prior coding).

                TOTAL QUESTIONS: {n}

                COMPREHENSIVE COVERAGE — USE EXACT SUBTOPIC NAMES (NO paraphrase):
                <<<
                {c['topics_and_subtopics']}
                >>>

                RAG_CONTEXT (optional, may be empty/trimmed):
                <<<
                {c.get('rag_context', '')}
                >>>

                DIFFICULTY COUNTS (MUST MATCH EXACTLY):
                - beginner: {split['beginner']}
                - intermediate: {split['intermediate']}
                - advanced: {split['advanced']}
                - master: {split['master']}

                DESIGN:
                - Welcoming tone, simple language, everyday analogies OK.
                - Each question may bundle 2–4 related subtopics.
                - Choices must be distinct and beginner-safe.

                ABSOLUTE MUSTS:
                - "subtopics_covered" MUST COPY names EXACTLY as listed above (character-for-character).
                - "correct_answer" MUST match exactly one of "choices".
                - Field "difficulty" MUST be one of: beginner|intermediate|advanced|master.
                - Total items MUST equal {n} and the per-difficulty counts MUST match the numbers above.

                ITEM SCHEMA:
                {{
                  "question_text": "<simple, friendly question>",
                  "choices": ["<A>", "<B>", "<C>", "<D>"],
                  "correct_answer": "<exactly one choice>",
                  "subtopics_covered": ["<exact name 1>", "<exact name 2>", "<exact name 3>"],
                  "difficulty": "beginner|intermediate|advanced|master"
                }}

                RETURN: JSON array ONLY.""".strip() 


# Global instance
deepseek_prompt_manager = DeepSeekPromptManager()
