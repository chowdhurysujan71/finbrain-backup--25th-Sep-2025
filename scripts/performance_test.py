#!/usr/bin/env python3
"""
Performance Baseline Test for FinBrain 
Measures P50, P90, P95, P99 for webhook processing
"""
import json
import time
import statistics
import requests
from concurrent.futures import ThreadPoolExecutor
import sys

BASE_URL = "http://localhost:5000"

def create_test_payload(message_text, mid_suffix=""):
    """Create a test webhook payload"""
    return {
        "object": "page",
        "entry": [{
            "id": "perf_test_page",
            "time": int(time.time() * 1000),
            "messaging": [{
                "sender": {"id": f"perf_user_{int(time.time())}_{mid_suffix}"},
                "recipient": {"id": "perf_test_page"},
                "timestamp": int(time.time() * 1000),
                "message": {
                    "mid": f"perf_test_{int(time.time())}_{mid_suffix}",
                    "text": message_text
                }
            }]
        }]
    }

def send_webhook_request(payload):
    """Send a single webhook request and measure timing"""
    start_time = time.time()
    try:
        response = requests.post(
            f"{BASE_URL}/webhook",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Local-Testing": "true"
            },
            timeout=10
        )
        end_time = time.time()
        
        return {
            "success": True,
            "latency_ms": (end_time - start_time) * 1000,
            "status_code": response.status_code,
            "response_size": len(response.text) if response.text else 0
        }
    except Exception as e:
        end_time = time.time()
        return {
            "success": False,
            "latency_ms": (end_time - start_time) * 1000,
            "error": str(e),
            "status_code": 0,
            "response_size": 0
        }

def run_performance_test(test_name, message_text, num_requests=20):
    """Run performance test with specified parameters"""
    print(f"Running {test_name} with {num_requests} requests...")
    
    results = []
    payloads = [create_test_payload(message_text, str(i)) for i in range(num_requests)]
    
    # Sequential requests to avoid overwhelming the server
    for i, payload in enumerate(payloads):
        result = send_webhook_request(payload)
        results.append(result)
        if i % 5 == 0:
            print(f"  Progress: {i+1}/{num_requests}")
        time.sleep(0.1)  # Small delay between requests
    
    # Calculate statistics
    successful_results = [r for r in results if r['success']]
    latencies = [r['latency_ms'] for r in successful_results]
    
    if latencies:
        stats = {
            "total_requests": num_requests,
            "successful_requests": len(successful_results),
            "failed_requests": num_requests - len(successful_results),
            "success_rate": len(successful_results) / num_requests * 100,
            "latency_stats": {
                "p50": statistics.median(latencies),
                "p90": statistics.quantiles(latencies, n=10)[8] if len(latencies) >= 10 else max(latencies),
                "p95": statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies),
                "p99": statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies),
                "min": min(latencies),
                "max": max(latencies),
                "avg": statistics.mean(latencies)
            },
            "raw_latencies": latencies
        }
    else:
        stats = {
            "total_requests": num_requests,
            "successful_requests": 0,
            "failed_requests": num_requests,
            "success_rate": 0,
            "latency_stats": None,
            "raw_latencies": []
        }
    
    return stats

if __name__ == "__main__":
    print("=== FINBRAIN PERFORMANCE BASELINE TEST ===")
    print(f"Target: {BASE_URL}")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test scenarios
    test_scenarios = [
        {
            "name": "fixed_input_simple",
            "message": "coffee 150 taka",
            "requests": 15
        },
        {
            "name": "fixed_input_complex", 
            "message": "lunch 200 and uber 100 and shopping 1500 taka",
            "requests": 15
        },
        {
            "name": "varied_inputs",
            "messages": [
                "breakfast 100 taka",
                "bus fare 25",
                "lunch meeting 500 taka", 
                "coffee and snacks 200",
                "dinner 800 taka",
                "uber ride home 150",
                "grocery shopping 1200 taka",
                "medicine 300",
                "book 250 taka",
                "movie ticket 400"
            ],
            "requests": 10
        }
    ]
    
    all_results = {}
    
    # Run fixed input tests
    for scenario in test_scenarios[:2]:
        all_results[scenario['name']] = run_performance_test(
            scenario['name'], 
            scenario['message'], 
            scenario['requests']
        )
    
    # Run varied input test
    print("Running varied_inputs test...")
    varied_results = []
    for i, message in enumerate(test_scenarios[2]['messages']):
        payload = create_test_payload(message, f"varied_{i}")
        result = send_webhook_request(payload)
        varied_results.append(result)
        time.sleep(0.1)
    
    # Process varied results
    successful_varied = [r for r in varied_results if r['success']]
    varied_latencies = [r['latency_ms'] for r in successful_varied]
    
    if varied_latencies:
        all_results['varied_inputs'] = {
            "total_requests": len(test_scenarios[2]['messages']),
            "successful_requests": len(successful_varied),
            "failed_requests": len(varied_results) - len(successful_varied),
            "success_rate": len(successful_varied) / len(varied_results) * 100,
            "latency_stats": {
                "p50": statistics.median(varied_latencies),
                "p90": statistics.quantiles(varied_latencies, n=10)[8] if len(varied_latencies) >= 10 else max(varied_latencies),
                "p95": max(varied_latencies),  # With small sample, use max
                "p99": max(varied_latencies),
                "min": min(varied_latencies),
                "max": max(varied_latencies),
                "avg": statistics.mean(varied_latencies)
            },
            "raw_latencies": varied_latencies
        }
    
    # Output results
    print("\n=== PERFORMANCE TEST RESULTS ===")
    print(json.dumps(all_results, indent=2))