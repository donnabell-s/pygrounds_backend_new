#!/usr/bin/env python
"""
Create comprehensive PyGrounds game structure
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
django.setup()

from content_ingestion.models import GameZone, Topic, Subtopic

def create_pygrounds_structure():
    """Create the complete PyGrounds game structure"""
    
    print("Creating PyGrounds Game Structure...")
    
    # Zone 1: Python Basics (Intro Gameplay Zone)
    try:
        zone1 = GameZone.objects.get(order=1)
        # Update existing zone with new name if different
        if zone1.name != "Python Basics":
            zone1.name = "Python Basics"
            zone1.description = "Intro Gameplay Zone - Learn Python fundamentals and setup"
            zone1.save()
            print(f"✓ Zone 1: Updated existing zone to '{zone1.name}'")
        else:
            print(f"✓ Zone 1: {zone1.name} (already exists)")
        created = False
    except GameZone.DoesNotExist:
        zone1 = GameZone.objects.create(
            name="Python Basics",
            description="Intro Gameplay Zone - Learn Python fundamentals and setup",
            order=1,
            required_exp=0,
            max_exp=1000,
            is_unlocked=True,
            is_active=True
        )
        print(f"✓ Zone 1: {zone1.name} (created)")
        created = True
    
    # Zone 1 Topics and Subtopics
    zone1_structure = [
        {
            'name': 'Introduction to Python & IDE Setup',
            'description': 'Setting up your Python development environment',
            'subtopics': [
                'Installing Python (Windows, macOS, Linux)',
                'Choosing and Setting Up an IDE (VS Code, PyCharm, etc.)',
                'Writing and Running Your First Python Script',
                'Understanding the Python Interpreter and Shell',
                'File Structure, Extensions, and Comments',
                'Managing Environment Variables and PATH',
                'Using the print() Function Effectively',
                'Troubleshooting Common Setup Errors'
            ]
        },
        {
            'name': 'Variables & Data Types',
            'description': 'Understanding Python variables and basic data types',
            'subtopics': [
                'Declaring and Naming Variables',
                'Integer and Floating-Point Numbers',
                'Strings and String Formatting',
                'Booleans and Logical Expressions',
                'Type Conversion and Casting',
                'Type Checking with type() and isinstance()',
                'Constants and Immutability Concepts'
            ]
        },
        {
            'name': 'Basic Input and Output',
            'description': 'Handling user input and program output',
            'subtopics': [
                'Using input() to Read User Data',
                'Basic Text Output with print()',
                'String Concatenation and Formatting (f-strings, .format())',
                'Handling Input Types (Converting to int, float, etc.)',
                'Printing Special Characters and Escape Sequences',
                'Multi-line Input and Output',
                'Best Practices for User-Friendly I/O'
            ]
        },
        {
            'name': 'Operators',
            'description': 'Mathematical, logical, and comparison operations',
            'subtopics': [
                'Arithmetic Operators (+, -, *, /, %, //, **)',
                'Comparison Operators (==, !=, >, <, >=, <=)',
                'Logical Operators (and, or, not)',
                'Assignment Operators (=, +=, -=, etc.)',
                'Operator Precedence and Associativity',
                'Membership (in, not in) and Identity Operators (is, is not)',
                'Bitwise Operators and Binary Representation (Advanced)'
            ]
        },
        {
            'name': 'Comments & Code Readability',
            'description': 'Writing clean, readable, and well-documented code',
            'subtopics': [
                'Single-line vs Multi-line Comments',
                'Docstrings and Inline Documentation',
                'Code Indentation and Block Structure',
                'Naming Conventions (PEP8 Guidelines)',
                'Structuring Code for Readability',
                'Avoiding Magic Numbers and Hardcoding',
                'Writing Self-Documenting Code'
            ]
        }
    ]
    
    create_topics_and_subtopics(zone1, zone1_structure)
    
    # Zone 2: Control Structures (Logic Decision Zone)
    try:
        zone2 = GameZone.objects.get(order=2)
        if zone2.name != "Control Structures":
            zone2.name = "Control Structures"
            zone2.description = "Logic Decision Zone - Master conditional logic and error handling"
            zone2.save()
            print(f"✓ Zone 2: Updated existing zone to '{zone2.name}'")
        else:
            print(f"✓ Zone 2: {zone2.name} (already exists)")
        created = False
    except GameZone.DoesNotExist:
        zone2 = GameZone.objects.create(
            name="Control Structures",
            description="Logic Decision Zone - Master conditional logic and error handling",
            order=2,
            required_exp=1000,
            max_exp=2000,
            is_unlocked=False,
            is_active=True
        )
        print(f"✓ Zone 2: {zone2.name} (created)")
        created = True
    
    zone2_structure = [
        {
            'name': 'Conditional Statements',
            'description': 'Making decisions in your code with if statements',
            'subtopics': [
                'if Statement Syntax and Structure',
                'if-else and elif Ladder',
                'Nested Conditional Statements',
                'Boolean Logic in Conditions',
                'Ternary Operators (One-liner conditionals)',
                'Using Conditions with Input',
                'Common Logic Pitfalls and Debugging'
            ]
        },
        {
            'name': 'Error Handling',
            'description': 'Managing and responding to runtime errors',
            'subtopics': [
                'Understanding Common Runtime Errors',
                'Try-Except Block Structure',
                'Catching Multiple Exceptions',
                'else and finally Clauses in Error Handling',
                'Raising Custom Exceptions',
                'Using assert Statements',
                'Error Messages and Debugging Tools'
            ]
        }
    ]
    
    create_topics_and_subtopics(zone2, zone2_structure)
    
    # Zone 3: Loops & Iteration (Cognitive Repetition Zone)
    try:
        zone3 = GameZone.objects.get(order=3)
        if zone3.name != "Loops & Iteration":
            zone3.name = "Loops & Iteration"
            zone3.description = "Cognitive Repetition Zone - Master loops and string processing"
            zone3.save()
            print(f"✓ Zone 3: Updated existing zone to '{zone3.name}'")
        else:
            print(f"✓ Zone 3: {zone3.name} (already exists)")
        created = False
    except GameZone.DoesNotExist:
        zone3 = GameZone.objects.create(
            name="Loops & Iteration",
            description="Cognitive Repetition Zone - Master loops and string processing",
            order=3,
            required_exp=2000,
            max_exp=3500,
            is_unlocked=False,
            is_active=True
        )
        print(f"✓ Zone 3: {zone3.name} (created)")
        created = True
    
    zone3_structure = [
        {
            'name': 'Loops',
            'description': 'Repeating code execution with for and while loops',
            'subtopics': [
                'for Loop with range()',
                'Iterating Over Lists, Tuples, and Strings',
                'while Loop and Loop Conditions',
                'break, continue, and pass Statements',
                'Looping with enumerate() and zip()',
                'Infinite Loops and Loop Safety',
                'Comparing for and while Loops'
            ]
        },
        {
            'name': 'Nested Loops',
            'description': 'Working with loops inside loops for complex patterns',
            'subtopics': [
                'Syntax of Nested for Loops',
                'Nested while and Mixed Loops',
                'Printing Patterns (e.g., triangle, pyramid)',
                'Matrix Traversal and Processing',
                'Loop Depth and Performance Considerations',
                'Managing Inner vs Outer Loop Variables',
                'Avoiding Logical Errors in Nested Structures'
            ]
        },
        {
            'name': 'Strings & String Methods',
            'description': 'Advanced string manipulation and processing',
            'subtopics': [
                'String Indexing and Slicing',
                'String Immutability',
                'Case Conversion Methods (lower(), upper(), etc.)',
                'Searching and Replacing Text',
                'String Splitting and Joining',
                'Validating and Cleaning Input Strings',
                'Escape Sequences and Raw Strings'
            ]
        }
    ]
    
    create_topics_and_subtopics(zone3, zone3_structure)
    
    # Zone 4: Data Structures & Modularity (System Design Zone)
    try:
        zone4 = GameZone.objects.get(order=4)
        if zone4.name != "Data Structures & Modularity":
            zone4.name = "Data Structures & Modularity"
            zone4.description = "System Design Zone - Advanced data structures and functions"
            zone4.save()
            print(f"✓ Zone 4: Updated existing zone to '{zone4.name}'")
        else:
            print(f"✓ Zone 4: {zone4.name} (already exists)")
        created = False
    except GameZone.DoesNotExist:
        zone4 = GameZone.objects.create(
            name="Data Structures & Modularity",
            description="System Design Zone - Advanced data structures and functions",
            order=4,
            required_exp=3500,
            max_exp=5000,
            is_unlocked=False,
            is_active=True
        )
        print(f"✓ Zone 4: {zone4.name} (created)")
        created = True
    
    zone4_structure = [
        {
            'name': 'Lists & Tuples',
            'description': 'Working with ordered collections of data',
            'subtopics': [
                'Creating and Modifying Lists',
                'List Methods (append(), remove(), sort(), etc.)',
                'List Indexing, Slicing, and Comprehension',
                'Tuples and Their Immutability',
                'Tuple Unpacking and Multiple Assignment',
                'Iterating Through Lists and Tuples',
                'When to Use Lists vs Tuples'
            ]
        },
        {
            'name': 'Sets',
            'description': 'Unique collections and set operations',
            'subtopics': [
                'Creating and Using Sets',
                'Set Operations (union, intersection, difference, etc.)',
                'Set Methods (add(), remove(), etc.)',
                'Working with Duplicates and Membership',
                'Frozen Sets and Hashing',
                'Performance Benefits of Sets',
                'Converting Between Sets and Other Types'
            ]
        },
        {
            'name': 'Functions',
            'description': 'Creating reusable code with functions',
            'subtopics': [
                'Defining Functions with def',
                'Parameters, Arguments, and Return Values',
                'Variable Scope and global/nonlocal',
                'Default and Keyword Arguments',
                'Docstrings and Function Annotations',
                'Lambda Functions and Anonymous Functions',
                'Higher-Order Functions and Functional Programming Basics'
            ]
        },
        {
            'name': 'Dictionaries',
            'description': 'Key-value data structures and mapping',
            'subtopics': [
                'Creating and Accessing Dictionary Items',
                'Adding, Updating, and Deleting Keys',
                'Looping Through Keys, Values, and Items',
                'Dictionary Methods (get(), pop(), update(), etc.)',
                'Nesting Dictionaries',
                'Using Dictionaries for Counting (e.g., frequency maps)',
                'Dictionary Comprehensions'
            ]
        }
    ]
    
    create_topics_and_subtopics(zone4, zone4_structure)
    
    print("\n=== PyGrounds Structure Created Successfully! ===")
    print(f"Total Zones: {GameZone.objects.count()}")
    print(f"Total Topics: {Topic.objects.count()}")
    print(f"Total Subtopics: {Subtopic.objects.count()}")
    
    # Find the input() subtopic
    input_subtopic = Subtopic.objects.filter(name__icontains='input()').first()
    if input_subtopic:
        print(f"\n✅ Found input() subtopic: ID {input_subtopic.id} - '{input_subtopic.name}'")
        print(f"   Full path: {input_subtopic.topic.zone.name} > {input_subtopic.topic.name} > {input_subtopic.name}")
        return input_subtopic
    else:
        print("\n⚠️ No input() subtopic found")
        return None

def create_topics_and_subtopics(zone, topics_structure):
    """Helper to create topics and subtopics for a zone"""
    for topic_order, topic_data in enumerate(topics_structure, 1):
        topic, created = Topic.objects.get_or_create(
            zone=zone,
            name=topic_data['name'],
            defaults={
                'description': topic_data['description'],
                'order': topic_order,
                'min_zone_exp': 0,
                'is_unlocked': topic_order == 1  # Only first topic unlocked
            }
        )
        
        if created:
            print(f"  ✓ Topic: {topic.name}")
        
        # Create subtopics
        for subtopic_order, subtopic_name in enumerate(topic_data['subtopics'], 1):
            # Generate learning objectives based on subtopic name
            learning_objectives = generate_learning_objectives(subtopic_name)
            
            subtopic, created = Subtopic.objects.get_or_create(
                topic=topic,
                name=subtopic_name,
                defaults={
                    'description': f'Master {subtopic_name.lower()} concepts and practical applications',
                    'order': subtopic_order,
                    'learning_objectives': learning_objectives,
                    'difficulty_levels': 5,
                    'min_zone_exp': 0,
                    'is_unlocked': subtopic_order == 1  # Only first subtopic unlocked
                }
            )
            
            if created:
                print(f"    • Subtopic: {subtopic.name}")

def generate_learning_objectives(subtopic_name):
    """Generate appropriate learning objectives for each subtopic"""
    objectives_map = {
        'Using input() to Read User Data': [
            'Understand the input() function syntax and return type',
            'Capture user input and store it in variables',
            'Handle different types of user input data',
            'Implement basic input validation techniques',
            'Create interactive programs that respond to user input'
        ],
        'Basic Text Output with print()': [
            'Use print() function for displaying text output',
            'Format output with multiple arguments and separators',
            'Control print() behavior with end and sep parameters',
            'Display variables and expressions in output',
            'Create well-formatted program output'
        ]
    }
    
    # Return specific objectives if available, otherwise generate generic ones
    if subtopic_name in objectives_map:
        return objectives_map[subtopic_name]
    else:
        # Generate generic objectives
        return [
            f'Understand the fundamentals of {subtopic_name.lower()}',
            f'Apply {subtopic_name.lower()} in practical coding scenarios',
            f'Recognize common patterns and best practices for {subtopic_name.lower()}',
            f'Debug and troubleshoot issues related to {subtopic_name.lower()}',
            f'Combine {subtopic_name.lower()} with other Python concepts'
        ]

if __name__ == "__main__":
    input_subtopic = create_pygrounds_structure()
    if input_subtopic:
        print(f"\n🎯 Ready to test question generation with subtopic ID: {input_subtopic.id}")
        print(f"   Test endpoint: /api/question_generation/compare/subtopic/{input_subtopic.id}/")
    else:
        print("\n🎯 Game structure created! Check for available subtopics to test.")
