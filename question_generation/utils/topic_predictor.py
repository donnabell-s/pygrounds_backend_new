import re

TOPIC_KEYWORDS = {
    "Variables": ["variable", "declare", "assign"],
    "Loops": ["for loop", "while loop", "iterate", "repeat"],
    "Conditionals": ["if", "else", "elif", "condition"],
    "Functions": ["function", "def", "parameter", "return"],
    "Recursion": ["recursion", "recursive"],
}

def clean_text(text):
    return re.sub(r'\W+', ' ', text.lower())

def predict_topic(text):
    ##Predicts the topic of a given question using keyword matching.
    ##It looks for specific Python-related keywords to determine if 
    ##the topic is Loops, Conditionals, Variables, etc.
    #Returns: Topic name as string (e.g. 'Loops', 'Conditionals')
    cleaned = clean_text(text)
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in cleaned:
                return topic
    return "Uncategorized"
