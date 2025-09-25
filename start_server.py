#!/usr/bin/env python3
"""
FinBrain production server startup script
Starts gunicorn without the --reload flag to prevent WINCH signal loops
"""
import os
import signal
import subprocess
import sys


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print(f"\nReceived signal {sig}, shutting down gracefully...")
    sys.exit(0)

def start_production_server():
    """Start gunicorn server in production mode"""
    # Handle shutdown signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Gunicorn command with production-ready worker configuration
    workers = os.environ.get('WEB_CONCURRENCY', '4')  # Default to 4 workers for MVP capacity
    cmd = [
        "gunicorn",
        "--bind", "0.0.0.0:5000",
        "--reuse-port",
        "--workers", workers,  # Use WEB_CONCURRENCY environment variable
        "--worker-class", "sync",  # Sync workers for stability
        "--timeout", "30",  # Production timeout (30s)
        "--keep-alive", "2",  # Keep connections alive  
        "--log-level", "info",
        "main:app"
    ]
    
    print("Starting FinBrain production server...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        # Start gunicorn process
        process = subprocess.run(cmd, check=False)
        return process.returncode
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        return 0
    except Exception as e:
        print(f"Error starting server: {e}")
        return 1

if __name__ == "__main__":
    exit_code = start_production_server()
    sys.exit(exit_code)