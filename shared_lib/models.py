"""
Common data models used across the ETL pipeline
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class EventData:
    """Base event data structure"""

    event_id: str
    event_date: datetime
    raw_data: dict
    processed_data: Optional[dict] = None


@dataclass
class ProcessingStatus:
    """Status tracking for processing steps"""

    step_name: str
    status: str  # 'pending', 'in_progress', 'completed', 'failed'
    timestamp: datetime
    error_message: Optional[str] = None


@dataclass
class CacheEntry:
    """Redis cache entry structure"""

    key: str
    value: dict
    ttl: int  # Time to live in seconds
    access_level: str  # 'free', 'premium'
