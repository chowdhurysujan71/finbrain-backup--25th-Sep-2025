"""
Cold-start mitigation and server warm-up functionality
Pre-warms AI providers and external services on app boot
"""
import logging
import os
import socket
import time
from datetime import datetime
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

class ColdStartMitigation:
    """Handles server warm-up and cold-start mitigation"""
    
    def __init__(self):
        self.boot_time = time.time()
        self.ai_enabled = os.environ.get('AI_ENABLED', 'false').lower() == 'true'
        self.ai_provider = os.environ.get('AI_PROVIDER', 'none')
        
        # Set provider-specific URLs and endpoints
        if self.ai_provider == 'gemini':
            self.ai_provider_url = 'https://generativelanguage.googleapis.com'
            self.ai_status_endpoint = f"{self.ai_provider_url}/v1beta/models"
        else:
            # Default to OpenAI for backwards compatibility
            self.ai_provider_url = os.environ.get('AI_PROVIDER_URL', 'https://api.openai.com')
            self.ai_status_endpoint = f"{self.ai_provider_url}/v1/models"
            
        self.warm_up_completed = False
        self.ai_warm_up_status = None
        
    def get_uptime_seconds(self) -> float:
        """Get server uptime in seconds"""
        return time.time() - self.boot_time
    
    def dns_resolve_ai_provider(self) -> bool:
        """Pre-resolve DNS for AI provider to avoid cold start delays"""
        if not self.ai_enabled:
            logger.info("AI disabled, skipping DNS resolution")
            return True
            
        try:
            # Extract hostname from URL
            from urllib.parse import urlparse
            parsed_url = urlparse(self.ai_provider_url)
            hostname = parsed_url.hostname
            
            if not hostname:
                logger.warning(f"Could not extract hostname from {self.ai_provider_url}")
                return False
            
            # Perform DNS resolution
            start_time = time.time()
            ip_address = socket.gethostbyname(hostname)
            dns_time = (time.time() - start_time) * 1000
            
            logger.info(f"DNS resolved {hostname} -> {ip_address} in {dns_time:.2f}ms")
            return True
            
        except Exception as e:
            logger.error(f"DNS resolution failed for AI provider: {str(e)}")
            return False
    
    def warm_up_ai_provider(self) -> dict[str, Any]:
        """Send warm-up request to AI provider status endpoint"""
        if not self.ai_enabled:
            return {
                "status": "disabled",
                "message": "AI processing disabled",
                "response_time_ms": 0
            }
        
        try:
            from utils.ai_adapter_v2 import production_ai_adapter as ai_adapter
            session = ai_adapter.session
            
            start_time = time.time()
            
            # Send HEAD request to status endpoint for minimal warm-up
            response = session.head(self.ai_status_endpoint, timeout=5)
            response_time_ms = (time.time() - start_time) * 1000
            
            if response.status_code in [200, 404, 405]:  # 405 = Method Not Allowed is acceptable
                logger.info(f"AI provider warm-up successful: {response.status_code} in {response_time_ms:.2f}ms")
                return {
                    "status": "warmed",
                    "status_code": response.status_code,
                    "response_time_ms": response_time_ms,
                    "endpoint": self.ai_status_endpoint
                }
            else:
                logger.warning(f"AI provider warm-up unexpected status: {response.status_code}")
                return {
                    "status": "warning",
                    "status_code": response.status_code,
                    "response_time_ms": response_time_ms,
                    "message": f"Unexpected status code: {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            logger.error("AI provider warm-up timeout (5s)")
            return {
                "status": "timeout",
                "message": "Warm-up request timed out after 5 seconds",
                "response_time_ms": 5000
            }
        except Exception as e:
            logger.error(f"AI provider warm-up failed: {str(e)}")
            return {
                "status": "error", 
                "message": str(e),
                "response_time_ms": 0
            }
    
    def run_warm_up_sequence(self) -> dict[str, Any]:
        """Execute complete server warm-up sequence"""
        logger.info("Starting cold-start mitigation warm-up sequence...")
        warm_up_start = time.time()
        
        results = {
            "started_at": datetime.utcnow().isoformat(),
            "ai_enabled": self.ai_enabled,
            "dns_resolution": False,
            "ai_warm_up": None,
            "total_time_ms": 0,
            "success": False
        }
        
        try:
            # Step 1: DNS resolution
            results["dns_resolution"] = self.dns_resolve_ai_provider()
            
            # Step 2: AI provider warm-up
            if self.ai_enabled:
                results["ai_warm_up"] = self.warm_up_ai_provider()
                self.ai_warm_up_status = results["ai_warm_up"]
            else:
                results["ai_warm_up"] = {"status": "disabled", "message": "AI processing disabled"}
                self.ai_warm_up_status = results["ai_warm_up"]
            
            # Calculate total time
            total_time_ms = (time.time() - warm_up_start) * 1000
            results["total_time_ms"] = total_time_ms
            
            # Determine overall success
            dns_ok = results["dns_resolution"]
            ai_ok = not self.ai_enabled or results["ai_warm_up"]["status"] in ["warmed", "warning", "disabled"]
            results["success"] = dns_ok and ai_ok
            
            self.warm_up_completed = True
            
            if results["success"]:
                logger.info(f"Cold-start mitigation completed successfully in {total_time_ms:.2f}ms")
            else:
                logger.warning(f"Cold-start mitigation completed with issues in {total_time_ms:.2f}ms")
                
        except Exception as e:
            logger.error(f"Cold-start mitigation failed: {str(e)}")
            results["error"] = str(e)
            results["total_time_ms"] = (time.time() - warm_up_start) * 1000
            
        return results
    
    def get_ai_status(self) -> dict[str, Any]:
        """Get current AI status for health checks"""
        if not self.ai_enabled:
            return {
                "enabled": False,
                "status": "disabled",
                "last_warm_up": None
            }
        
        return {
            "enabled": True,
            "status": self.ai_warm_up_status.get("status", "unknown") if self.ai_warm_up_status else "not_warmed",
            "last_warm_up": self.ai_warm_up_status.get("response_time_ms") if self.ai_warm_up_status else None,
            "endpoint": self.ai_provider_url
        }

# Global cold-start mitigation instance
cold_start_mitigator = ColdStartMitigation()