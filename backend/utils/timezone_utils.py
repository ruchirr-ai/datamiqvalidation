"""
Timezone Utilities

Converts UTC datetime to IST (Indian Standard Time) for display
"""
from datetime import datetime, timedelta
from typing import Optional

# IST is UTC+5:30
IST_OFFSET = timedelta(hours=5, minutes=30)

def utc_to_ist(utc_datetime: Optional[datetime]) -> Optional[datetime]:
    """
    Convert UTC datetime to IST
    
    Args:
        utc_datetime: UTC datetime object
        
    Returns:
        IST datetime object or None if input is None
    """
    if utc_datetime is None:
        return None
    
    # If datetime is naive (no timezone info), assume it's UTC
    if utc_datetime.tzinfo is None:
        return utc_datetime + IST_OFFSET
    
    # If datetime has timezone info, convert to UTC first then add IST offset
    utc_datetime = utc_datetime.replace(tzinfo=None)
    return utc_datetime + IST_OFFSET

def utc_to_ist_string(utc_datetime: Optional[datetime]) -> Optional[str]:
    """
    Convert UTC datetime to IST and return as ISO string
    
    Args:
        utc_datetime: UTC datetime object or datetime string
        
    Returns:
        IST datetime as ISO string or None if input is None
    """
    if utc_datetime is None:
        return None
    
    # If it's already a string, try to parse it first
    if isinstance(utc_datetime, str):
        try:
            utc_datetime = datetime.fromisoformat(utc_datetime.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            # If parsing fails, return the original string
            return utc_datetime
    
    ist_datetime = utc_to_ist(utc_datetime)
    if ist_datetime is None:
        return None
    
    return ist_datetime.isoformat()
