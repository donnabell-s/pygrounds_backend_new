# Cross-Page Content Merging Solution

## Problem Solved ✅

You asked: *"one last thing for chunking, we have this 2 pages in a pdf and the code is cutoff to the 2nd page, how do we connect them?"*

## Solution Implemented

The **Cross-Page Content Merger** automatically detects and merges content that spans multiple pages, specifically handling your example:

### Your Example:
**Page 140 ends with:**
```python
>>> dir(MyClass)
['_MyClass__secret_value', '__class__', '__delattr__', '__dict__',
```

**Page 141 continues with:**
```python
'__dir__', '__doc__', '__eq__', '__format__', '__ge__', '__getattribute__',
'__gt__', '__hash__', '__init__', '__le__', '__lt__', '__module__',
'__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__',
'__setattr__', '__sizeof__', '__str__', '__subclasshook__', '__weakref__']
>>> instance_of._MyClass__secret_value
1
```

## How It Works

### 1. **Split Detection**
```python
def _is_split_code_block(chunk1: Dict[str, Any], chunk2: Dict[str, Any]) -> bool:
    """Detect if code blocks are split across pages."""
    text1, text2 = chunk1['text'].strip(), chunk2['text'].strip()
    
    # Incomplete list ending (your exact case)
    if re.search(r'\[.*,$', text1):
        if re.search(r'^.*\]', text2):
            return True
    
    # Incomplete Python statement
    if text1.endswith(',') and ('>>>' in text2 or 'def ' in text2):
        return True
```

### 2. **Smart Merging**
```python
def _merge_code_blocks(chunk1: Dict[str, Any], chunk2: Dict[str, Any]) -> Dict[str, Any]:
    """Merge split code blocks with proper formatting."""
    merged_text = chunk1['text'].rstrip()
    continuation = chunk2['text'].lstrip()
    
    # Remove page numbers and headers from continuation
    continuation = _clean_page_boundary(continuation)
    
    # Join with appropriate spacing
    if merged_text.endswith(','):
        merged_text += '\n' + continuation
    else:
        merged_text += ' ' + continuation
```

### 3. **Test Results**
```
Input: 3 chunks
  Chunk 1: Page 140, Type: Code, Length: 692
  Chunk 2: Page 141, Type: Code, Length: 612  
  Chunk 3: Page 141, Type: Concept, Length: 285

🔗 Merging chunks due to split_code_block: pages 140 and 141

Output: 2 chunks after merging
  Chunk 1: Page 140, Type: Code, Length: 1305  # ← MERGED!
  Chunk 2: Page 141, Type: Concept, Length: 285
```

## Integration Points

### 1. **Updated Extract Functions**
Both `extract_unstructured_chunks()` and `extract_chunks_with_subtopic_context()` now include cross-page processing:

```python
# Apply cross-page content merging
if len(processed_chunks) > 1:
    processed_chunks = merge_cross_page_content(processed_chunks)
```

### 2. **Patterns Handled**
- ✅ **Split Python code blocks** (your case)
- ✅ **Incomplete class/function definitions**
- ✅ **Broken sentences at page boundaries**
- ✅ **Split method explanations**
- ✅ **Incomplete imports/statements**

### 3. **Smart Context Preservation**
- Maintains chunk type consistency
- Preserves page number references
- Tracks merge metadata for debugging
- Cleans page boundaries (headers, page numbers)

## Benefits for Question Generation

### Before (Broken Context):
```
Chunk 1: ">>> dir(MyClass)\n['_MyClass__secret_value', '__class__',"
Chunk 2: "'__dir__', '__doc__', ...]\n>>> instance_of._MyClass__secret_value\n1"
```
**Problem**: Incomplete code context, broken examples

### After (Complete Context): 
```
Merged Chunk: ">>> dir(MyClass)\n['_MyClass__secret_value', '__class__', '__dir__', '__doc__', ...]\n>>> instance_of._MyClass__secret_value\n1"
```
**Result**: Complete, coherent code examples for better question generation

## Usage in Your Pipeline

The cross-page merger is now automatically integrated into your chunking pipeline. When you process PDFs, content that spans pages will be automatically detected and merged, providing complete context for both coding and conceptual questions.

This solves the exact problem you described where code examples were cut off across pages!
