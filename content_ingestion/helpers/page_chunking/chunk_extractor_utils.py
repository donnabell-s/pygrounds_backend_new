import re
from unstructured.partition.pdf import partition_pdf
from unstructured.chunking.title import chunk_by_title
from unstructured.cleaners.core import clean_extra_whitespace

# Heuristic chunk classifier
def infer_chunk_type(text, default="Text"):
    text_lower = text.lower()
    if text.strip().startswith(">>>") or ">>>" in text or "..." in text:
        return "Code"
    elif "try it" in text_lower or "try this" in text_lower:
        return "Exercise"
    elif re.match(r"(module|chapter|section)\s+\d+", text_lower):
        return "Lesson"
    elif "for example" in text_lower or text_lower.startswith("example:"):
        return "Example"
    elif "exercise" in text_lower:
        return "Exercise"
    else:
        return default

# Remove visual duplicates and normalize chunk text
def clean_chunk_text(text):
    lines = text.strip().split("\n")
    if len(lines) > 1 and lines[0].strip() == lines[1].strip():
        lines.pop(0)
    if len(lines) == 1:
        segments = lines[0].split()
        mid = len(segments) // 2
        if segments[:mid] == segments[mid:]:
            lines[0] = " ".join(segments[:mid])
    return re.sub(r"\s+", " ", "\n".join(lines)).strip()

# Parse PDF into text chunks
def extract_unstructured_chunks(file_path):
    raw_elements = partition_pdf(filename=file_path, strategy="hi_res")
    cleaned_elements = []
    for el in raw_elements:
        if hasattr(el, "text") and el.text:
            el.text = clean_extra_whitespace(el.text)
            cleaned_elements.append(el)

    chunks = chunk_by_title(cleaned_elements, max_characters=500, overlap=50)

    return [{
        "content": clean_chunk_text(chunk.text if hasattr(chunk, "text") else str(chunk)),
        "chunk_type": infer_chunk_type(chunk.text if hasattr(chunk, "text") else str(chunk)),
        "source": "unstructured"
    } for chunk in chunks]

# Unified callable
def extract_chunks(document_id, toc_entry, pdf_path):
    return extract_unstructured_chunks(pdf_path)
