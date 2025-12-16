import re
from typing import Optional


def infer_chunk_type(text: str, default: str = "Concept") -> str:
    text_lower = text.lower()
    text_stripped = text.strip()
    
    # CODING-RELATED CONTENT header names
    
    # 1. if header code
    if _is_code_content(text, text_lower, text_stripped):
        return "Code"
    
    # 2. Try_It 
    if _is_try_it_content(text_lower):
        return "Try_It"
    
    # 3. Exercise 
    if _is_exercise_content(text_lower):
        return "Exercise"
    
    # 4. Example
    if _is_example_content(text, text_lower):
        return "Example"
    
    # CONCEPTUAL CONTENT (paragraphs)
    if _is_conceptual_content(text, text_lower):
        return "Concept"
    return "Concept"

#check for type indicators
def _is_code_content(text: str, text_lower: str, text_stripped: str) -> bool:
    coding_indicators = [
        text_stripped.startswith(">>>"),
        ">>>" in text,
        "..." in text and (">>>" in text or "def " in text),
        text_stripped.startswith(("import ", "from ", "def ", "class ", "if __name__")),
        re.search(r'^\s*(def|class|import|from)\s+\w+', text, re.MULTILINE),
        re.search(r'[a-zA-Z_]\w*\s*=\s*[^=]', text), 
        re.search(r'print\s*\(.*\)', text),
        re.search(r'return\s+\w+', text),
        text.count('{') > 0 and text.count('}') > 0,  
        text.count('[') > 1 and text.count(']') > 1,  
    ]
    
    return any(coding_indicators)


def _is_try_it_content(text_lower: str) -> bool:
    try_it_indicators = [
        "try it" in text_lower,
        "try this" in text_lower, 
        "give it a try" in text_lower,
        "now try" in text_lower,
        "your turn" in text_lower and ("code" in text_lower or "write" in text_lower),
        "hands-on" in text_lower,
        "interactive" in text_lower and ("session" in text_lower or "example" in text_lower),
    ]
    
    return any(try_it_indicators)


def _is_exercise_content(text_lower: str) -> bool:
    exercise_indicators = [
        "exercise" in text_lower and ("write" in text_lower or "code" in text_lower or "implement" in text_lower),
        "practice" in text_lower and ("coding" in text_lower or "programming" in text_lower),
        "challenge" in text_lower and ("code" in text_lower or "implement" in text_lower),
        "assignment" in text_lower and ("write" in text_lower or "create" in text_lower),
        "task:" in text_lower or "problem:" in text_lower,
        "implement" in text_lower and ("function" in text_lower or "class" in text_lower or "method" in text_lower),
    ]
    
    return any(exercise_indicators)


def _is_example_content(text: str, text_lower: str) -> bool:
    has_code_elements = (
        ("def " in text or "class " in text or "import " in text) or 
        (">>>" in text) or 
        (text.count('(') > 2 and text.count(')') > 2)
    )
    
    example_with_code_indicators = [
        ("example" in text_lower or "demonstration" in text_lower) and has_code_elements,
        "here's how" in text_lower and ("code" in text_lower or "write" in text_lower or "implement" in text_lower),
        "sample code" in text_lower,
        "code snippet" in text_lower,
        "following code" in text_lower,
        "code below" in text_lower or "code above" in text_lower,
        "usage example" in text_lower and ("function" in text_lower or "method" in text_lower or "class" in text_lower),
    ]
    
    return any(example_with_code_indicators)


def _is_conceptual_content(text: str, text_lower: str) -> bool:
    conceptual_indicators = [
        " is defined as " in text_lower,
        " refers to " in text_lower,
        " means " in text_lower,
        "definition:" in text_lower,
        "in other words" in text_lower,
        "simply put" in text_lower,
        "to understand" in text_lower,
        "concept" in text_lower,
        "principle" in text_lower,
        "theory" in text_lower,
        
     
        "key term" in text_lower,
        "important to note" in text_lower,
        "terminology" in text_lower,
        "glossary" in text_lower,
        
      
        "explanation" in text_lower and not any(code_word in text_lower for code_word in ["code", "implementation", "write", "program"]),
        "why" in text_lower and "?" in text, 
        "what" in text_lower and "?" in text,
        "when" in text_lower and "?" in text,
        "how" in text_lower and "?" in text and not ("code" in text_lower or "implement" in text_lower),
        
        
        "introduction" in text_lower,
        "background" in text_lower,
        "overview" in text_lower,
        "history" in text_lower,
        "evolution" in text_lower,
    ]
    
   
    has_no_code = not any([
        "def " in text,
        "class " in text,
        "import " in text,
        ">>>" in text,
        re.search(r'[a-zA-Z_]\w*\s*=\s*[^=]', text),  
        re.search(r'print\s*\(', text),
        text.count('(') > 3 and text.count(')') > 3,  
    ])
    
   
    if any(conceptual_indicators) and has_no_code:
        return True
    
    technical_terms_count = sum(1 for term in [
        "algorithm", "data structure", "variable", "function", "method", "object", "class",
        "inheritance", "polymorphism", "encapsulation", "abstraction", "module", "library",
        "framework", "API", "protocol", "syntax", "semantics", "compiler", "interpreter"
    ] if term in text_lower)
    
    return technical_terms_count > 0 and has_no_code
