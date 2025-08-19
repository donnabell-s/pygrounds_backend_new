#!/usr/bin/env python
"""
Populate PyGrounds database with predefined game zones, topics, and subtopics.
Run this script after migrating a fresh database to set up the learning structure.

Usage: python populate_zones.py
"""

import os
import sys
import django

# Add the parent directory to the Python path so we can import pygrounds_backend_new
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
django.setup()

from content_ingestion.models import GameZone, Topic, Subtopic


def generate_subtopic_embeddings(concept_intents_map=None, code_intents_map=None):
    """
    Generate embeddings for subtopics using the new ProcessPool system.
    Creates BOTH MiniLM (concept) and CodeBERT (code) embeddings for dual compatibility.

    Args:
        concept_intents_map: Optional dict {subtopic_id: concept_intent_text} (legacy support)
        code_intents_map:    Optional dict {subtopic_id: code_intent_text} (legacy support)
    """
    concept_intents_map = concept_intents_map or {}
    code_intents_map = code_intents_map or {}
    
    try:
        from multiprocessing import Pool
        import psutil
        from django.db import transaction
        from django.db.models import Q
        
        print("\n🔮 Generating dual embeddings for subtopics using ProcessPool system...")
        print("=" * 60)

        # Get subtopics without embeddings and with intent fields
        subtopics = Subtopic.objects.filter(
            embeddings__isnull=True
        ).filter(
            Q(concept_intent__isnull=False) | Q(code_intent__isnull=False)
        )
        
        print(f"\n📝 Found {subtopics.count()} subtopics ready for embedding generation...")

        if subtopics.count() == 0:
            print("✨ No subtopics need embedding generation!")
            return

        # Update all to processing status
        subtopics.update(embedding_status='processing')

        # Determine optimal number of processes
        cpu_count = psutil.cpu_count(logical=True)
        max_workers = min(4, max(1, cpu_count - 1))  # Use up to 4 processes, leave 1 CPU free
        print(f"🔋 Using {max_workers} worker processes...")

        # Prepare all tasks
        all_tasks = []
        for subtopic in subtopics:
            if subtopic.concept_intent:
                all_tasks.append((subtopic.id, 'concept'))
            if subtopic.code_intent:
                all_tasks.append((subtopic.id, 'code'))

        print(f"📋 Prepared {len(all_tasks)} embedding tasks...")

        success_count = 0
        failed_count = 0

        try:
            # Import the worker function from our separate module
            from content_ingestion.embedding_worker import generate_embedding_task
            
            print("\n🚀 Starting parallel embedding generation...")
            
            # Execute all tasks in parallel
            with Pool(processes=max_workers) as pool:
                results = pool.map(generate_embedding_task, all_tasks)
            
            print("📊 Processing results...")
            
            # Group results by subtopic ID
            subtopic_vectors = {}
            task_index = 0
            
            for model_type, vector in results:
                task_subtopic_id, task_model_type = all_tasks[task_index]
                
                if task_subtopic_id not in subtopic_vectors:
                    subtopic_vectors[task_subtopic_id] = {}
                    
                if vector is not None:
                    subtopic_vectors[task_subtopic_id][model_type] = vector
                    success_count += 1
                else:
                    failed_count += 1
                    
                task_index += 1

            # Process results by subtopic
            for subtopic in subtopics:
                subtopic_results = subtopic_vectors.get(subtopic.id, {})

                # Create embedding record if we have any vectors
                if subtopic_results:
                    from content_ingestion.models import Embedding
                    
                    try:
                        Embedding.objects.create(
                            subtopic=subtopic,
                            content_type='subtopic',
                            model_type='dual',
                            model_name=f"dual:minilm+codebert",
                            dimension=384,  # Standard dimension
                            minilm_vector=subtopic_results.get('concept'),
                            codebert_vector=subtopic_results.get('code')
                        )
                        
                        # Update status to completed
                        subtopic.embedding_status = 'completed'
                        subtopic.embedding_error = None
                        subtopic.save()
                        
                        print(f"  ✅ {subtopic.name}")
                        intent_status = []
                        if 'concept' in subtopic_results:
                            intent_status.append("Concept: ✓")
                        if 'code' in subtopic_results:
                            intent_status.append("Code: ✓")
                        print(f"     {' | '.join(intent_status)}")
                        
                    except Exception as e:
                        print(f"  ❌ Failed to save embedding for '{subtopic.name}': {e}")
                        subtopic.embedding_status = 'failed'
                        subtopic.embedding_error = str(e)
                        subtopic.save()
                else:
                    print(f"  ❌ No embeddings generated for '{subtopic.name}'")
                    subtopic.embedding_status = 'failed'
                    subtopic.embedding_error = 'No embeddings were generated'
                    subtopic.save()

        except Exception as e:
            print(f"❌ Error during parallel processing: {e}")
            # Update all to failed status
            subtopics.update(embedding_status='failed', embedding_error=str(e))
            failed_count = subtopics.count()

        print(f"\n🎉 Subtopic embedding generation complete!")
        print(f"  • Total subtopics processed: {subtopics.count()}")
        print(f"  • Successful embeddings: {success_count}")
        print(f"  • Failed: {failed_count}")
        
        # Count total embeddings
        try:
            total_with_embeddings = Subtopic.objects.filter(embeddings__isnull=False).distinct().count()
            print(f"  • Subtopics with embeddings: {total_with_embeddings}")
        except Exception:
            pass

    except ImportError as e:
        print(f"\n⚠️  Embedding system not available: {e}")
        print("   Subtopics created without embeddings")
        print("   You can generate embeddings later using the admin interface")
    except Exception as e:
        print(f"\n❌ Error generating embeddings: {e}")
        print("   Subtopics created without embeddings")


def populate_zones():
    """
    Populate the database with predefined zones, topics, and subtopics.
    This will completely overwrite any existing data.
    """
    # Each subtopic includes both concept_intent (for MiniLM) and code_intent (for CodeBERT)
    zones_data = [
        {
            "name": "Python Basics",
            "description": "Intro Gameplay Zone - Master the fundamentals of Python programming",
            "order": 1,
            "topics": [
                {
                    "name": "Introduction to Python & IDE Setup",
                    "subtopics": [
                        {
                            "name": "Installing Python (Windows, macOS, Linux)",
                            "concept_intent": "Download and install CPython 3.x, verify installation, understand multiple versions and package managers.",
                            "code_intent": "python --version; py -3 --version; brew install python; sudo apt install python3"
                        },
                        {
                            "name": "Choosing and Setting Up an IDE (VS Code, PyCharm, etc.)",
                            "concept_intent": "Select an editor, configure interpreter, enable linting/formatting and debugging.",
                            "code_intent": "VS Code: Python extension, Select Interpreter, Run/Debug; PyCharm new project with venv"
                        },
                        {
                            "name": "Writing and Running Your First Python Script",
                            "concept_intent": "Create a .py file, write a basic statement, execute via terminal.",
                            "code_intent": 'hello.py with print("Hello, world!"); python hello.py; python3 hello.py'
                        },
                        {
                            "name": "Understanding the Python Interpreter and Shell",
                            "concept_intent": "Use the interactive REPL for quick experiments and expression testing.",
                            "code_intent": "Start REPL: python; >>> 2+2; exit() or quit()"
                        },
                        {
                            "name": "File Structure, Extensions, and Comments",
                            "concept_intent": "Organize .py files and packages; use comments/docstrings; entry-point idiom.",
                            "code_intent": '# single-line comment; """docstring"""; if __name__ == "__main__": main()'
                        },
                        {
                            "name": "Managing Environment Variables and PATH",
                            "concept_intent": "Make Python and pip discoverable; understand PATH and environment settings.",
                            "code_intent": "where python / which python; setx PATH ...; export PATH=..."
                        },
                        {
                            "name": "Using the print() Function Effectively",
                            "concept_intent": "Control formatting with f-strings, separators and end characters.",
                            "code_intent": 'print(f"sum={a+b}"); print(a, b, sep=","); print("no newline", end="")'
                        },
                        {
                            "name": "Troubleshooting Common Setup Errors",
                            "concept_intent": "Diagnose missing commands, version mismatches, and import issues.",
                            "code_intent": "'pip' is not recognized; ModuleNotFoundError; python vs python3; pip install <pkg>"
                        }
                    ]
                },
                {
                    "name": "Variables & Data Types",
                    "subtopics": [
                        {
                            "name": "Declaring and Naming Variables",
                            "concept_intent": "Assign values with clear, descriptive names following conventions.",
                            "code_intent": 'x = 1; name = "Alice"; total_count = 0'
                        },
                        {
                            "name": "Integer and Floating-Point Numbers",
                            "concept_intent": "Work with ints/floats, arithmetic, and conversion between types.",
                            "code_intent": "x=3; y=2.5; z=x+y; int(2.9); float('3.14')"
                        },
                        {
                            "name": "Strings and String Formatting",
                            "concept_intent": "Build and format strings using concatenation, f-strings, and format().",
                            "code_intent": 'f"{name} has {n} apples"; "{} {}".format(a, b); "a,b".split(",")'
                        },
                        {
                            "name": "Booleans and Logical Expressions",
                            "concept_intent": "Use True/False values and combine conditions with and/or/not.",
                            "code_intent": "True/False; (a>0 and b<5) or not flag"
                        },
                        {
                            "name": "Type Conversion and Casting",
                            "concept_intent": "Convert values safely between types to avoid runtime errors.",
                            "code_intent": "int('3'); str(123); float('2.7')"
                        },
                        {
                            "name": "Type Checking with type() and isinstance()",
                            "concept_intent": "Inspect variable types and validate interfaces.",
                            "code_intent": "type(x) is int; isinstance(x, (int, float))"
                        },
                        {
                            "name": "Constants and Immutability Concepts",
                            "concept_intent": "Prefer constants and immutable types for clarity and safety.",
                            "code_intent": "PI = 3.14159; CONFIG = {...}; t = (1,2,3)  # tuple immutable"
                        }
                    ]
                },
                {
                    "name": "Basic Input and Output",
                    "subtopics": [
                        {
                            "name": "Using input() to Read User Data",
                            "concept_intent": "Prompt users and parse textual input into the right types.",
                            "code_intent": 'name = input("Name: "); age = int(input("Age: "))'
                        },
                        {
                            "name": "Basic Text Output with print()",
                            "concept_intent": "Display messages and variables for user feedback.",
                            "code_intent": 'print("Hello"); print("x=", x)'
                        },
                        {
                            "name": "String Concatenation and Formatting (f-strings, .format())",
                            "concept_intent": "Combine values and format text clearly.",
                            "code_intent": '"Hello, " + name; f"Hi {name}"; "Hi {}".format(name)'
                        },
                        {
                            "name": "Handling Input Types (Converting to int, float, etc.)",
                            "concept_intent": "Parse and cast input robustly to avoid exceptions.",
                            "code_intent": "int(input()); float(input()); bool(int_str)"
                        },
                        {
                            "name": "Printing Special Characters and Escape Sequences",
                            "concept_intent": "Represent newlines, tabs, and paths safely in strings.",
                            "code_intent": r'print("Line1\nLine2"); print(r"C:\path\to\file")'
                        },
                        {
                            "name": "Multi-line Input and Output",
                            "concept_intent": "Work with multi-line strings for messages or templates.",
                            "code_intent": 'text = """a\nb\nc""" ; print(text)'
                        },
                        {
                            "name": "Best Practices for User-Friendly I/O",
                            "concept_intent": "Design clear prompts and consistent outputs.",
                            "code_intent": 'print("Enter value: ", end=""); val = input().strip()'
                        }
                    ]
                },
                {
                    "name": "Operators",
                    "subtopics": [
                        {
                            "name": "Arithmetic Operators (+, -, *, /, %, //, **)",
                            "concept_intent": "Perform arithmetic, integer division, modulo, and powers.",
                            "code_intent": "a+b; a-b; a*b; a/b; a%2; a//2; a**3"
                        },
                        {
                            "name": "Comparison Operators (==, !=, >, <, >=, <=)",
                            "concept_intent": "Compare values for equality and ordering.",
                            "code_intent": "x==y; x!=y; x>y; x<=y"
                        },
                        {
                            "name": "Logical Operators (and, or, not)",
                            "concept_intent": "Combine boolean conditions to control flow.",
                            "code_intent": "flag and ready or not done"
                        },
                        {
                            "name": "Assignment Operators (=, +=, -=, etc. )",
                            "concept_intent": "Update variables concisely with compound operations.",
                            "code_intent": "x=1; x+=2; x*=3"
                        },
                        {
                            "name": "Operator Precedence and Associativity",
                            "concept_intent": "Understand evaluation order to avoid logic bugs.",
                            "code_intent": "a+b*c; (a+b)*c; a**b**c"
                        },
                        {
                            "name": "Membership (in, not in) and Identity Operators (is, is not)",
                            "concept_intent": "Check presence and object identity correctly.",
                            "code_intent": "'a' in s; x is None; y is not None"
                        },
                        {
                            "name": "Bitwise Operators and Binary Representation (Advanced)",
                            "concept_intent": "Manipulate integers at the bit level and view binary forms.",
                            "code_intent": "x & y; x | y; x ^ y; x << 1; x >> 1; bin(x)"
                        }
                    ]
                },
                {
                    "name": "Comments & Code Readability",
                    "subtopics": [
                        {
                            "name": "Single-line vs Multi-line Comments",
                            "concept_intent": "Document code at the right granularity using comments.",
                            "code_intent": '# single; """multi-line docstring"""'
                        },
                        {
                            "name": "Docstrings and Inline Documentation",
                            "concept_intent": "Explain purpose, parameters, and returns in docstrings.",
                            "code_intent": 'def f(): """Explain behavior."""; x = 1  # count'
                        },
                        {
                            "name": "Code Indentation and Block Structure",
                            "concept_intent": "Use consistent indentation to define blocks clearly.",
                            "code_intent": "if x:\n    do_something()"
                        },
                        {
                            "name": "Naming Conventions (PEP8 Guidelines)",
                            "concept_intent": "Apply snake_case, PascalCase, and constant naming styles.",
                            "code_intent": "snake_case, PascalCase, UPPER_SNAKE"
                        },
                        {
                            "name": "Structuring Code for Readability",
                            "concept_intent": "Break code into small, focused functions and modules.",
                            "code_intent": "extract functions; avoid deep nesting"
                        },
                        {
                            "name": "Avoiding Magic Numbers and Hardcoding",
                            "concept_intent": "Use named constants and configs for clarity and changeability.",
                            "code_intent": "MAX_RETRY = 3; if retry > MAX_RETRY: ..."
                        },
                        {
                            "name": "Writing Self-Documenting Code",
                            "concept_intent": "Prefer clear names and simple logic over comments alone.",
                            "code_intent": "clear variable names; small functions"
                        }
                    ]
                }
            ]
        },
        {
            "name": "Control Structures",
            "description": "Logic Decision Zone - Master decision-making and flow control",
            "order": 2,
            "topics": [
                {
                    "name": "Conditional Statements",
                    "subtopics": [
                        {
                            "name": "if Statement Syntax and Structure",
                            "concept_intent": "Branch code execution based on a single condition.",
                            "code_intent": "if cond:\n    ..."
                        },
                        {
                            "name": "if-else and elif Ladder",
                            "concept_intent": "Handle multiple exclusive cases clearly and safely.",
                            "code_intent": "if a:\n    ...\nelif b:\n    ...\nelse:\n    ..."
                        },
                        {
                            "name": "Nested Conditional Statements",
                            "concept_intent": "Represent hierarchical logic while keeping readability.",
                            "code_intent": "if a:\n    if b:\n        ..."
                        },
                        {
                            "name": "Boolean Logic in Conditions",
                            "concept_intent": "Combine logical operators to express complex decisions.",
                            "code_intent": "if (a and b) or not c:\n    ..."
                        },
                        {
                            "name": "Ternary Operators (One-liner conditionals)",
                            "concept_intent": "Write concise conditional assignments for simple branches.",
                            "code_intent": "x = 1 if cond else 0"
                        },
                        {
                            "name": "Using Conditions with Input",
                            "concept_intent": "Validate and branch on user input safely.",
                            "code_intent": 'age = int(input()); print("adult" if age>=18 else "minor")'
                        },
                        {
                            "name": "Common Logic Pitfalls and Debugging",
                            "concept_intent": "Avoid common mistakes like identity vs equality and truthiness traps.",
                            "code_intent": "== vs is; truthy/falsey; print() checks"
                        }
                    ]
                },
                {
                    "name": "Error Handling",
                    "subtopics": [
                        {
                            "name": "Understanding Common Runtime Errors",
                            "concept_intent": "Recognize common exceptions and their causes.",
                            "code_intent": "ZeroDivisionError; NameError; TypeError"
                        },
                        {
                            "name": "Try-Except Block Structure",
                            "concept_intent": "Catch and handle errors to keep programs robust.",
                            "code_intent": "try:\n    ...\nexcept Exception as e:\n    ..."
                        },
                        {
                            "name": "Catching Multiple Exceptions",
                            "concept_intent": "Handle specific errors differently for better recovery.",
                            "code_intent": "except (ValueError, TypeError) as e:"
                        },
                        {
                            "name": "else and finally Clauses in Error Handling",
                            "concept_intent": "Execute success/finalization code reliably around errors.",
                            "code_intent": "try: ...\nexcept: ...\nelse: ...\nfinally: ..."
                        },
                        {
                            "name": "Raising Custom Exceptions",
                            "concept_intent": "Signal invalid states with explicit, meaningful exceptions.",
                            "code_intent": "raise ValueError('bad input')"
                        },
                        {
                            "name": "Using assert Statements",
                            "concept_intent": "Enforce invariants during development and testing.",
                            "code_intent": "assert x>=0, 'x must be non-negative'"
                        },
                        {
                            "name": "Error Messages and Debugging Tools",
                            "concept_intent": "Inspect stack traces and step through code to locate issues.",
                            "code_intent": "print(e); traceback; pdb.set_trace()"
                        }
                    ]
                }
            ]
        },
        {
            "name": "Loops & Iteration",
            "description": "Cognitive Repetition Zone - Master repetitive tasks and iteration",
            "order": 3,
            "topics": [
                {
                    "name": "Loops",
                    "subtopics": [
                        {
                            "name": "for Loop with range()",
                            "concept_intent": "Iterate a fixed number of times using a counter sequence.",
                            "code_intent": "for i in range(5): print(i)"
                        },
                        {
                            "name": "Iterating Over Lists, Tuples, and Strings",
                            "concept_intent": "Traverse sequences element-by-element for processing.",
                            "code_intent": "for x in items: ... ; for ch in s: ..."
                        },
                        {
                            "name": "while Loop and Loop Conditions",
                            "concept_intent": "Repeat until a condition becomes false; ensure progress.",
                            "code_intent": "while n>0:\n    n-=1"
                        },
                        {
                            "name": "break, continue, and pass Statements",
                            "concept_intent": "Control loop flow with early exit, skipping, or placeholders.",
                            "code_intent": "for x in xs:\n    if bad: break\n    if skip: continue\n    pass"
                        },
                        {
                            "name": "Looping with enumerate() and zip()",
                            "concept_intent": "Access indices and synchronize multiple iterables cleanly.",
                            "code_intent": "for i, x in enumerate(xs): ...; for a,b in zip(xs, ys): ..."
                        },
                        {
                            "name": "Infinite Loops and Loop Safety",
                            "concept_intent": "Detect and prevent infinite loops with explicit breaks.",
                            "code_intent": "while True:\n    if should_stop: break"
                        },
                        {
                            "name": "Comparing for and while Loops",
                            "concept_intent": "Choose the loop type that best expresses the iteration intent.",
                            "code_intent": "for i in range(n): ...  vs  while i<n: ...; i+=1"
                        }
                    ]
                },
                {
                    "name": "Nested Loops",
                    "subtopics": [
                        {
                            "name": "Syntax of Nested for Loops",
                            "concept_intent": "Combine loops to process multi-dimensional data.",
                            "code_intent": "for i in range(n):\n    for j in range(m): ..."
                        },
                        {
                            "name": "Nested while and Mixed Loops",
                            "concept_intent": "Mix loop types for complex iteration patterns.",
                            "code_intent": "while i<n:\n    for j in range(m): ..."
                        },
                        {
                            "name": "Printing Patterns (e.g., triangle, pyramid)",
                            "concept_intent": "Use indices to generate structured text patterns.",
                            "code_intent": "for i in range(1,6): print('*'*i)"
                        },
                        {
                            "name": "Matrix Traversal and Processing",
                            "concept_intent": "Access rows/columns systematically in 2D data.",
                            "code_intent": "for i in range(rows):\n    for j in range(cols): ..."
                        },
                        {
                            "name": "Loop Depth and Performance Considerations",
                            "concept_intent": "Avoid excessive nested loops and prefer early exits.",
                            "code_intent": "avoid O(n^3); break early"
                        },
                        {
                            "name": "Managing Inner vs Outer Loop Variables",
                            "concept_intent": "Keep variable scopes clear and counters independent.",
                            "code_intent": "use distinct names; reset counters properly"
                        },
                        {
                            "name": "Avoiding Logical Errors in Nested Structures",
                            "concept_intent": "Validate indices and boundaries to prevent mistakes.",
                            "code_intent": "watch indices; test small cases"
                        }
                    ]
                },
                {
                    "name": "Strings & String Methods",
                    "subtopics": [
                        {
                            "name": "String Indexing and Slicing",
                            "concept_intent": "Extract substrings and characters by position and ranges.",
                            "code_intent": "s[0]; s[-1]; s[2:5]; s[:3]; s[::2]"
                        },
                        {
                            "name": "String Immutability",
                            "concept_intent": "Understand strings cannot be changed in place; create new ones.",
                            "code_intent": 's = "hi"; s = s + "!"'
                        },
                        {
                            "name": "Case Conversion Methods (lower(), upper(), etc.)",
                            "concept_intent": "Normalize text for comparisons and display.",
                            "code_intent": "s.lower(); s.upper(); s.title(); s.capitalize()"
                        },
                        {
                            "name": "Searching and Replacing Text",
                            "concept_intent": "Find substrings and replace them safely.",
                            "code_intent": "s.find('a'); s.replace('a','b'); 'a' in s"
                        },
                        {
                            "name": "String Splitting and Joining",
                            "concept_intent": "Tokenize text and reassemble with custom separators.",
                            "code_intent": '"a,b,c".split(\",\"); \",\".join(items)'
                        },
                        {
                            "name": "Validating and Cleaning Input Strings",
                            "concept_intent": "Strip whitespace and check simple patterns.",
                            "code_intent": "s.strip(); s.isdigit(); s.isalpha(); s.isalnum()"
                        },
                        {
                            "name": "Escape Sequences and Raw Strings",
                            "concept_intent": "Represent special characters and windows paths correctly.",
                            "code_intent": r'print("A\tB\nC"); r"C:\path\file.txt"'
                        }
                    ]
                }
            ]
        },
        {
            "name": "Data Structures & Modularity",
            "description": "System Design Zone - Master data organization and code modularity",
            "order": 4,
            "topics": [
                {
                    "name": "Lists & Tuples",
                    "subtopics": [
                        {
                            "name": "Creating and Modifying Lists",
                            "concept_intent": "Build dynamic sequences and update contents in place.",
                            "code_intent": "xs=[1,2]; xs.append(3); xs[0]=9"
                        },
                        {
                            "name": "List Methods (append(), remove(), sort(), etc.)",
                            "concept_intent": "Use built-ins to manage order, membership, and size.",
                            "code_intent": "xs.append(x); xs.remove(x); xs.sort(); xs.reverse()"
                        },
                        {
                            "name": "List Indexing, Slicing, and Comprehension",
                            "concept_intent": "Access by position and build lists from expressions.",
                            "code_intent": "xs[1:4]; [x*x for x in xs if x%2==0]"
                        },
                        {
                            "name": "Tuples and Their Immutability",
                            "concept_intent": "Use fixed-size ordered collections for safety and hashing.",
                            "code_intent": "t=(1,2,3); hash(t)"
                        },
                        {
                            "name": "Tuple Unpacking and Multiple Assignment",
                            "concept_intent": "Bind multiple values cleanly to variables.",
                            "code_intent": "a,b = (1,2); a,b = b,a"
                        },
                        {
                            "name": "Iterating Through Lists and Tuples",
                            "concept_intent": "Traverse elements for processing and aggregation.",
                            "code_intent": "for x in xs: ... ; for a,b in pairs: ..."
                        },
                        {
                            "name": "When to Use Lists vs Tuples",
                            "concept_intent": "Pick mutable vs immutable based on use and semantics.",
                            "code_intent": "list for dynamic; tuple for fixed keys"
                        }
                    ]
                },
                {
                    "name": "Sets",
                    "subtopics": [
                        {
                            "name": "Creating and Using Sets",
                            "concept_intent": "Represent unique, unordered collections efficiently.",
                            "code_intent": "s=set([1,2,2]); s.add(3)"
                        },
                        {
                            "name": "Set Operations (union, intersection, difference, etc.)",
                            "concept_intent": "Combine and compare sets for relationships.",
                            "code_intent": "a|b; a&b; a-b; a^b"
                        },
                        {
                            "name": "Set Methods (add(), remove(), etc.)",
                            "concept_intent": "Modify membership safely and check existence.",
                            "code_intent": "s.add(x); s.remove(x); x in s"
                        },
                        {
                            "name": "Working with Duplicates and Membership",
                            "concept_intent": "Eliminate duplicates and query presence fast.",
                            "code_intent": "unique = set(xs); if key in seen: ..."
                        },
                        {
                            "name": "Frozen Sets and Hashing",
                            "concept_intent": "Use immutable sets as dict keys or set members.",
                            "code_intent": "fs = frozenset([1,2]); d[fs]=True"
                        },
                        {
                            "name": "Performance Benefits of Sets",
                            "concept_intent": "Use O(1) average-time membership checks.",
                            "code_intent": "x in s  # fast membership"
                        },
                        {
                            "name": "Converting Between Sets and Other Types",
                            "concept_intent": "Switch representations for operations then convert back.",
                            "code_intent": "list(set(xs)); set('aab')"
                        }
                    ]
                },
                {
                    "name": "Functions",
                    "subtopics": [
                        {
                            "name": "Defining Functions with def",
                            "concept_intent": "Package reusable logic with clear inputs/outputs.",
                            "code_intent": "def add(a,b): return a+b"
                        },
                        {
                            "name": "Parameters, Arguments, and Return Values",
                            "concept_intent": "Pass values and receive results explicitly.",
                            "code_intent": "def f(x,y=0,*args,**kw): return x+y"
                        },
                        {
                            "name": "Variable Scope and global/nonlocal",
                            "concept_intent": "Understand name resolution and side-effects scope.",
                            "code_intent": "x=0; def f():\n    global x; x+=1"
                        },
                        {
                            "name": "Default and Keyword Arguments",
                            "concept_intent": "Make APIs flexible and self-documenting.",
                            "code_intent": "def connect(host='localhost', port=5432): ..."
                        },
                        {
                            "name": "Docstrings and Function Annotations",
                            "concept_intent": "Describe behavior and types for tools and readers.",
                            "code_intent": "def f(a: int) -> int:\n    \"\"\"Squares a number\"\"\"\n    return a*a"
                        },
                        {
                            "name": "Lambda Functions and Anonymous Functions",
                            "concept_intent": "Define small inline functions for brief use.",
                            "code_intent": "sorted(xs, key=lambda x: x[1])"
                        },
                        {
                            "name": "Higher-Order Functions and Functional Programming Basics",
                            "concept_intent": "Use map/filter/reduce and pass functions as values.",
                            "code_intent": "list(map(str, xs)); list(filter(pred, xs))"
                        }
                    ]
                },
                {
                    "name": "Dictionaries",
                    "subtopics": [
                        {
                            "name": "Creating and Accessing Dictionary Items",
                            "concept_intent": "Map keys to values and retrieve them efficiently.",
                            "code_intent": "d={'a':1}; d['a']; d.get('b',0)"
                        },
                        {
                            "name": "Adding, Updating, and Deleting Keys",
                            "concept_intent": "Maintain and mutate mappings safely.",
                            "code_intent": "d['x']=1; d.update(y=2); del d['x']"
                        },
                        {
                            "name": "Looping Through Keys, Values, and Items",
                            "concept_intent": "Traverse mappings by keys, values, or pairs.",
                            "code_intent": "for k,v in d.items(): ..."
                        },
                        {
                            "name": "Dictionary Methods (get(), pop(), update(), etc.)",
                            "concept_intent": "Use helpers for defaults, removal, and merges.",
                            "code_intent": "d.get('k',0); d.pop('k',None); d.update(other)"
                        },
                        {
                            "name": "Nesting Dictionaries",
                            "concept_intent": "Represent structured data with nested mappings.",
                            "code_intent": "user={'name':{'first':'A','last':'B'}}"
                        },
                        {
                            "name": "Using Dictionaries for Counting (e.g., frequency maps)",
                            "concept_intent": "Aggregate occurrences efficiently by key.",
                            "code_intent": "from collections import Counter; Counter(xs)"
                        },
                        {
                            "name": "Dictionary Comprehensions",
                            "concept_intent": "Build mappings from sequences in one expression.",
                            "code_intent": "{x: x*x for x in range(5)}"
                        }
                    ]
                }
            ]
        }
    ]

    print("🚀 Starting PyGrounds zone population...")
    print("=" * 60)

    # Clean up existing data with detailed feedback
    print("🧹 Cleaning existing data...")

    existing_subtopics = Subtopic.objects.count()
    existing_topics = Topic.objects.count()
    existing_zones = GameZone.objects.count()

    if existing_subtopics > 0 or existing_topics > 0 or existing_zones > 0:
        print(f"  📊 Found existing data:")
        print(f"    • {existing_zones} zones")
        print(f"    • {existing_topics} topics")
        print(f"    • {existing_subtopics} subtopics")
        print("  🗑️  Deleting all existing data...")

        # Delete in proper order (child to parent) to avoid foreign key issues
        Subtopic.objects.all().delete()
        print("    ✅ Subtopics deleted")

        Topic.objects.all().delete()
        print("    ✅ Topics deleted")

        GameZone.objects.all().delete()
        print("    ✅ Zones deleted")

        # Also clean up any orphaned embeddings
        try:
            from content_ingestion.models import Embedding
            orphaned_embeddings = Embedding.objects.filter(subtopic__isnull=True, document_chunk__isnull=True)
            if orphaned_embeddings.exists():
                count = orphaned_embeddings.count()
                orphaned_embeddings.delete()
                print(f"    ✅ {count} orphaned embeddings deleted")
        except Exception as e:
            print(f"    ⚠️  Could not clean orphaned embeddings: {e}")

        print("  🎯 Database cleaned successfully!")
    else:
        print("  ✨ Database is already clean - no existing data found")

    print()

    total_zones = len(zones_data)
    total_topics = sum(len(zone["topics"]) for zone in zones_data)
    total_subtopics = sum(len(topic["subtopics"]) for zone in zones_data for topic in zone["topics"])

    print(f"📊 Will create: {total_zones} zones, {total_topics} topics, {total_subtopics} subtopics\n")

    # Create zones, topics, and subtopics
    code_intents_map = {}
    concept_intents_map = {}

    for zone_idx, zone_data in enumerate(zones_data, 1):
        zone = GameZone.objects.create(
            name=zone_data["name"],
            description=zone_data.get("description", ""),
            order=zone_data.get("order", zone_idx),
            is_unlocked=zone_data.get("is_unlocked", False),
        )
        print(f"✅ Zone {zone.order}: {zone.name}")
        for topic_idx, topic_data in enumerate(zone_data["topics"], 1):
            topic = Topic.objects.create(
                zone=zone,
                name=topic_data["name"],
                description=topic_data.get("description", topic_data["name"]),
            )
            print(f"  📚 Topic: {topic.name}")
            for sub_idx, sub in enumerate(topic_data["subtopics"], 1):
                # sub may be a dict with name/intent fields
                if isinstance(sub, dict):
                    sub_name = sub["name"]
                    concept_intent = sub.get("concept_intent", "")
                    code_intent = sub.get("code_intent", "")
                else:
                    sub_name = str(sub)
                    concept_intent = ""
                    code_intent = ""

                subtopic = Subtopic.objects.create(
                    topic=topic,
                    name=sub_name,
                    concept_intent=concept_intent,
                    code_intent=code_intent
                )
                print(f"    📝 Subtopic: {subtopic.name}")
                if concept_intent:
                    print(f"        💡 Concept: {concept_intent[:60]}...")
                if code_intent:
                    print(f"        💻 Code: {code_intent[:60]}...")

                # Save mapping for embedding generation
                if concept_intent:
                    concept_intents_map[subtopic.id] = concept_intent
                if code_intent:
                    code_intents_map[subtopic.id] = code_intent
        print()

    print("=" * 60)
    print("🎉 PyGrounds zone population complete!\n")

    # Verify the data was created correctly
    final_zones = GameZone.objects.count()
    final_topics = Topic.objects.count()
    final_subtopics = Subtopic.objects.count()

    print("📈 Final Summary:")
    print(f"  • Created {final_zones} zones (expected: {total_zones})")
    print(f"  • Created {final_topics} topics (expected: {total_topics})")
    print(f"  • Created {final_subtopics} subtopics (expected: {total_subtopics})")

    if final_zones == total_zones and final_topics == total_topics and final_subtopics == total_subtopics:
        print("  ✅ All data created successfully!")
    else:
        print("  ⚠️  Warning: Some data may not have been created correctly")
        print("     Please check the logs above for any errors")

    # Generate embeddings with both intent maps
    generate_subtopic_embeddings(concept_intents_map=concept_intents_map, code_intents_map=code_intents_map)

    print("\n🎮 Your PyGrounds learning structure is ready!")


if __name__ == "__main__":
    try:
        populate_zones()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error during population: {e}")
        print("   Please check your database connection and model definitions")
        sys.exit(1)
