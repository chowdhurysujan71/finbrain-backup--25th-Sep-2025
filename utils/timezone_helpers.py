"""
Timezone Helper Functions for Growth Metrics
Provides standardized timezone handling for Asia/Dhaka timezone
Required by guardrails for D1/D3/streak calculations
"""

import logging
from datetime import date, datetime
from typing import Optional

import pytz

logger = logging.getLogger(__name__)

# Constants
DHAKA_TZ = pytz.timezone('Asia/Dhaka')
UTC_TZ = pytz.UTC

def to_local(dt: datetime, timezone_str: str = 'Asia/Dhaka') -> datetime:
    """
    Convert UTC datetime to local timezone
    
    Args:
        dt: UTC datetime object
        timezone_str: Target timezone (default: Asia/Dhaka)
        
    Returns:
        datetime: Localized datetime in target timezone
    """
    try:
        if dt is None:
            return None
            
        # Ensure dt is timezone-aware (assume UTC if naive)
        if dt.tzinfo is None:
            dt = UTC_TZ.localize(dt)
        elif dt.tzinfo != UTC_TZ:
            # Convert to UTC first if different timezone
            dt = dt.astimezone(UTC_TZ)
        
        # Convert to target timezone
        target_tz = pytz.timezone(timezone_str)
        return dt.astimezone(target_tz)
        
    except Exception as e:
        logger.error(f"Timezone conversion failed for {dt}: {e}")
        return dt  # Return original if conversion fails

def day_key(dt: datetime) -> str:
    """
    Convert datetime to YYYY-MM-DD string in local timezone
    
    Args:
        dt: datetime object
        
    Returns:
        str: Date string in YYYY-MM-DD format (Asia/Dhaka timezone)
    """
    try:
        if dt is None:
            return None
            
        local_dt = to_local(dt)
        return local_dt.strftime('%Y-%m-%d')
        
    except Exception as e:
        logger.error(f"Day key generation failed for {dt}: {e}")
        return None

def is_same_local_day(dt1: datetime, dt2: datetime) -> bool:
    """
    Check if two datetimes fall on the same local calendar day
    
    Args:
        dt1: First datetime
        dt2: Second datetime
        
    Returns:
        bool: True if same local day, False otherwise
    """
    try:
        if dt1 is None or dt2 is None:
            return False
            
        day1 = day_key(dt1)
        day2 = day_key(dt2)
        
        return day1 == day2 and day1 is not None
        
    except Exception as e:
        logger.error(f"Same day comparison failed for {dt1}, {dt2}: {e}")
        return False

def local_date_from_datetime(dt: datetime) -> date | None:
    """
    Extract local date from datetime
    
    Args:
        dt: datetime object
        
    Returns:
        date: Date in Asia/Dhaka timezone
    """
    try:
        if dt is None:
            return None
            
        local_dt = to_local(dt)
        return local_dt.date()
        
    except Exception as e:
        logger.error(f"Local date extraction failed for {dt}: {e}")
        return None

def days_between_local(dt1: datetime, dt2: datetime) -> int | None:
    """
    Calculate days between two datetimes in local timezone
    
    Args:
        dt1: Earlier datetime
        dt2: Later datetime
        
    Returns:
        int: Number of days between (positive if dt2 > dt1)
    """
    try:
        if dt1 is None or dt2 is None:
            return None
            
        date1 = local_date_from_datetime(dt1)
        date2 = local_date_from_datetime(dt2)
        
        if date1 is None or date2 is None:
            return None
            
        return (date2 - date1).days
        
    except Exception as e:
        logger.error(f"Days calculation failed for {dt1}, {dt2}: {e}")
        return None

def is_within_hours(dt1: datetime, dt2: datetime, hours: int) -> bool:
    """
    Check if two datetimes are within specified hours of each other
    
    Args:
        dt1: First datetime
        dt2: Second datetime  
        hours: Maximum hours between them
        
    Returns:
        bool: True if within specified hours
    """
    try:
        if dt1 is None or dt2 is None:
            return False
            
        # Calculate absolute difference in seconds
        diff_seconds = abs((dt2 - dt1).total_seconds())
        max_seconds = hours * 3600
        
        return diff_seconds <= max_seconds
        
    except Exception as e:
        logger.error(f"Hours comparison failed for {dt1}, {dt2}: {e}")
        return False

def now_local() -> datetime:
    """
    Get current time in Asia/Dhaka timezone
    
    Returns:
        datetime: Current local time
    """
    try:
        utc_now = datetime.utcnow()
        return to_local(utc_now)
    except Exception as e:
        logger.error(f"Local now calculation failed: {e}")
        return datetime.utcnow()  # Fallback to UTC

def today_local() -> date:
    """
    Get today's date in Asia/Dhaka timezone
    
    Returns:
        date: Today's local date
    """
    try:
        return now_local().date()
    except Exception as e:
        logger.error(f"Local today calculation failed: {e}")
        return datetime.utcnow().date()  # Fallback to UTC date

# Validation functions for testing
def validate_timezone_helpers():
    """
    Validate timezone helper functions work correctly
    For testing and debugging purposes
    """
    try:
        # Test current time conversion
        utc_now = datetime.utcnow()
        local_now = to_local(utc_now)
        
        # Test day key generation
        day_str = day_key(local_now)
        
        # Test same day comparison
        same_day = is_same_local_day(utc_now, local_now)
        
        logger.info(f"Timezone validation: UTC={utc_now}, Local={local_now}, DayKey={day_str}, SameDay={same_day}")
        return True
        
    except Exception as e:
        logger.error(f"Timezone validation failed: {e}")
        return False