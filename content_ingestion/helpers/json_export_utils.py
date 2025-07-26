"""
JSON Export Utilities for PyGrounds Backend

Provides utilities for exporting and appending data to JSON files 
for easier debugging and analysis outside of Postman/console.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

class JSONExporter:
    """
    Handles JSON file operations for exporting data with append functionality.
    """
    
    def __init__(self, base_directory: str = "exports"):
        """
        Initialize the JSON exporter.
        
        Args:
            base_directory: Base directory for all JSON exports
        """
        self.base_dir = Path(base_directory)
        self.base_dir.mkdir(exist_ok=True)
        
    def append_to_json(self, filename: str, data: Dict[str, Any], 
                      max_entries: int = 1000) -> Dict[str, Any]:
        """
        Append data to a JSON file, creating it if it doesn't exist.
        
        Args:
            filename: Name of the JSON file (without extension)
            data: Data to append
            max_entries: Maximum number of entries to keep (oldest removed first)
            
        Returns:
            Dictionary with operation status and metadata
        """
        filepath = self.base_dir / f"{filename}.json"
        
        # Add timestamp to data
        timestamped_data = {
            "timestamp": datetime.now().isoformat(),
            "id": len(self._get_existing_data(filepath)) + 1,
            **data
        }
        
        try:
            # Load existing data
            existing_data = self._get_existing_data(filepath)
            
            # Append new data
            existing_data.append(timestamped_data)
            
            # Limit entries if needed
            if len(existing_data) > max_entries:
                existing_data = existing_data[-max_entries:]
                
            # Write back to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
                
            return {
                "status": "success",
                "filepath": str(filepath),
                "total_entries": len(existing_data),
                "new_entry_id": timestamped_data["id"]
            }
            
        except Exception as e:
            return {
                "status": "error", 
                "error": str(e),
                "filepath": str(filepath)
            }
    
    def _get_existing_data(self, filepath: Path) -> List[Dict[str, Any]]:
        """Load existing data from JSON file or return empty list."""
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return []
        return []
    
    def export_snapshot(self, filename: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export a complete snapshot to JSON (overwrites existing file).
        
        Args:
            filename: Name of the JSON file (without extension)
            data: Complete data to export
            
        Returns:
            Dictionary with operation status
        """
        filepath = self.base_dir / f"{filename}_snapshot.json"
        
        snapshot_data = {
            "exported_at": datetime.now().isoformat(),
            "data": data
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(snapshot_data, f, indent=2, ensure_ascii=False)
                
            return {
                "status": "success",
                "filepath": str(filepath),
                "data_size": len(str(data))
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "filepath": str(filepath)
            }
    
    def get_export_summary(self) -> Dict[str, Any]:
        """
        Get summary of all export files.
        
        Returns:
            Dictionary with export file information
        """
        files = []
        total_size = 0
        
        for filepath in self.base_dir.glob("*.json"):
            try:
                stat = filepath.stat()
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                files.append({
                    "filename": filepath.name,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "entries": len(data) if isinstance(data, list) else 1
                })
                total_size += stat.st_size
                
            except Exception as e:
                files.append({
                    "filename": filepath.name,
                    "error": str(e)
                })
        
        return {
            "export_directory": str(self.base_dir),
            "total_files": len(files),
            "total_size_bytes": total_size,
            "files": files
        }

# Global exporter instance
json_exporter = JSONExporter()

def log_question_generation(subtopic_id: int, questions: List[Dict], 
                          metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Log question generation results to JSON.
    
    Args:
        subtopic_id: ID of the subtopic
        questions: Generated questions
        metadata: Generation metadata (RAG context, model info, etc.)
        
    Returns:
        Log operation result
    """
    log_data = {
        "operation": "question_generation",
        "subtopic_id": subtopic_id,
        "questions_count": len(questions),
        "questions": questions,
        "metadata": metadata
    }
    
    return json_exporter.append_to_json("question_generation_log", log_data)

def log_toc_generation(document_id: int, toc_entries: List[Dict], 
                      metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Log TOC generation results to JSON.
    
    Args:
        document_id: ID of the document
        toc_entries: Generated TOC entries
        metadata: Generation metadata
        
    Returns:
        Log operation result
    """
    log_data = {
        "operation": "toc_generation",
        "document_id": document_id,
        "toc_entries_count": len(toc_entries),
        "toc_entries": toc_entries,
        "metadata": metadata
    }
    
    return json_exporter.append_to_json("toc_generation_log", log_data)

def log_embedding_generation(entity_type: str, entity_id: int, 
                           embedding_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Log embedding generation results to JSON.
    
    Args:
        entity_type: Type of entity (topic, subtopic, chunk)
        entity_id: ID of the entity
        embedding_results: Embedding generation results
        
    Returns:
        Log operation result
    """
    log_data = {
        "operation": "embedding_generation",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "embedding_results": embedding_results
    }
    
    return json_exporter.append_to_json("embedding_generation_log", log_data)

def log_chunk_processing(document_id: int, chunks: List[Dict], 
                        metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Log chunk processing results to JSON.
    
    Args:
        document_id: ID of the document
        chunks: Processed chunks
        metadata: Processing metadata
        
    Returns:
        Log operation result
    """
    log_data = {
        "operation": "chunk_processing", 
        "document_id": document_id,
        "chunks_count": len(chunks),
        "chunks": chunks,
        "metadata": metadata
    }
    
    return json_exporter.append_to_json("chunk_processing_log", log_data)

def export_complete_state_snapshot() -> Dict[str, Any]:
    """
    Export a complete snapshot of the current system state.
    
    Returns:
        Export operation result
    """
    try:
        from content_ingestion.models import UploadedDocument, DocumentChunk, TOCEntry
        from content_ingestion.models import GameZone, Topic, Subtopic
        
        # Gather all data
        documents = list(UploadedDocument.objects.values())
        chunks = list(DocumentChunk.objects.values())
        toc_entries = list(TOCEntry.objects.values())
        zones = list(GameZone.objects.values())
        topics = list(Topic.objects.values())
        subtopics = list(Subtopic.objects.values())
        
        snapshot_data = {
            "documents": {
                "count": len(documents),
                "data": documents
            },
            "chunks": {
                "count": len(chunks),
                "data": chunks
            },
            "toc_entries": {
                "count": len(toc_entries),
                "data": toc_entries
            },
            "learning_structure": {
                "zones": {"count": len(zones), "data": zones},
                "topics": {"count": len(topics), "data": topics},
                "subtopics": {"count": len(subtopics), "data": subtopics}
            }
        }
        
        return json_exporter.export_snapshot("complete_system_state", snapshot_data)
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
