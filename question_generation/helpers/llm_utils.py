# llm_utils.py

from openai import OpenAI
import os
import logging

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_API_URL")

# Temperature settings for different question types
CODING_TEMPERATURE = 0.0    # Very deterministic for coding questions
NON_CODING_TEMPERATURE = 0.5  # More creative for non-coding questions


client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)

def send_llm_messages(messages, tools=None, model="deepseek-chat", **kwargs):
    # Send messages to DeepSeek LLM
    # Parameters:
    # - messages: Chat message list in OpenAI format
    # - tools: Optional function definitions for tool use
    # - model: Model to use (default: deepseek-chat)
    # - kwargs: Additional OpenAI API parameters
    params = {
        "model": model,
        "messages": messages,
    }
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
    # Simple one-shot prompt to DeepSeek, returns text response
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    msg = send_llm_messages(messages, model=model, **kwargs)
    return msg.content
