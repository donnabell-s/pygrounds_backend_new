"""
Token counting utilities for chunking optimization
"""
import tiktoken
from typing import Optional


class TokenCounter:
    """Utility class for counting tokens in text using various encodings"""
    
    def __init__(self, encoding_name: str = "cl100k_base"):
        """
        Initialize token counter with specified encoding.
        
        Args:
            encoding_name: tiktoken encoding name. Options:
                - "cl100k_base": GPT-4, GPT-3.5-turbo, text-embedding-ada-002
                - "p50k_base": Codex models, text-davinci-002, text-davinci-003
                - "r50k_base": GPT-3 models like davinci
        """
        self.encoding_name = encoding_name
        try:
            self.encoding = tiktoken.get_encoding(encoding_name)
        except Exception as e:
            # Fallback to cl100k_base if encoding not found
            print(f"Warning: Could not load encoding {encoding_name}, falling back to cl100k_base")
            self.encoding = tiktoken.get_encoding("cl100k_base")
            self.encoding_name = "cl100k_base"
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in the given text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        if not text:
            return 0
        
        try:
            tokens = self.encoding.encode(text)
            return len(tokens)
        except Exception as e:
            print(f"Error counting tokens: {e}")
            # Fallback: rough estimate (1 token ≈ 4 characters for English)
            return len(text) // 4
    
    def estimate_cost(self, token_count: int, model: str = "gpt-4") -> dict:
        """
        Estimate API costs based on token count.
        
        Args:
            token_count: Number of tokens
            model: Model name for pricing
            
        Returns:
            Dict with cost estimates
        """
        # Pricing as of 2024 (these may change)
        pricing = {
            "gpt-4": {"input": 0.03 / 1000, "output": 0.06 / 1000},
            "gpt-3.5-turbo": {"input": 0.001 / 1000, "output": 0.002 / 1000},
            "text-embedding-ada-002": {"input": 0.0001 / 1000, "output": 0},
        }
        
        if model not in pricing:
            model = "gpt-4"  # Default fallback
        
        input_cost = token_count * pricing[model]["input"]
        
        return {
            "token_count": token_count,
            "model": model,
            "estimated_input_cost_usd": round(input_cost, 6),
            "cost_per_1k_tokens": pricing[model]["input"] * 1000,
        }
    
    def analyze_chunk_sizes(self, chunks: list) -> dict:
        """
        Analyze token distribution across chunks.
        
        Args:
            chunks: List of chunk texts or DocumentChunk objects
            
        Returns:
            Analysis statistics
        """
        token_counts = []
        
        for chunk in chunks:
            if hasattr(chunk, 'text'):
                text = chunk.text
            else:
                text = str(chunk)
            
            token_count = self.count_tokens(text)
            token_counts.append(token_count)
        
        if not token_counts:
            return {"error": "No chunks provided"}
        
        return {
            "total_chunks": len(token_counts),
            "total_tokens": sum(token_counts),
            "avg_tokens_per_chunk": round(sum(token_counts) / len(token_counts), 2),
            "min_tokens": min(token_counts),
            "max_tokens": max(token_counts),
            "encoding": self.encoding_name,
            "chunks_over_1k": len([c for c in token_counts if c > 1000]),
            "chunks_over_2k": len([c for c in token_counts if c > 2000]),
            "chunks_over_4k": len([c for c in token_counts if c > 4000]),
        }


def count_tokens_for_chunk(text: str, encoding_name: str = "cl100k_base") -> int:
    """
    Quick function to count tokens for a single chunk.
    
    Args:
        text: Text content to count
        encoding_name: tiktoken encoding to use
        
    Returns:
        Number of tokens
    """
    counter = TokenCounter(encoding_name)
    return counter.count_tokens(text)


def get_optimal_chunk_size(target_tokens: int = 1000, encoding_name: str = "cl100k_base") -> dict:
    """
    Get recommendations for chunk sizing based on target token count.
    
    Args:
        target_tokens: Target number of tokens per chunk
        encoding_name: tiktoken encoding to use
        
    Returns:
        Recommendations dict
    """
    # Rough estimates for character counts (varies by language/content)
    chars_per_token = 4  # Average for English text
    
    return {
        "target_tokens": target_tokens,
        "estimated_characters": target_tokens * chars_per_token,
        "estimated_words": target_tokens * 0.75,  # ~0.75 words per token
        "encoding": encoding_name,
        "recommended_max": target_tokens * 1.2,  # 20% buffer
        "recommended_min": target_tokens * 0.5,   # 50% minimum
    }
