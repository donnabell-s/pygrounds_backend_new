import traceback
import re

def run_user_code(user_code: str, function_name: str, test_cases: list):
    """
    Executes the user-submitted Python code and validates the target function
    against the provided test cases.

    Supported test formats:
    1. Dict format (recommended):
       [{"input": "(1,2)", "output": "3"}, ...]
    2. Legacy string input:
       ["(1,2)", ...]  # output not checked
    3. Malformed legacy with output inside:
       ["(1,2),output:3", ...]  # auto-parsed

    Returns:
        (bool success, str message, str traceback)
    """

    local_env = {}

    # 1️⃣ Compile and load user code
    try:
        exec(user_code, {}, local_env)
    except Exception as e:
        return False, f"Code error during compilation: {e}", traceback.format_exc()

    # 2️⃣ Find target function
    func = local_env.get(function_name)
    if not callable(func):
        return False, f"Function `{function_name}` not found or not callable.", ""

    # 3️⃣ Iterate test cases
    for idx, test in enumerate(test_cases, 1):
        try:
            # ✅ Normalize test format
            if isinstance(test, dict):
                input_expr = test.get("input", "")
                expected = test.get("output", None)

            elif isinstance(test, str):
                # Handle legacy string test
                if "output" in test:
                    # Auto-split malformed strings like "(1,2),output:'3'"
                    parts = re.split(r",\s*output[:=]", test, maxsplit=1)
                    input_expr = parts[0].strip()
                    expected = parts[1].strip().strip("'\"") if len(parts) > 1 else None
                else:
                    input_expr = test.strip()
                    expected = None

            else:
                # Unsupported test type
                continue

            # ✅ Evaluate function arguments
            args = eval(input_expr)
            if not isinstance(args, tuple):
                args = (args,)

            # ✅ Run user function
            result = func(*args)

            # ✅ Compare result if expected is provided
            if expected is not None:
                try:
                    expected_eval = eval(expected)
                except Exception:
                    expected_eval = expected  # fallback to raw string

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
