"""
External health ping system to keep server warm
Implements 5-minute health check pings to prevent cold starts
"""
import os
import time
import logging
import requests
import threading
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class HealthPinger:
    """Manages external health pings to keep server warm"""
    
    def __init__(self):
        self.enabled = os.environ.get('HEALTH_PING_ENABLED', 'true').lower() == 'true'
        self.interval_seconds = 300  # 5 minutes
        self.health_url = os.environ.get('HEALTH_PING_URL', 'http://localhost:5000/health')
        self.ping_thread = None
        self.running = False
        self.last_ping_time = None
        self.last_ping_status = None
        
    def start_health_pings(self):
        """Start background health ping thread"""
        if not self.enabled:
            logger.info("Health pings disabled via HEALTH_PING_ENABLED=false")
            return
            
        if self.running:
            logger.warning("Health pings already running")
            return
            
        self.running = True
        self.ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
        self.ping_thread.start()
        logger.info(f"Health ping system started: {self.health_url} every {self.interval_seconds}s")
    
    def stop_health_pings(self):
        """Stop background health ping thread"""
        self.running = False
        if self.ping_thread:
            self.ping_thread.join(timeout=5)
        logger.info("Health ping system stopped")
    
    def _ping_loop(self):
        """Background thread loop for health pings"""
        while self.running:
            try:
                # Wait for initial warm-up before starting pings
                time.sleep(30)  # 30 second initial delay
                
                while self.running:
                    self._perform_health_ping()
                    time.sleep(self.interval_seconds)
                    
            except Exception as e:
                logger.error(f"Health ping loop error: {str(e)}")
                if self.running:
                    time.sleep(60)  # Wait 1 minute before retrying
    
    def _perform_health_ping(self):
        """Perform single health ping"""
        try:
            start_time = time.time()
            
            response = requests.get(
                self.health_url,
                timeout=10,
                headers={'User-Agent': 'FinBrain-HealthPing/1.0'}
            )
            
            response_time_ms = (time.time() - start_time) * 1000
            self.last_ping_time = datetime.utcnow()
            
            if response.status_code == 200:
                self.last_ping_status = "success"
                logger.debug(f"Health ping successful: {response.status_code} in {response_time_ms:.2f}ms")
            else:
                self.last_ping_status = f"error_{response.status_code}"
                logger.warning(f"Health ping unexpected status: {response.status_code}")
                
        except requests.exceptions.Timeout:
            self.last_ping_status = "timeout"
            logger.warning("Health ping timeout (10s)")
        except Exception as e:
            self.last_ping_status = f"error_{str(e)[:20]}"
            logger.error(f"Health ping failed: {str(e)}")
    
    def get_ping_status(self) -> dict:
        """Get current health ping status"""
        return {
            "enabled": self.enabled,
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            "health_url": self.health_url,
            "last_ping_time": self.last_ping_time.isoformat() if self.last_ping_time else None,
            "last_ping_status": self.last_ping_status
        }

# Global health pinger instance
health_pinger = HealthPinger()