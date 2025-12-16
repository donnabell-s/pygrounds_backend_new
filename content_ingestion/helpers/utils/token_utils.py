# token counting helpers for chunking
import tiktoken
import logging

logger = logging.getLogger(__name__)



def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    if not text:
        return 0
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        tokens = encoding.encode(text)
        return len(tokens)
    except Exception as e:
        logger.warning("Error counting tokens with tiktoken: %s", e)
        return len(text) // 4

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
    # backward-compatible wrapper
    
    def __init__(self, encoding_name: str = "cl100k_base"):
        self.encoding_name = encoding_name
    
    def count_tokens(self, text: str) -> int:
        # count tokens in text
        return count_tokens(text, self.encoding_name)
    
    def analyze_chunks(self, chunks: list) -> dict:
        # summarize token distribution across chunks
        return analyze_chunk_sizes(chunks, self.encoding_name)
