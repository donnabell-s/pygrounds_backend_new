"""
Django management command to clean deprecated fields from GeneratedQuestion game_data.

This command removes the following fields from existing GeneratedQuestion game_data:
- used
- context  
- auto_generated
- pipeline_version
- is_cross_subtopic

Also removes 'used' and 'context' from nested rag_context objects.

Usage: python manage.py clean_game_data_fields
"""

from django.core.management.base import BaseCommand
from question_generation.models import GeneratedQuestion


class Command(BaseCommand):
    help = 'Clean deprecated fields from GeneratedQuestion game_data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Fields to remove from game_data
        fields_to_remove = ['used', 'context', 'auto_generated', 'pipeline_version', 'is_cross_subtopic']
        rag_context_fields_to_remove = ['used', 'context']
        
        # Get all questions with game_data
        questions = GeneratedQuestion.objects.exclude(game_data__isnull=True).exclude(game_data={})
        
        updated_count = 0
        total_count = questions.count()
        
        self.stdout.write(f"Found {total_count} questions with game_data")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
        
        for question in questions:
            game_data = question.game_data.copy()
            original_data = question.game_data.copy()
            
            # Remove deprecated fields from top level
            fields_removed = []
            for field in fields_to_remove:
                if field in game_data:
                    if not dry_run:
                        del game_data[field]
                    fields_removed.append(field)
            
            # Remove deprecated fields from nested rag_context
            rag_fields_removed = []
            if 'rag_context' in game_data and isinstance(game_data['rag_context'], dict):
                for field in rag_context_fields_to_remove:
                    if field in game_data['rag_context']:
                        if not dry_run:
                            del game_data['rag_context'][field]
                        rag_fields_removed.append(f'rag_context.{field}')
                
                # Remove empty rag_context entirely
                if not dry_run and not game_data['rag_context']:
                    del game_data['rag_context']
                    rag_fields_removed.append('rag_context (empty)')
                elif dry_run and not game_data['rag_context']:
                    rag_fields_removed.append('rag_context (empty)')
            
            # Also check for empty rag_context at top level
            elif 'rag_context' in game_data and not game_data['rag_context']:
                if not dry_run:
                    del game_data['rag_context']
                rag_fields_removed.append('rag_context (empty)')
            
            # Update the question if any fields were removed
            if fields_removed or rag_fields_removed:
                if not dry_run:
                    question.game_data = game_data
                    question.save(update_fields=['game_data'])
                
                updated_count += 1
                all_removed = fields_removed + rag_fields_removed
                
                if dry_run or len(all_removed) <= 3:  # Show details for dry run or few fields
                    self.stdout.write(
                        f"Question {question.id}: Removed {', '.join(all_removed)}"
                    )
                elif updated_count % 10 == 0:  # Show progress for bulk updates
                    self.stdout.write(f"Updated {updated_count}/{total_count} questions...")
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"DRY RUN: Would update {updated_count} out of {total_count} questions")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully updated {updated_count} out of {total_count} questions")
            )
            
        if updated_count == 0:
            self.stdout.write("No questions needed updating - all game_data is already clean!")
