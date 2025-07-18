from typing import Dict
from django.db import transaction
from content_ingestion.models import UploadedDocument, PageChunk, TOCEntry

class ChunkStorage:
    """
    PostgreSQL-based storage for PDF page chunks
    """
    def __init__(self):
        self.batch_size = 100  # Adjust based on your needs

    @transaction.atomic
    def batch_save_chunks(self, chunks: Dict[str, str], document_id: int) -> None:
        """
        Save multiple chunks in a batch operation
        
        Args:
            chunks: Dictionary mapping page IDs to chunk content
            document_id: ID of the UploadedDocument
        """
        document = UploadedDocument.objects.get(id=document_id)
        chunk_objects = []
        
        for page_key, content in chunks.items():
            # Extract page number from key (e.g., 'page_1' -> 1)
            page_number = int(page_key.split('_')[1])
            
            chunk = PageChunk(
                document=document,
                page_number=page_number,
                content=content
            )
            chunk_objects.append(chunk)
            
            # Batch create in smaller chunks to optimize memory
            if len(chunk_objects) >= self.batch_size:
                PageChunk.objects.bulk_create(chunk_objects, ignore_conflicts=True)
                chunk_objects = []
        
        # Create any remaining chunks
        if chunk_objects:
            PageChunk.objects.bulk_create(chunk_objects, ignore_conflicts=True)

    def get_chunks_by_topic(self, document_id: int, topic_id: int) -> Dict[str, str]:
        """
        Get all chunks associated with a specific topic
        
        Args:
            document_id: ID of the document
            topic_id: ID of the TOC entry/topic
            
        Returns:
            Dictionary mapping page numbers to chunk content
        """
        chunks = PageChunk.objects.filter(
            document_id=document_id,
            toc_entry_id=topic_id
        ).order_by('page_number')
        
        return {f"page_{chunk.page_number}": chunk.content for chunk in chunks}

    def get_document_chunks(self, document_id: int) -> Dict[str, str]:
        """
        Get all chunks for a document
        
        Args:
            document_id: ID of the document
            
        Returns:
            Dictionary mapping page numbers to chunk content
        """
        chunks = PageChunk.objects.filter(
            document_id=document_id
        ).order_by('page_number')
        
        return {f"page_{chunk.page_number}": chunk.content for chunk in chunks}

    def update_chunk_topic(self, document_id: int, page_number: int, topic_id: int) -> None:
        """
        Update the topic association for a chunk
        
        Args:
            document_id: ID of the document
            page_number: Page number of the chunk
            topic_id: ID of the TOC entry to associate with
        """
        PageChunk.objects.filter(
            document_id=document_id,
            page_number=page_number
        ).update(toc_entry_id=topic_id)

    def delete_document_chunks(self, document_id: int) -> None:
        """
        Delete all chunks for a document
        
        Args:
            document_id: ID of the document
        """
        PageChunk.objects.filter(document_id=document_id).delete()
