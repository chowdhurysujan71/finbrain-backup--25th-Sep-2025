#!/usr/bin/env python3
"""
Quick test script to validate Redis job functionality
"""
import os
import sys
import time
from datetime import datetime

# Add the current directory to the path for imports
sys.path.insert(0, '.')

def test_redis_connection():
    """Test basic Redis connection"""
    try:
        from utils.job_queue import job_queue
        
        print("🔍 Testing Redis connection...")
        if job_queue and job_queue.redis_available:
            print("✅ Redis connection: ACTIVE")
            
            # Test basic Redis operations
            test_key = f"test:finbrain:{int(time.time())}"
            job_queue.client.set(test_key, "test_value", ex=5)  # 5 second expiry
            result = job_queue.client.get(test_key)
            
            if result == b"test_value":
                print("✅ Redis read/write: SUCCESS")
                job_queue.client.delete(test_key)  # Clean up
                return True
            else:
                print(f"❌ Redis read/write: FAILED (got {result})")
                return False
        else:
            print("❌ Redis connection: NOT AVAILABLE")
            return False
            
    except Exception as e:
        print(f"❌ Redis connection error: {e}")
        return False

def test_goal_analysis_job():
    """Test goal analysis job enqueue/processing"""
    try:
        from utils.goal_automation import schedule_goal_analysis_for_user
        
        print("\n🧪 Testing goal analysis job...")
        
        # Use a test user ID
        test_user_id = "test_user_hash_" + str(int(time.time()))
        
        # Schedule a goal analysis job
        success = schedule_goal_analysis_for_user(test_user_id)
        
        if success:
            print("✅ Goal analysis job scheduling: SUCCESS")
            return True
        else:
            print("❌ Goal analysis job scheduling: FAILED")
            return False
            
    except Exception as e:
        print(f"❌ Goal analysis job error: {e}")
        return False

def test_job_queue_status():
    """Check job queue status"""
    try:
        from utils.job_queue import job_queue
        
        print("\n📊 Job queue status:")
        if job_queue:
            status = {
                'redis_available': job_queue.redis_available,
                'connection_pool': str(job_queue.client.connection_pool) if job_queue.redis_available else 'N/A',
                'queue_size': len(job_queue.client.lrange("job_queue", 0, -1)) if job_queue.redis_available else 0
            }
            
            for key, value in status.items():
                print(f"  {key}: {value}")
            
            return True
        else:
            print("  Job queue not initialized")
            return False
            
    except Exception as e:
        print(f"❌ Job queue status error: {e}")
        return False

def test_smart_banners():
    """Test smart banner service"""
    try:
        from utils.smart_banners import smart_banner_service
        
        print("\n💡 Testing smart banner service...")
        
        test_user_id = "test_user_hash_" + str(int(time.time()))
        
        # Test goal-aware banner retrieval
        banners = smart_banner_service.get_goal_aware_banners(test_user_id, limit=3)
        
        print(f"✅ Smart banners retrieved: {len(banners)} banners")
        for banner in banners:
            if isinstance(banner, dict):
                print(f"  - {banner.get('banner_type', 'unknown')}: {banner.get('title', 'No title')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Smart banner service error: {e}")
        return False

def main():
    print("🚀 finbrain Redis Jobs & Goal Automation Test Suite")
    print("=" * 60)
    
    tests = [
        test_redis_connection,
        test_goal_analysis_job,
        test_job_queue_status,
        test_smart_banners
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test_func.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"📈 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Redis jobs and goal automation are working!")
        return 0
    else:
        print(f"⚠️  {total - passed} tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    exit(main())