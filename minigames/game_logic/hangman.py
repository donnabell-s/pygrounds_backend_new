import traceback

def run_user_code(user_code: str, function_name: str, test_cases: list):
    """
    Executes the user-submitted Python code and validates the target function
    against the provided test cases.

    Parameters:
    - user_code (str): The raw Python code from the user.
    - function_name (str): The expected function the user should define.
    - test_cases (list): A list of {"input": "...", "output": "..."} pairs.

    Returns:
    - (bool) Whether all tests passed.
    - (str) A message or reason.
    - (str) Optional traceback (empty string if no exception occurred).
    """
    local_env = {}

    try:
        # Run the user's code in isolated local environment
        exec(user_code, {}, local_env)
    except Exception as e:
        return False, f"Code error during compilation: {e}", traceback.format_exc()

    func = local_env.get(function_name)
    if not callable(func):
        return False, f"Function `{function_name}` not found or not callable.", ""

    for idx, test in enumerate(test_cases, 1):
        try:
            # Convert string input to tuple args
            args = eval(test["input"])
            if not isinstance(args, tuple):
                args = (args,)  # Ensure args is a tuple

            result = func(*args)
            expected = test["output"]

            # Normalize to string for comparison
            if str(result) != str(expected):
                return (
                    False,
                    f"Test case {idx} failed.\nInput: {test['input']}\nExpected: {expected}\nGot: {result}",
                    ""
                )
        except Exception as e:
            return (
                False,
                f"Exception during test case {idx}: {e}",
                traceback.format_exc()
            )

    return True, "All test cases passed!", ""
