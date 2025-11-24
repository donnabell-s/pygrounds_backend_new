"""
Django management command to check game_data fields in existing questions.
"""

from django.core.management.base import BaseCommand
from question_generation.models import GeneratedQuestion
import json


class Command(BaseCommand):
    help = 'Check game_data fields in existing questions'

    def handle(self, *args, **options):
        questions = GeneratedQuestion.objects.all()[:10]
        
        self.stdout.write(f"Checking first 10 questions out of {GeneratedQuestion.objects.count()} total")
        
        # Check for the deprecated fields we want to remove
        deprecated_fields = ['used', 'context', 'auto_generated', 'pipeline_version', 'is_cross_subtopic']
        
        questions_with_deprecated = 0
        
        for q in questions:
            if q.game_data:
                has_deprecated = any(field in q.game_data for field in deprecated_fields)
                
                # Check nested rag_context
                has_nested_deprecated = False
                if 'rag_context' in q.game_data and isinstance(q.game_data['rag_context'], dict):
                    has_nested_deprecated = any(field in q.game_data['rag_context'] for field in ['used', 'context'])
                
                if has_deprecated or has_nested_deprecated:
                    questions_with_deprecated += 1
                    deprecated_found = []
                    
                    for field in deprecated_fields:
                        if field in q.game_data:
                            deprecated_found.append(field)
                    
                    if 'rag_context' in q.game_data and isinstance(q.game_data['rag_context'], dict):
                        for field in ['used', 'context']:
                            if field in q.game_data['rag_context']:
                                deprecated_found.append(f'rag_context.{field}')
                    
                    self.stdout.write(f"Question {q.id}: Found deprecated fields: {', '.join(deprecated_found)}")
                else:
                    self.stdout.write(f"Question {q.id}: Clean - Keys: {list(q.game_data.keys())}")
            else:
                self.stdout.write(f"Question {q.id}: No game_data")
        
        self.stdout.write(f"\nSummary: {questions_with_deprecated} out of 10 questions have deprecated fields")
        
        if questions_with_deprecated > 0:
            self.stdout.write(self.style.WARNING("Run 'python manage.py clean_game_data_fields' to clean them"))
        else:
            self.stdout.write(self.style.SUCCESS("All checked questions are clean!"))
