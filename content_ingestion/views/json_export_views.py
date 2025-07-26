"""
JSON Export Views

Provides endpoints for accessing JSON export logs and generating snapshots.
"""

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
import os
from pathlib import Path

from content_ingestion.helpers.json_export_utils import json_exporter, export_complete_state_snapshot

@api_view(['GET'])
def get_export_summary(request):
    """
    Get summary of all JSON export files.
    
    Returns information about available export logs and snapshots.
    """
    try:
        summary = json_exporter.get_export_summary()
        return Response(summary, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            "error": f"Failed to get export summary: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def download_export_file(request, filename):
    """
    Download a specific JSON export file.
    
    Args:
        filename: Name of the export file (without .json extension)
    """
    try:
        filepath = json_exporter.base_dir / f"{filename}.json"
        
        if not filepath.exists():
            return Response({
                "error": f"Export file '{filename}.json' not found"
            }, status=status.HTTP_404_NOT_FOUND)
            
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        response = HttpResponse(
            json.dumps(data, indent=2, ensure_ascii=False),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}.json"'
        return response
        
    except Exception as e:
        return Response({
            "error": f"Failed to download export file: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def view_export_file(request, filename):
    """
    View the contents of a specific JSON export file in the browser.
    
    Args:
        filename: Name of the export file (without .json extension)
    """
    try:
        filepath = json_exporter.base_dir / f"{filename}.json"
        
        if not filepath.exists():
            return Response({
                "error": f"Export file '{filename}.json' not found"
            }, status=status.HTTP_404_NOT_FOUND)
            
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        return Response(data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            "error": f"Failed to view export file: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def create_system_snapshot(request):
    """
    Create a complete snapshot of the current system state.
    
    Exports all documents, chunks, TOC entries, and learning structure to JSON.
    """
    try:
        result = export_complete_state_snapshot()
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            "error": f"Failed to create system snapshot: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_recent_logs(request, log_type, count=10):
    """
    Get the most recent entries from a specific log type.
    
    Args:
        log_type: Type of log (question_generation, toc_generation, etc.)
        count: Number of recent entries to return (default: 10)
    """
    try:
        count = int(request.GET.get('count', count))
        filepath = json_exporter.base_dir / f"{log_type}_log.json"
        
        if not filepath.exists():
            return Response({
                "log_type": log_type,
                "entries": [],
                "message": f"No log file found for {log_type}"
            }, status=status.HTTP_200_OK)
            
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Get the most recent entries
        recent_entries = data[-count:] if len(data) > count else data
        
        return Response({
            "log_type": log_type,
            "total_entries": len(data),
            "returned_entries": len(recent_entries),
            "entries": recent_entries
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            "error": f"Failed to get recent logs: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
def clear_export_logs(request):
    """
    Clear all export log files (keeping snapshots).
    
    This removes all log files but preserves snapshot files.
    """
    try:
        cleared_files = []
        export_dir = json_exporter.base_dir
        
        for filepath in export_dir.glob("*_log.json"):
            filepath.unlink()
            cleared_files.append(filepath.name)
            
        return Response({
            "status": "success",
            "cleared_files": cleared_files,
            "message": f"Cleared {len(cleared_files)} log files"
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            "error": f"Failed to clear export logs: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_log_statistics(request):
    """
    Get statistics about all log files.
    
    Returns counts, dates, and size information for all export logs.
    """
    try:
        export_dir = json_exporter.base_dir
        stats = {
            "logs": {},
            "snapshots": {},
            "summary": {
                "total_log_files": 0,
                "total_snapshot_files": 0,
                "total_entries": 0
            }
        }
        
        # Process log files
        for filepath in export_dir.glob("*_log.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                log_name = filepath.stem.replace('_log', '')
                stats["logs"][log_name] = {
                    "entries": len(data),
                    "latest_entry": data[-1]["timestamp"] if data else None,
                    "file_size_bytes": filepath.stat().st_size
                }
                stats["summary"]["total_entries"] += len(data)
                stats["summary"]["total_log_files"] += 1
                
            except Exception as e:
                stats["logs"][filepath.stem] = {"error": str(e)}
        
        # Process snapshot files
        for filepath in export_dir.glob("*_snapshot.json"):
            try:
                stat = filepath.stat()
                snapshot_name = filepath.stem.replace('_snapshot', '')
                stats["snapshots"][snapshot_name] = {
                    "file_size_bytes": stat.st_size,
                    "created": stat.st_mtime
                }
                stats["summary"]["total_snapshot_files"] += 1
                
            except Exception as e:
                stats["snapshots"][filepath.stem] = {"error": str(e)}
        
        return Response(stats, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            "error": f"Failed to get log statistics: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
