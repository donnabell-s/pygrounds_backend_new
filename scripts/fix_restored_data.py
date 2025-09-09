#!/usr/bin/env python
"""
Fix restored data that's missing new required fields.
This script adds missing slugs, order_in_topic, and other new fields with sensible defaults.

Usage: python scripts/fix_restored_data.py
"""

import os
import sys
import django
from django.utils.text import slugify

# Add the parent directory to the Python path so we can import pygrounds_backend_new
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
django.setup()

from content_ingestion.models import GameZone, Topic, Subtopic


def fix_missing_slugs():
    """Add missing slug fields to Topics and Subtopics"""
    print("🔧 Fixing missing slug fields...")
    
    # Fix Topics
    topics_fixed = 0
    for topic in Topic.objects.filter(slug__isnull=True):
        topic.slug = slugify(topic.name)
        topic.save()
        print(f"  ✅ Topic: '{topic.name}' -> slug: '{topic.slug}'")
        topics_fixed += 1
    
    # Fix Subtopics  
    subtopics_fixed = 0
    for subtopic in Subtopic.objects.filter(slug__isnull=True):
        subtopic.slug = slugify(subtopic.name)
        subtopic.save()
        print(f"  ✅ Subtopic: '{subtopic.name}' -> slug: '{subtopic.slug}'")
        subtopics_fixed += 1
    
    print(f"  📊 Fixed {topics_fixed} topics and {subtopics_fixed} subtopics")


def fix_missing_order_fields():
    """Add missing order_in_topic fields"""
    print("\n🔢 Fixing missing order_in_topic fields...")
    
    subtopics_fixed = 0
    
    # Group subtopics by topic and assign sequential order
    for topic in Topic.objects.all():
        subtopics = Subtopic.objects.filter(topic=topic, order_in_topic__isnull=True).order_by('id')
        
        if subtopics.exists():
            # Get the highest existing order for this topic
            max_order = Subtopic.objects.filter(
                topic=topic, 
                order_in_topic__isnull=False
            ).aggregate(max_order=models.Max('order_in_topic'))['max_order'] or 0
            
            for i, subtopic in enumerate(subtopics, start=1):
                subtopic.order_in_topic = max_order + i
                subtopic.save()
                print(f"  ✅ '{subtopic.name}' -> order: {subtopic.order_in_topic}")
                subtopics_fixed += 1
    
    print(f"  📊 Fixed {subtopics_fixed} subtopic orders")


def fix_missing_intent_fields():
    """Add placeholder content for missing intent fields"""
    print("\n💡 Adding placeholder intent content...")
    
    concept_fixed = 0
    code_fixed = 0
    
    for subtopic in Subtopic.objects.all():
        updated = False
        
        if not subtopic.concept_intent:
            subtopic.concept_intent = f"Learn about {subtopic.name.lower()} concepts and fundamentals."
            concept_fixed += 1
            updated = True
            
        if not subtopic.code_intent:
            subtopic.code_intent = f"Practice {subtopic.name.lower()} with hands-on coding examples."
            code_fixed += 1
            updated = True
            
        if updated:
            subtopic.save()
            print(f"  ✅ Added intents for: '{subtopic.name}'")
    
    print(f"  📊 Added {concept_fixed} concept intents and {code_fixed} code intents")


def fix_missing_descriptions():
    """Add descriptions where missing"""
    print("\n📝 Adding missing descriptions...")
    
    topics_fixed = 0
    
    for topic in Topic.objects.filter(description__isnull=True):
        topic.description = f"Learn {topic.name.lower()} fundamentals and best practices."
        topic.save()
        print(f"  ✅ Topic: '{topic.name}' -> description added")
        topics_fixed += 1
    
    # Also fix empty descriptions (not just null)
    for topic in Topic.objects.filter(description=""):
        topic.description = f"Learn {topic.name.lower()} fundamentals and best practices."
        topic.save()
        print(f"  ✅ Topic: '{topic.name}' -> empty description fixed")
        topics_fixed += 1
    
    print(f"  📊 Fixed {topics_fixed} topic descriptions")


def display_summary():
    """Show final data summary"""
    print("\n📊 Current Database Summary:")
    print("=" * 50)
    
    zones = GameZone.objects.count()
    topics = Topic.objects.count()
    subtopics = Subtopic.objects.count()
    
    print(f"  🎮 Game Zones: {zones}")
    print(f"  📚 Topics: {topics}")
    print(f"  📝 Subtopics: {subtopics}")
    
    # Check for any remaining issues
    topics_no_slug = Topic.objects.filter(slug__isnull=True).count()
    subtopics_no_slug = Subtopic.objects.filter(slug__isnull=True).count()
    subtopics_no_order = Subtopic.objects.filter(order_in_topic__isnull=True).count()
    
    if topics_no_slug or subtopics_no_slug or subtopics_no_order:
        print("\n⚠️  Remaining Issues:")
        if topics_no_slug:
            print(f"    • {topics_no_slug} topics still missing slugs")
        if subtopics_no_slug:
            print(f"    • {subtopics_no_slug} subtopics still missing slugs")
        if subtopics_no_order:
            print(f"    • {subtopics_no_order} subtopics still missing order")
    else:
        print("\n✅ All required fields are now populated!")


def main():
    """Run all fixes"""
    print("🚀 Starting database restoration fixes...")
    print("=" * 60)
    
    try:
        from django.db import models
        
        fix_missing_slugs()
        fix_missing_order_fields()
        fix_missing_intent_fields()
        fix_missing_descriptions()
        
        display_summary()
        
        print("\n🎉 Database fixes complete!")
        print("Your restored data should now be compatible with the new schema.")
        
    except Exception as e:
        print(f"\n❌ Error during fixes: {e}")
        print("You may need to check your database connection or model definitions.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
