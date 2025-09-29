# Common utilities for question generation
# Shared functions and constants to reduce code duplication

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEOUT = 120
MAX_RETRIES = 3
DEFAULT_BATCH_SIZE = 50

# Common validation patterns
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def safe_get_nested_value(data: Dict[str, Any], 
                         keys: List[str], 
                         default: Any = None) -> Any:
    """
    Safely get a nested value from a dictionary.
    
    Args:
        data: The dictionary to search
        keys: List of keys to traverse (e.g., ['user', 'profile', 'name'])
        default: Default value if key path doesn't exist
        
    Returns:
        The value at the key path or default
        
    Example:
        safe_get_nested_value({'user': {'profile': {'name': 'John'}}}, ['user', 'profile', 'name'])
        # Returns: 'John'
    """
    try:
        result = data
        for key in keys:
            result = result[key]
        return result
    except (KeyError, TypeError, AttributeError):
        return default


def safe_int_conversion(value: Any, default: int = 0) -> int:
    """
    Safely convert a value to integer.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Integer value or default
    """
    try:
        if isinstance(value, (int, float)):
            return int(value)
        elif isinstance(value, str):
            # Handle common string formats
            cleaned = value.strip().replace(',', '')
            return int(float(cleaned))
        else:
            return default
    except (ValueError, TypeError, AttributeError):
        return default


def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Float value or default
    """
    try:
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            # Handle percentages and common formats
            cleaned = value.strip().replace(',', '').replace('%', '')
            return float(cleaned)
        else:
            return default
    except (ValueError, TypeError, AttributeError):
        return default


def validate_positive_integer(value: Any, field_name: str = "value") -> int:
    """
    Validate and convert a value to a positive integer.
    
    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        
    Returns:
        Validated positive integer
        
    Raises:
        ValueError: If value is not a positive integer
    """
    try:
        int_value = safe_int_conversion(value)
        if int_value <= 0:
            raise ValueError(f"{field_name} must be a positive integer, got: {value}")
        return int_value
    except Exception as e:
        raise ValueError(f"Invalid {field_name}: {value}. Error: {str(e)}")


def validate_string_list(value: Any, 
                        field_name: str = "list", 
                        min_length: int = 1,
                        max_length: Optional[int] = None) -> List[str]:
    """
    Validate that a value is a list of non-empty strings.
    
    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        min_length: Minimum number of items required
        max_length: Maximum number of items allowed (None = no limit)
        
    Returns:
        List of validated strings
        
    Raises:
        ValueError: If validation fails
    """
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list, got: {type(value).__name__}")
    
    if len(value) < min_length:
        raise ValueError(f"{field_name} must contain at least {min_length} item(s), got: {len(value)}")
    
    if max_length and len(value) > max_length:
        raise ValueError(f"{field_name} must contain at most {max_length} item(s), got: {len(value)}")
    
    # Validate each item is a non-empty string
    validated_items = []
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{field_name}[{i}] must be a string, got: {type(item).__name__}")
        
        cleaned_item = item.strip()
        if not cleaned_item:
            raise ValueError(f"{field_name}[{i}] cannot be empty or whitespace only")
        
        validated_items.append(cleaned_item)
    
    return validated_items


def format_duration_human(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Human-readable duration string
    """
    if seconds < 0:
        return "0 seconds"
    
    if seconds < 60:
        return f"{int(seconds)} second{'s' if int(seconds) != 1 else ''}"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        remaining_seconds = int(seconds % 60)
        if remaining_seconds == 0:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = int(seconds / 3600)
        remaining_minutes = int((seconds % 3600) / 60)
        if remaining_minutes == 0:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        return f"{hours}h {remaining_minutes}m"


def calculate_percentage(part: float, whole: float, precision: int = 1) -> float:
    """
    Calculate percentage with safe division.
    
    Args:
        part: The part value
        whole: The whole value
        precision: Number of decimal places
        
    Returns:
        Percentage value (0-100)
    """
    if whole == 0:
        return 0.0
    
    percentage = (part / whole) * 100
    return round(percentage, precision)


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split a list into chunks of specified size.
    
    Args:
        items: List to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    if chunk_size <= 0:
        raise ValueError("Chunk size must be positive")
    
    chunks = []
    for i in range(0, len(items), chunk_size):
        chunks.append(items[i:i + chunk_size])
    
    return chunks


def remove_duplicates_preserve_order(items: List[Any]) -> List[Any]:
    """
    Remove duplicates from a list while preserving order.
    
    Args:
        items: List with potential duplicates
        
    Returns:
        List with duplicates removed, order preserved
    """
    seen = set()
    result = []
    
    for item in items:
        # Use a hashable representation for unhashable types
        if isinstance(item, (list, dict)):
            key = str(item)
        else:
            key = item
            
        if key not in seen:
            seen.add(key)
            result.append(item)
    
    return result


def log_performance(operation_name: str, 
                   start_time: float, 
                   success: bool = True,
                   details: Optional[Dict[str, Any]] = None) -> None:
    """
    Log performance metrics for operations.
    
    Args:
        operation_name: Name of the operation
        start_time: Start time (from time.time())
        success: Whether operation was successful
        details: Additional details to log
    """
    import time
    
    duration = time.time() - start_time
    status = "SUCCESS" if success else "FAILED"
    
    base_msg = f"🔍 {operation_name} {status} in {format_duration_human(duration)}"
    
    if details:
        detail_strs = [f"{k}={v}" for k, v in details.items()]
        base_msg += f" ({', '.join(detail_strs)})"
    
    if success:
        logger.info(base_msg)
    else:
        logger.warning(base_msg)


def create_error_response(error_message: str, 
                         error_code: Optional[str] = None,
                         details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Args:
        error_message: Main error message
        error_code: Optional error code
        details: Additional error details
        
    Returns:
        Standardized error response dictionary
    """
    response = {
        'success': False,
        'error': error_message,
        'timestamp': datetime.now().isoformat()
    }
    
    if error_code:
        response['error_code'] = error_code
    
    if details:
        response['details'] = details
    
    return response


def create_success_response(data: Any = None, 
                           message: Optional[str] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a standardized success response.
    
    Args:
        data: Response data
        message: Optional success message
        metadata: Additional metadata
        
    Returns:
        Standardized success response dictionary
    """
    response = {
        'success': True,
        'timestamp': datetime.now().isoformat()
    }
    
    if data is not None:
        response['data'] = data
    
    if message:
        response['message'] = message
    
    if metadata:
        response['metadata'] = metadata
    
    return response


def extract_object_names(objects: List[Any], name_attribute: str = 'name') -> List[str]:
    """
    Extract names from a list of objects.
    
    Args:
        objects: List of objects with name attributes
        name_attribute: Name of the attribute containing the name
        
    Returns:
        List of extracted names
    """
    names = []
    for obj in objects:
        try:
            if hasattr(obj, name_attribute):
                name = getattr(obj, name_attribute)
                if isinstance(name, str) and name.strip():
                    names.append(name.strip())
        except (AttributeError, TypeError):
            continue
    
    return names


def batch_process(items: List[Any], 
                 process_func: Any,
                 batch_size: int = DEFAULT_BATCH_SIZE,
                 max_workers: int = 4) -> List[Any]:
    """
    Process items in batches with optional parallelization.
    
    Args:
        items: Items to process
        process_func: Function to process each batch
        batch_size: Size of each batch
        max_workers: Maximum number of worker threads
        
    Returns:
        List of processing results
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    if not items:
        return []
    
    chunks = chunk_list(items, batch_size)
    results = []
    
    if max_workers <= 1:
        # Sequential processing
        for chunk in chunks:
            try:
                result = process_func(chunk)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing batch: {str(e)}")
                results.append(None)
    else:
        # Parallel processing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {executor.submit(process_func, chunk): chunk for chunk in chunks}
            
            for future in as_completed(future_to_chunk):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    chunk = future_to_chunk[future]
                    logger.error(f"Error processing batch {chunk}: {str(e)}")
                    results.append(None)
    
    return results