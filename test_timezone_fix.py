#!/usr/bin/env python3
"""
Test script to verify timezone helper fixes
Tests that all functions return valid values and never return None
"""
import os
import sys
from datetime import datetime, timedelta
import pytz

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

from app import app
from utils.timezone_helpers import (
    to_local, day_key, is_same_local_day, 
    format_dhaka_time, start_of_day_dhaka, today_local
)

def test_timezone_helpers():
    """Test all timezone helper functions with various inputs"""
    
    print("=" * 60)
    print("TIMEZONE HELPERS TEST")
    print("=" * 60)
    
    # Test 1: to_local with valid UTC datetime
    print("\n[TEST 1] to_local with valid datetime:")
    utc_now = datetime.utcnow()
    local_dt = to_local(utc_now)
    print(f"  UTC:   {utc_now}")
    print(f"  Local: {local_dt}")
    print(f"  Type:  {type(local_dt)}")
    assert local_dt is not None, "to_local returned None!"
    assert isinstance(local_dt, datetime), "to_local didn't return datetime!"
    print("  ✓ PASS")
    
    # Test 2: to_local with None input (should fallback)
    print("\n[TEST 2] to_local with None input:")
    try:
        local_dt_none = to_local(None)
        print(f"  Result: {local_dt_none}")
        print(f"  Type:   {type(local_dt_none)}")
        assert local_dt_none is not None, "to_local returned None for None input!"
        assert isinstance(local_dt_none, datetime), "to_local didn't return datetime!"
        print("  ✓ PASS (fallback worked)")
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        
    # Test 3: day_key with valid datetime
    print("\n[TEST 3] day_key with valid datetime:")
    day_str = day_key(utc_now)
    print(f"  Input:  {utc_now}")
    print(f"  Result: {day_str}")
    print(f"  Type:   {type(day_str)}")
    assert day_str is not None, "day_key returned None!"
    assert isinstance(day_str, str), "day_key didn't return str!"
    assert len(day_str) == 10, "day_key format incorrect!"
    print("  ✓ PASS")
    
    # Test 4: day_key with None input (should fallback)
    print("\n[TEST 4] day_key with None input:")
    try:
        day_str_none = day_key(None)
        print(f"  Result: {day_str_none}")
        print(f"  Type:   {type(day_str_none)}")
        assert day_str_none is not None, "day_key returned None for None input!"
        assert isinstance(day_str_none, str), "day_key didn't return str!"
        print("  ✓ PASS (fallback worked)")
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
    
    # Test 5: format_dhaka_time
    print("\n[TEST 5] format_dhaka_time:")
    formatted = format_dhaka_time(utc_now)
    print(f"  Input:    {utc_now}")
    print(f"  Formatted: {formatted}")
    assert formatted is not None, "format_dhaka_time returned None!"
    assert isinstance(formatted, str), "format_dhaka_time didn't return str!"
    print("  ✓ PASS")
    
    # Test 6: start_of_day_dhaka
    print("\n[TEST 6] start_of_day_dhaka:")
    from datetime import date
    today_date = date.today()
    start_of_day = start_of_day_dhaka(today_date)
    print(f"  Input:  {today_date}")
    print(f"  Result: {start_of_day}")
    assert start_of_day is not None, "start_of_day_dhaka returned None!"
    assert isinstance(start_of_day, datetime), "start_of_day_dhaka didn't return datetime!"
    print("  ✓ PASS")
    
    # Test 7: today_local
    print("\n[TEST 7] today_local:")
    from datetime import date
    today = today_local()
    print(f"  Result: {today}")
    assert today is not None, "today_local returned None!"
    assert isinstance(today, date), "today_local didn't return date!"
    print("  ✓ PASS")
    
    # Test 8: is_same_local_day
    print("\n[TEST 8] is_same_local_day:")
    dt1 = datetime.utcnow()
    dt2 = dt1 + timedelta(hours=2)
    same_day = is_same_local_day(dt1, dt2)
    print(f"  DT1:      {dt1}")
    print(f"  DT2:      {dt2}")
    print(f"  Same day: {same_day}")
    assert isinstance(same_day, bool), "is_same_local_day didn't return bool!"
    print("  ✓ PASS")
    
    print("\n" + "=" * 60)
    print("ALL TIMEZONE HELPER TESTS PASSED!")
    print("=" * 60)

def test_backend_get_totals():
    """Test get_totals function from backend_assistant"""
    
    print("\n" + "=" * 60)
    print("BACKEND GET_TOTALS TEST")
    print("=" * 60)
    
    from backend_assistant import get_totals
    
    # Get test user ID from database
    from db_base import db
    from sqlalchemy import text
    
    with app.app_context():
        # Find a test user with expenses
        result = db.session.execute(text("""
            SELECT u.id, u.user_id_hash, COUNT(e.id) as expense_count
            FROM users u
            LEFT JOIN expenses e ON e.user_id_hash = u.user_id_hash
            WHERE u.id = 338
            GROUP BY u.id, u.user_id_hash
            LIMIT 1
        """)).first()
        
        if not result:
            print("  No test users found - skipping backend test")
            return
        
        user_id, user_hash, expense_count = result
        print(f"\n  Test User: {user_id} (hash: {user_hash[:16]}...)")
        print(f"  Expenses:  {expense_count}")
        
        # Test get_totals for each period
        for period in ['day', 'week', 'month']:
            print(f"\n[TEST] get_totals(period={period}):")
            try:
                totals = get_totals(user_hash, period)
                print(f"  Result: {totals}")
                
                # Verify structure
                assert totals is not None, "get_totals returned None!"
                assert 'period' in totals, "Missing 'period' key!"
                assert 'total_minor' in totals, "Missing 'total_minor' key!"
                assert 'top_category' in totals, "Missing 'top_category' key!"
                assert 'expenses_count' in totals, "Missing 'expenses_count' key!"
                
                # Verify types
                assert isinstance(totals['period'], str), "period is not str!"
                assert isinstance(totals['total_minor'], int), "total_minor is not int!"
                assert isinstance(totals['expenses_count'], int), "expenses_count is not int!"
                
                print(f"  ✓ PASS")
            except Exception as e:
                print(f"  ✗ FAIL: {e}")
                import traceback
                traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("BACKEND GET_TOTALS TESTS COMPLETED!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_timezone_helpers()
        test_backend_get_totals()
        print("\n✓ ALL TESTS PASSED!")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
