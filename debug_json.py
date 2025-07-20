#!/usr/bin/env python
"""
Debug JSON loading and snippet selection
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Test JSON loading
def test_json_loading():
    print("Testing JSON loading...")
    
    try:
        # Import the function
        from question_generation.views import load_code_snippets
        
        snippets_data = load_code_snippets()
        if snippets_data:
            print("✅ JSON loaded successfully")
            print(f"Categories available: {list(snippets_data['python_snippets'].keys())}")
            
            # Test category finding
            from question_generation.views import CompareSubtopicAndGenerateView
            view = CompareSubtopicAndGenerateView()
            
            test_subtopic_name = "Using input() to Read User Data"
            category = view._find_relevant_snippet_category(test_subtopic_name, snippets_data)
            print(f"Relevant category for '{test_subtopic_name}': {category}")
            
            if category and category in snippets_data['python_snippets']:
                snippets = snippets_data['python_snippets'][category]['snippets']
                print(f"Found {len(snippets)} snippets in category '{category}'")
                if snippets:
                    first_snippet = snippets[0]
                    print(f"First snippet ID: {first_snippet['id']}")
                    print(f"First snippet concepts: {first_snippet.get('concepts', [])}")
            else:
                print("❌ No relevant category found")
        else:
            print("❌ JSON loading failed")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_json_loading()
