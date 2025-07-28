#!/usr/bin/env python
"""
Populate PyGrounds database with predefined game zones, topics, and subtopics.
Run this script after migrating a fresh database to set up the learning structure.

Usage: python populate_zones.py
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
django.setup()

from content_ingestion.models import GameZone, Topic, Subtopic

def generate_topic_embeddings():
    """
    Generate embeddings for all topics and subtopics for better RAG semantic matching.
    """
    try:
        from content_ingestion.helpers.embedding_utils import EmbeddingGenerator
        from django.utils import timezone

        embedding_generator = EmbeddingGenerator()
        print("\n🔮 Generating embeddings for topics and subtopics...")
        print("=" * 60)

        # Topic embeddings
        topics = Topic.objects.filter(embedding__isnull=True)
        print(f"📚 Generating embeddings for {topics.count()} topics...")
        for topic in topics:
            try:
                embedding_text = f"{topic.name}: {topic.description}"
                embedding = embedding_generator.generate_embedding(embedding_text)
                topic.embedding = embedding
                topic.save()
                print(f"  ✅ {topic.name}")
            except Exception as e:
                print(f"  ❌ Failed to embed topic '{topic.name}': {e}")

        # Subtopic embeddings - create Embedding objects
        subtopics = Subtopic.objects.filter(embedding_obj__isnull=True)
        print(f"\n📝 Generating embeddings for {subtopics.count()} subtopics...")
        for subtopic in subtopics:
            try:
                from content_ingestion.models import Embedding
                embedding_text = f"{subtopic.topic.name} - {subtopic.name}"
                embedding = embedding_generator.generate_embedding(embedding_text)
                Embedding.objects.create(
                    subtopic=subtopic,
                    vector=embedding,
                    model_name="all-MiniLM-L6-v2"
                )
                print(f"  ✅ {subtopic.name}")
            except Exception as e:
                print(f"  ❌ Failed to embed subtopic '{subtopic.name}': {e}")

        print(f"\n🎉 Embedding generation complete!")
        print(f"  • Topics embedded: {Topic.objects.filter(embedding__isnull=False).count()}")
        print(f"  • Subtopics embedded: {Subtopic.objects.filter(embedding_obj__isnull=False).count()}")
    except ImportError:
        print("\n⚠️  Embedding utilities not available - skipping embedding generation")
        print("   Topics and subtopics created without embeddings")
    except Exception as e:
        print(f"\n❌ Error generating embeddings: {e}")
        print("   Topics and subtopics created without embeddings")

def populate_zones():
    """
    Populate the database with predefined zones, topics, and subtopics.
    This will completely overwrite any existing data.
    """
    zones_data = [
    {
        "name": "Python Basics",
        "description": "Intro Gameplay Zone - Master the fundamentals of Python programming",
        "order": 1,
        "required_exp": 0,
        "max_exp": 1000,
        "is_unlocked": True,
        "topics": [
            {
                "name": "Introduction to Python & IDE Setup",
                "subtopics": [
                    "Installing Python (Windows, macOS, Linux)",
                    "Choosing and Setting Up an IDE (VS Code, PyCharm, etc.)",
                    "Writing and Running Your First Python Script",
                    "Understanding the Python Interpreter and Shell",
                    "File Structure, Extensions, and Comments",
                    "Managing Environment Variables and PATH",
                    "Using the print() Function Effectively",
                    "Troubleshooting Common Setup Errors"
                ]
            },
            {
                "name": "Variables & Data Types",
                "subtopics": [
                    "Declaring and Naming Variables",
                    "Integer and Floating-Point Numbers",
                    "Strings and String Formatting",
                    "Booleans and Logical Expressions",
                    "Type Conversion and Casting",
                    "Type Checking with type() and isinstance()",
                    "Constants and Immutability Concepts"
                ]
            },
            {
                "name": "Basic Input and Output",
                "subtopics": [
                    "Using input() to Read User Data",
                    "Basic Text Output with print()",
                    "String Concatenation and Formatting (f-strings, .format())",
                    "Handling Input Types (Converting to int, float, etc.)",
                    "Printing Special Characters and Escape Sequences",
                    "Multi-line Input and Output",
                    "Best Practices for User-Friendly I/O"
                ]
            },
            {
                "name": "Operators",
                "subtopics": [
                    "Arithmetic Operators (+, -, *, /, %, //, **)",
                    "Comparison Operators (==, !=, >, <, >=, <=)",
                    "Logical Operators (and, or, not)",
                    "Assignment Operators (=, +=, -=, etc.)",
                    "Operator Precedence and Associativity",
                    "Membership (in, not in) and Identity Operators (is, is not)",
                    "Bitwise Operators and Binary Representation (Advanced)"
                ]
            },
            {
                "name": "Comments & Code Readability",
                "subtopics": [
                    "Single-line vs Multi-line Comments",
                    "Docstrings and Inline Documentation",
                    "Code Indentation and Block Structure",
                    "Naming Conventions (PEP8 Guidelines)",
                    "Structuring Code for Readability",
                    "Avoiding Magic Numbers and Hardcoding",
                    "Writing Self-Documenting Code"
                ]
            }
        ]
    },
    {
        "name": "Control Structures",
        "description": "Logic Decision Zone - Master decision-making and flow control",
        "order": 2,
        "required_exp": 1000,
        "max_exp": 2000,
        "is_unlocked": False,
        "is_active": True,
        "topics": [
            {
                "name": "Conditional Statements",
                "subtopics": [
                    "if Statement Syntax and Structure",
                    "if-else and elif Ladder",
                    "Nested Conditional Statements",
                    "Boolean Logic in Conditions",
                    "Ternary Operators (One-liner conditionals)",
                    "Using Conditions with Input",
                    "Common Logic Pitfalls and Debugging"
                ]
            },
            {
                "name": "Error Handling",
                "subtopics": [
                    "Understanding Common Runtime Errors",
                    "Try-Except Block Structure",
                    "Catching Multiple Exceptions",
                    "else and finally Clauses in Error Handling",
                    "Raising Custom Exceptions",
                    "Using assert Statements",
                    "Error Messages and Debugging Tools"
                ]
            }
        ]
    },
    {
        "name": "Loops & Iteration",
        "description": "Cognitive Repetition Zone - Master repetitive tasks and iteration",
        "order": 3,
        "required_exp": 2000,
        "max_exp": 3000,
        "is_unlocked": False,
        "is_active": True,
        "topics": [
            {
                "name": "Loops",
                "subtopics": [
                    "for Loop with range()",
                    "Iterating Over Lists, Tuples, and Strings",
                    "while Loop and Loop Conditions",
                    "break, continue, and pass Statements",
                    "Looping with enumerate() and zip()",
                    "Infinite Loops and Loop Safety",
                    "Comparing for and while Loops"
                ]
            },
            {
                "name": "Nested Loops",
                "subtopics": [
                    "Syntax of Nested for Loops",
                    "Nested while and Mixed Loops",
                    "Printing Patterns (e.g., triangle, pyramid)",
                    "Matrix Traversal and Processing",
                    "Loop Depth and Performance Considerations",
                    "Managing Inner vs Outer Loop Variables",
                    "Avoiding Logical Errors in Nested Structures"
                ]
            },
            {
                "name": "Strings & String Methods",
                "subtopics": [
                    "String Indexing and Slicing",
                    "String Immutability",
                    "Case Conversion Methods (lower(), upper(), etc.)",
                    "Searching and Replacing Text",
                    "String Splitting and Joining",
                    "Validating and Cleaning Input Strings",
                    "Escape Sequences and Raw Strings"
                ]
            }
        ]
    },
    {
        "name": "Data Structures & Modularity",
        "description": "System Design Zone - Master data organization and code modularity",
        "order": 4,
        "required_exp": 3000,
        "max_exp": 4000,
        "is_unlocked": False,
        "is_active": True,
        "topics": [
            {
                "name": "Lists & Tuples",
                "subtopics": [
                    "Creating and Modifying Lists",
                    "List Methods (append(), remove(), sort(), etc.)",
                    "List Indexing, Slicing, and Comprehension",
                    "Tuples and Their Immutability",
                    "Tuple Unpacking and Multiple Assignment",
                    "Iterating Through Lists and Tuples",
                    "When to Use Lists vs Tuples"
                ]
            },
            {
                "name": "Sets",
                "subtopics": [
                    "Creating and Using Sets",
                    "Set Operations (union, intersection, difference, etc.)",
                    "Set Methods (add(), remove(), etc.)",
                    "Working with Duplicates and Membership",
                    "Frozen Sets and Hashing",
                    "Performance Benefits of Sets",
                    "Converting Between Sets and Other Types"
                ]
            },
            {
                "name": "Functions",
                "subtopics": [
                    "Defining Functions with def",
                    "Parameters, Arguments, and Return Values",
                    "Variable Scope and global/nonlocal",
                    "Default and Keyword Arguments",
                    "Docstrings and Function Annotations",
                    "Lambda Functions and Anonymous Functions",
                    "Higher-Order Functions and Functional Programming Basics"
                ]
            },
            {
                "name": "Dictionaries",
                "subtopics": [
                    "Creating and Accessing Dictionary Items",
                    "Adding, Updating, and Deleting Keys",
                    "Looping Through Keys, Values, and Items",
                    "Dictionary Methods (get(), pop(), update(), etc.)",
                    "Nesting Dictionaries",
                    "Using Dictionaries for Counting (e.g., frequency maps)",
                    "Dictionary Comprehensions"
                ]
            }
        ]
    }
]


    print("🚀 Starting PyGrounds zone population...")
    print("=" * 60)
    
    # Clean up existing data with detailed feedback
    print("🧹 Cleaning existing data...")
    
    # Get counts before deletion for feedback
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
                order=topic_idx,
            )
            print(f"  📚 Topic {topic.order}: {topic.name}")
            for sub_idx, subtopic_name in enumerate(topic_data["subtopics"], 1):
                subtopic = Subtopic.objects.create(
                    topic=topic,
                    name=subtopic_name,
                    order=sub_idx,
                )
                print(f"    📝 Subtopic {subtopic.order}: {subtopic.name}")
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
    
    # Verify counts match expectations
    if final_zones == total_zones and final_topics == total_topics and final_subtopics == total_subtopics:
        print("  ✅ All data created successfully!")
    else:
        print("  ⚠️  Warning: Some data may not have been created correctly")
        print("     Please check the logs above for any errors")

    generate_topic_embeddings()

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