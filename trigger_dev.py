"""
Trigger.dev Python SDK compatibility wrapper.

This module provides a compatibility layer for Trigger.dev's Python SDK.
When running on Trigger.dev infrastructure, these decorators will be
replaced with the actual SDK.

For local development, these provide mock functionality so the code runs.
"""
import os
import sys
from functools import wraps
from typing import Any, Callable, Optional
from dataclasses import dataclass

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class TriggerContext:
    """Mock Trigger.dev context for local development."""
    run: Any = None
    
    def __post_init__(self):
        if self.run is None:
            self.run = type('Run', (), {'id': 'local-run-001'})()


class TriggerLogger:
    """Mock logger that works both locally and in Trigger.dev."""
    
    @staticmethod
    def info(message: str, properties: Optional[dict] = None):
        if properties:
            print(f"[INFO] {message} | {properties}")
        else:
            print(f"[INFO] {message}")
    
    @staticmethod
    def error(message: str, properties: Optional[dict] = None):
        if properties:
            print(f"[ERROR] {message} | {properties}", file=sys.stderr)
        else:
            print(f"[ERROR] {message}", file=sys.stderr)
    
    @staticmethod
    def debug(message: str, properties: Optional[dict] = None):
        if os.getenv("DEBUG"):
            if properties:
                print(f"[DEBUG] {message} | {properties}")
            else:
                print(f"[DEBUG] {message}")
    
    @staticmethod
    def warn(message: str, properties: Optional[dict] = None):
        if properties:
            print(f"[WARN] {message} | {properties}")
        else:
            print(f"[WARN] {message}")


# Global logger instance
logger = TriggerLogger()


def task(
    id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    retries: int = 0,
    timeout: Optional[str] = None,
    **kwargs
) -> Callable:
    """
    Decorator to mark a function as a Trigger.dev task.
    
    When running on Trigger.dev, this will be replaced with the actual SDK.
    For local development, this just wraps the function.
    
    Args:
        id: Unique task identifier
        name: Human-readable name
        description: Task description
        retries: Number of retry attempts on failure
        timeout: Maximum execution time (e.g., "10m", "1h")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check if running on Trigger.dev
            if os.getenv("TRIGGER_ENV"):
                # Running on Trigger.dev - the SDK will handle this
                return func(*args, **kwargs)
            
            # Local development mode
            print(f"\n{'='*60}")
            print(f"[LOCAL MODE] Task: {id}")
            if name:
                print(f"Name: {name}")
            if description:
                print(f"Description: {description}")
            print(f"{'='*60}\n")
            
            # Ensure context is provided
            if not args or not isinstance(args[0], TriggerContext):
                args = (TriggerContext(),) + args
            
            try:
                result = func(*args, **kwargs)
                print(f"\n[LOCAL MODE] Task {id} completed successfully")
                return result
            except Exception as e:
                print(f"\n[LOCAL MODE] Task {id} failed: {e}")
                raise
        
        # Store metadata on the function
        wrapper._trigger_task_id = id
        wrapper._trigger_name = name
        wrapper._trigger_description = description
        wrapper._trigger_retries = retries
        wrapper._trigger_timeout = timeout
        
        return wrapper
    return decorator


# Try to import actual Trigger.dev SDK if available
try:
    # If the actual SDK is installed, use it
    from trigger_ai import task as _real_task, logger as _real_logger
    # Replace our mocks with real implementations
    task = _real_task
    logger = _real_logger
    print("[Trigger.dev] Using production SDK")
except ImportError:
    # Use our mock implementations for local development
    pass
