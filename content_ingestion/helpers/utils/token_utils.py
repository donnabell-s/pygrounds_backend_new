"""
Token counting utilities for chunking optimization
"""
import tiktoken
from typing import Optional



def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    if not text:
        return 0
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        tokens = encoding.encode(text)
        return len(tokens)
    except Exception as e:
        print(f"Error counting tokens: {e}")
        return len(text) // 4

def estimate_cost(token_count: int, model: str = "gpt-4") -> dict:
    pricing = {
        "gpt-4": {"input": 0.03 / 1000, "output": 0.06 / 1000},
        "gpt-3.5-turbo": {"input": 0.001 / 1000, "output": 0.002 / 1000},
        "text-embedding-ada-002": {"input": 0.0001 / 1000, "output": 0},
    }
    if model not in pricing:
        model = "gpt-4"
    input_cost = token_count * pricing[model]["input"]
    return {
        "token_count": token_count,
        "model": model,
        "estimated_input_cost_usd": round(input_cost, 6),
        "cost_per_1k_tokens": pricing[model]["input"] * 1000,
    }

def analyze_chunk_sizes(chunks: list, encoding_name: str = "cl100k_base") -> dict:
    token_counts = []
    for chunk in chunks:
        if hasattr(chunk, 'text'):
            text = chunk.text
        else:
            text = str(chunk)
        token_count = count_tokens(text, encoding_name)
        token_counts.append(token_count)
    if not token_counts:
        return {"error": "No chunks provided"}
    return {
        "total_chunks": len(token_counts),
        "total_tokens": sum(token_counts),
        "avg_tokens_per_chunk": round(sum(token_counts) / len(token_counts), 2),
        "min_tokens": min(token_counts),
        "max_tokens": max(token_counts),
        "encoding": encoding_name,
        "chunks_over_1k": len([c for c in token_counts if c > 1000]),
        "chunks_over_2k": len([c for c in token_counts if c > 2000]),
        "chunks_over_4k": len([c for c in token_counts if c > 4000]),
    }


def count_tokens_for_chunk(text: str, encoding_name: str = "cl100k_base") -> int:
    return count_tokens(text, encoding_name)


def get_optimal_chunk_size(target_tokens: int = 1000, encoding_name: str = "cl100k_base") -> dict:
    chars_per_token = 4
    return {
        "target_tokens": target_tokens,
        "estimated_characters": target_tokens * chars_per_token,
        "estimated_words": target_tokens * 0.75,
        "encoding": encoding_name,
        "recommended_max": target_tokens * 1.2,
        "recommended_min": target_tokens * 0.5,
    }


class TokenCounter:
    """
    Class-based wrapper around token counting functions for backward compatibility.
    """
    
    def __init__(self, encoding_name: str = "cl100k_base"):
        self.encoding_name = encoding_name
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return count_tokens(text, self.encoding_name)
    
    def estimate_cost(self, token_count: int, model: str = "gpt-4") -> dict:
        """Estimate cost for token usage."""
        return estimate_cost(token_count, model)
    
    def analyze_chunks(self, chunks: list) -> dict:
        """Analyze token distribution across chunks."""
        return analyze_chunk_sizes(chunks, self.encoding_name)
