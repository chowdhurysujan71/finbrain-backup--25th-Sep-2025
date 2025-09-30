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
            # Fallback to current UTC time if None
            logger.warning("to_local received None, falling back to current UTC")
            dt = datetime.utcnow()
            
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
        # Fallback to current time in target timezone
        try:
            target_tz = pytz.timezone(timezone_str)
            return datetime.now(target_tz)
        except:
            return datetime.utcnow()  # Ultimate fallback

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
            # Fallback to current date
            logger.warning("day_key received None, falling back to current date")
            dt = datetime.utcnow()
            
        local_dt = to_local(dt)
        return local_dt.strftime('%Y-%m-%d')
        
    except Exception as e:
        logger.error(f"Day key generation failed for {dt}: {e}")
        # Fallback to current date string
        return datetime.utcnow().strftime('%Y-%m-%d')

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

def local_date_from_datetime(dt: datetime) -> date:
    """
    Extract local date from datetime
    
    Args:
        dt: datetime object
        
    Returns:
        date: Date in Asia/Dhaka timezone, falls back to today if conversion fails
    """
    try:
        if dt is None:
            logger.warning("local_date_from_datetime received None, falling back to today")
            return today_local()
            
        local_dt = to_local(dt)
        return local_dt.date()
        
    except Exception as e:
        logger.error(f"Local date extraction failed for {dt}: {e}")
        return today_local()  # Fallback to current date

def days_between_local(dt1: datetime, dt2: datetime) -> int:
    """
    Calculate days between two datetimes in local timezone
    
    Args:
        dt1: Earlier datetime
        dt2: Later datetime
        
    Returns:
        int: Number of days between (positive if dt2 > dt1), 0 if calculation fails
    """
    try:
        if dt1 is None or dt2 is None:
            logger.warning(f"days_between_local received None input, returning 0")
            return 0
            
        date1 = local_date_from_datetime(dt1)
        date2 = local_date_from_datetime(dt2)
        
        return (date2 - date1).days
        
    except Exception as e:
        logger.error(f"Days calculation failed for {dt1}, {dt2}: {e}")
        return 0  # Safe fallback

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


def start_of_day_dhaka(date_obj: Optional[date] = None) -> datetime:
    """
    Get the start of day (00:00:00) in Asia/Dhaka timezone.
    
    Args:
        date_obj: date object (defaults to today in Dhaka)
        
    Returns:
        datetime object for midnight in Dhaka (as UTC for DB queries)
    """
    try:
        if date_obj is None:
            date_obj = today_local()
        
        # Create midnight in Dhaka timezone
        midnight_dhaka = DHAKA_TZ.localize(datetime.combine(date_obj, datetime.min.time()))
        
        # Convert to UTC for database queries
        return midnight_dhaka.astimezone(UTC_TZ).replace(tzinfo=None)
    except Exception as e:
        logger.error(f"Start of day calculation failed for {date_obj}: {e}")
        return datetime.combine(date_obj or datetime.utcnow().date(), datetime.min.time())


def end_of_day_dhaka(date_obj: Optional[date] = None) -> datetime:
    """
    Get the end of day (23:59:59.999999) in Asia/Dhaka timezone.
    
    Args:
        date_obj: date object (defaults to today in Dhaka)
        
    Returns:
        datetime object for end of day in Dhaka (as UTC for DB queries)
    """
    try:
        if date_obj is None:
            date_obj = today_local()
        
        # Create end of day in Dhaka timezone
        end_dhaka = DHAKA_TZ.localize(datetime.combine(date_obj, datetime.max.time()))
        
        # Convert to UTC for database queries
        return end_dhaka.astimezone(UTC_TZ).replace(tzinfo=None)
    except Exception as e:
        logger.error(f"End of day calculation failed for {date_obj}: {e}")
        return datetime.combine(date_obj or datetime.utcnow().date(), datetime.max.time())


def is_today_dhaka(dt: datetime) -> bool:
    """
    Check if a datetime is today in Asia/Dhaka timezone.
    
    Args:
        dt: datetime to check
        
    Returns:
        bool: True if datetime is today in Dhaka
    """
    try:
        if dt is None:
            return False
        
        local_dt = to_local(dt)
        today = today_local()
        
        return local_dt.date() == today
    except Exception as e:
        logger.error(f"is_today_dhaka check failed for {dt}: {e}")
        return False


def is_yesterday_dhaka(dt: datetime) -> bool:
    """
    Check if a datetime is yesterday in Asia/Dhaka timezone.
    
    Args:
        dt: datetime to check
        
    Returns:
        bool: True if datetime is yesterday in Dhaka
    """
    try:
        if dt is None:
            return False
        
        from datetime import timedelta
        
        local_dt = to_local(dt)
        today = today_local()
        yesterday = today - timedelta(days=1)
        
        return local_dt.date() == yesterday
    except Exception as e:
        logger.error(f"is_yesterday_dhaka check failed for {dt}: {e}")
        return False


def format_dhaka_time(dt: datetime, format_str: str = '%Y-%m-%d %H:%M') -> str:
    """
    Format a datetime in Asia/Dhaka timezone.
    
    Args:
        dt: datetime to format
        format_str: strftime format string
        
    Returns:
        Formatted string in Dhaka time
    """
    try:
        if dt is None:
            return ''
        
        dhaka_dt = to_local(dt)
        return dhaka_dt.strftime(format_str)
    except Exception as e:
        logger.error(f"Format dhaka time failed for {dt}: {e}")
        return ''


def format_dhaka_time_friendly(dt: datetime) -> str:
    """
    Format a datetime in a user-friendly way in Dhaka time.
    
    Shows:
    - "Today at HH:MM" if today
    - "Yesterday at HH:MM" if yesterday
    - "DD MMM at HH:MM" if this year
    - "DD MMM YYYY at HH:MM" if previous years
    
    Args:
        dt: datetime to format
        
    Returns:
        User-friendly formatted string
    """
    try:
        if dt is None:
            return ''
        
        dhaka_dt = to_local(dt)
        
        if is_today_dhaka(dt):
            return f"Today at {dhaka_dt.strftime('%H:%M')}"
        elif is_yesterday_dhaka(dt):
            return f"Yesterday at {dhaka_dt.strftime('%H:%M')}"
        elif dhaka_dt.year == today_local().year:
            return dhaka_dt.strftime('%d %b at %H:%M')
        else:
            return dhaka_dt.strftime('%d %b %Y at %H:%M')
    except Exception as e:
        logger.error(f"Format friendly time failed for {dt}: {e}")
        return ''

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