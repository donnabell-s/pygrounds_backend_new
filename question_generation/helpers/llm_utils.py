from openai import OpenAI
import os
import logging

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_API_URL")
DEEPSEEK_TIMEOUT_SECONDS = float(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "180"))

CODING_TEMPERATURE = 0.0
NON_CODING_TEMPERATURE = 0.8

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    timeout=DEEPSEEK_TIMEOUT_SECONDS,
)


def send_llm_messages(messages, tools=None, model="deepseek-chat", **kwargs):
    params = {"model": model, "messages": messages}
    if tools:
        params["tools"] = tools
    params.update(kwargs)
    try:
        response = client.chat.completions.create(**params)
        return response.choices[0].message
    except Exception as e:
        logger.error(f"DeepSeek LLM call failed: {e}")
        raise


def invoke_deepseek(prompt, system_prompt="You are a helpful assistant.", model="deepseek-chat", **kwargs):
    """One-shot prompt to DeepSeek; returns text content."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": prompt},
    ]
    kwargs.setdefault("max_tokens", 8000)
    return send_llm_messages(messages, model=model, **kwargs).content
