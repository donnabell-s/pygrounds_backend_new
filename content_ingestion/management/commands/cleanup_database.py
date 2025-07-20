from django.core.management.base import BaseCommand
from django.db import transaction
from content_ingestion.models import (
    UploadedDocument, 
    DocumentChunk, 
    TOCEntry, 
    GameZone, 
    Topic, 
    Subtopic, 
    ContentMapping
)
from question_generation.models import GeneratedQuestion


class Command(BaseCommand):
    help = 'Clean up the database by removing all document processing data while keeping uploaded PDFs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-documents',
            action='store_true',
            help='Keep uploaded documents but reset their processing status',
        )
        parser.add_argument(
            '--keep-structure',
            action='store_true', 
            help='Keep GameZone/Topic/Subtopic structure but remove mappings',
        )
        parser.add_argument(
            '--full-reset',
            action='store_true',
            help='Remove everything including uploaded documents and structure',
        )
        parser.add_argument(
            '--document-id',
            type=int,
            help='Clean only a specific document by ID',
        )

    def handle(self, *args, **options):
        if options['full_reset']:
            self.full_database_reset()
        elif options['document_id']:
            self.clean_specific_document(options['document_id'])
        else:
            self.clean_processing_data(
                keep_documents=options['keep_documents'],
                keep_structure=options['keep_structure']
            )

    def full_database_reset(self):
        """Remove all data including uploaded documents"""
        self.stdout.write(
            self.style.WARNING('⚠️  FULL DATABASE RESET - This will remove EVERYTHING!')
        )
        
        with transaction.atomic():
            # Remove all data in dependency order
            counts = {}
            
            counts['questions'] = GeneratedQuestion.objects.count()
            GeneratedQuestion.objects.all().delete()
            
            counts['mappings'] = ContentMapping.objects.count()
            ContentMapping.objects.all().delete()
            
            counts['subtopics'] = Subtopic.objects.count()
            Subtopic.objects.all().delete()
            
            counts['topics'] = Topic.objects.count()
            Topic.objects.all().delete()
            
            counts['zones'] = GameZone.objects.count()
            GameZone.objects.all().delete()
            
            counts['chunks'] = DocumentChunk.objects.count()
            DocumentChunk.objects.all().delete()
            
            counts['toc_entries'] = TOCEntry.objects.count()
            TOCEntry.objects.all().delete()
            
            counts['documents'] = UploadedDocument.objects.count()
            UploadedDocument.objects.all().delete()
            
        self.stdout.write(self.style.SUCCESS('✅ Full database reset completed:'))
        for model, count in counts.items():
            self.stdout.write(f'   - Deleted {count} {model}')

    def clean_specific_document(self, document_id):
        """Clean data for a specific document only"""
        try:
            document = UploadedDocument.objects.get(id=document_id)
            self.stdout.write(f'🎯 Cleaning data for document: {document.title}')
            
            with transaction.atomic():
                counts = {}
                
                # Remove questions related to this document's structure
                questions = GeneratedQuestion.objects.filter(
                    subtopic__topic__gamezone__documents=document
                )
                counts['questions'] = questions.count()
                questions.delete()
                
                # Remove content mappings for this document's TOC
                mappings = ContentMapping.objects.filter(toc_entry__document=document)
                counts['mappings'] = mappings.count()
                mappings.delete()
                
                # Remove chunks for this document
                chunks = DocumentChunk.objects.filter(document=document)
                counts['chunks'] = chunks.count()
                chunks.delete()
                
                # Remove TOC entries for this document
                toc_entries = TOCEntry.objects.filter(document=document)
                counts['toc_entries'] = toc_entries.count()
                toc_entries.delete()
                
                # Reset document processing status
                document.processing_status = 'PENDING'
                document.parsed = False
                document.parsed_pages = []
                document.parse_metadata = {}
                document.save()
                
            self.stdout.write(self.style.SUCCESS(f'✅ Document {document_id} cleaned:'))
            for model, count in counts.items():
                self.stdout.write(f'   - Deleted {count} {model}')
                
        except UploadedDocument.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Document with ID {document_id} not found')
            )

    def clean_processing_data(self, keep_documents=True, keep_structure=False):
        """Clean processing data while optionally keeping documents and structure"""
        self.stdout.write('🧹 Cleaning processing data...')
        
        with transaction.atomic():
            counts = {}
            
            # Always remove questions and mappings
            counts['questions'] = GeneratedQuestion.objects.count()
            GeneratedQuestion.objects.all().delete()
            
            counts['mappings'] = ContentMapping.objects.count()
            ContentMapping.objects.all().delete()
            
            # Remove structure if not keeping it
            if not keep_structure:
                counts['subtopics'] = Subtopic.objects.count()
                Subtopic.objects.all().delete()
                
                counts['topics'] = Topic.objects.count()
                Topic.objects.all().delete()
                
                counts['zones'] = GameZone.objects.count()
                GameZone.objects.all().delete()
            
            # Always remove chunks and TOC
            counts['chunks'] = DocumentChunk.objects.count()
            DocumentChunk.objects.all().delete()
            
            counts['toc_entries'] = TOCEntry.objects.count()
            TOCEntry.objects.all().delete()
            
            # Handle documents
            if keep_documents:
                # Reset all documents to unprocessed state
                documents = UploadedDocument.objects.all()
                counts['documents'] = f'{documents.count()} (reset, not deleted)'
                documents.update(
                    processing_status='PENDING',
                    parsed=False,
                    parsed_pages=[],
                    parse_metadata={}
                )
            else:
                counts['documents'] = UploadedDocument.objects.count()
                UploadedDocument.objects.all().delete()
        
        self.stdout.write(self.style.SUCCESS('✅ Processing data cleaned:'))
        for model, count in counts.items():
            self.stdout.write(f'   - {model}: {count}')
        
        if keep_documents:
            self.stdout.write(
                self.style.SUCCESS('📁 Uploaded documents preserved and reset to unprocessed state')
            )
        
        if keep_structure:
            self.stdout.write(
                self.style.SUCCESS('🏗️  GameZone/Topic/Subtopic structure preserved')
            )

    def display_current_counts(self):
        """Display current record counts"""
        self.stdout.write('📊 Current database counts:')
        models = [
            ('Documents', UploadedDocument),
            ('TOC Entries', TOCEntry),
            ('Chunks', DocumentChunk),
            ('Game Zones', GameZone),
            ('Topics', Topic),
            ('Subtopics', Subtopic),
            ('Content Mappings', ContentMapping),
            ('Generated Questions', GeneratedQuestion),
        ]
        
        for name, model in models:
            count = model.objects.count()
            self.stdout.write(f'   - {name}: {count}')
