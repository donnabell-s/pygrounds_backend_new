import traceback
import re

def run_user_code(user_code: str, function_name: str, test_cases: list):

    local_env = {}

    try:
        exec(user_code, {}, local_env)
    except Exception as e:
        return False, f"Code error during compilation: {e}", traceback.format_exc()

    func = local_env.get(function_name)
    if not callable(func):
        return False, f"Function `{function_name}` not found or not callable.", ""

    for idx, test in enumerate(test_cases, 1):
        try:

            if isinstance(test, dict):
                input_expr = test.get("input", "")
                expected = test.get("output", None)

            elif isinstance(test, str):

                if "output" in test:
                    parts = re.split(r",\s*output[:=]", test, maxsplit=1)
                    input_expr = parts[0].strip()
                    expected = parts[1].strip().strip("'\"") if len(parts) > 1 else None
                else:
                    input_expr = test.strip()
                    expected = None

            else:
                continue

            args = eval(input_expr)
            if not isinstance(args, tuple):
                args = (args,)

            result = func(*args)

            if expected is not None:
                try:
                    expected_eval = eval(expected)
                except Exception:
                    expected_eval = expected 

                if str(result) != str(expected_eval):
                    return (
                        False,
                        f"Test case {idx} failed.\nInput: {input_expr}\nExpected: {expected_eval}\nGot: {result}",
                        ""
                    )

        except Exception as e:
            return (
                False,
                f"Exception during test case {idx}: {e}",
                traceback.format_exc()
            )

    return True, "All test cases passed!", ""
