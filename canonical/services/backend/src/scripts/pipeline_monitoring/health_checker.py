"""
Component Health Checker

Implements periodic health checks for all pipeline components.
Addresses GAP-002: No Periodic Health Checks
"""

import time
import asyncio
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum


class ComponentHealth(Enum):
    """Component health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    component: str
    status: ComponentHealth
    latency_ms: float
    details: Dict[str, Any]
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "component": self.component,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "details": self.details,
            "timestamp": self.timestamp
        }


class HealthChecker:
    """Periodic health checker for pipeline components"""
    
    def __init__(self, interval_seconds: int = 30):
        """
        Initialize health checker
        
        Args:
            interval_seconds: Interval between health checks (default: 30s)
        """
        self.interval_seconds = interval_seconds
        self.components = [
            "frontend",
            "extension",
            "wasm_orchestrator",
            "backend_api",
            "mongodb",
            "redis",
            "llm_provider"
        ]
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._results_history: List[List[HealthCheckResult]] = []
        self._alert_callbacks: List[Callable] = []
    
    def register_alert_callback(self, callback: Callable):
        """
        Register a callback to be called when alerts are triggered
        
        Args:
            callback: Async function to call with alert data
        """
        self._alert_callbacks.append(callback)
    
    async def start_monitoring(self):
        """Start periodic health checks"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
    
    async def stop_monitoring(self):
        """Stop periodic health checks"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                results = await self.check_all_components()
                self._results_history.append(results)
                
                # Keep only last 100 checks
                if len(self._results_history) > 100:
                    self._results_history.pop(0)
                
                await self._process_results(results)
                
                # Publish health update event for WebSocket streaming
                try:
                    from app.services.monitoring_event_publisher import get_monitoring_publisher
                    publisher = await get_monitoring_publisher()
                    await publisher.publish_health_update(results)
                except Exception as e:
                    # Log but don't fail monitoring if event publishing fails
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to publish health update event: {e}")
            
            except Exception as e:
                print(f"Health check error: {e}")
            
            await asyncio.sleep(self.interval_seconds)
    
    async def check_all_components(self) -> List[HealthCheckResult]:
        """
        Check health of all components in parallel
        
        Returns:
            List of HealthCheckResult for all components
        """
        tasks = [
            self._check_component(component)
            for component in self.components
        ]
        return await asyncio.gather(*tasks)
    
    async def check_component(self, component: str) -> HealthCheckResult:
        """
        Check health of a specific component
        
        Args:
            component: Component name to check
            
        Returns:
            HealthCheckResult for the component
        """
        return await self._check_component(component)
    
    async def _check_component(self, component: str) -> HealthCheckResult:
        """Check health of a single component"""
        start_time = time.time()
        
        try:
            # Component-specific health check
            if component == "frontend":
                status, details = await self._check_frontend_health()
            elif component == "extension":
                status, details = await self._check_extension_health()
            elif component == "wasm_orchestrator":
                status, details = await self._check_wasm_health()
            elif component == "backend_api":
                status, details = await self._check_backend_health()
            elif component == "mongodb":
                status, details = await self._check_mongodb_health()
            elif component == "redis":
                status, details = await self._check_redis_health()
            elif component == "llm_provider":
                status, details = await self._check_llm_health()
            else:
                status = ComponentHealth.UNKNOWN
                details = {"error": "Unknown component"}
            
            latency_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                component=component,
                status=status,
                latency_ms=latency_ms,
                details=details,
                timestamp=time.time()
            )
        except Exception as e:
            return HealthCheckResult(
                component=component,
                status=ComponentHealth.UNHEALTHY,
                latency_ms=(time.time() - start_time) * 1000,
                details={"error": str(e)},
                timestamp=time.time()
            )
    
    async def _process_results(self, results: List[HealthCheckResult]):
        """Process health check results and trigger alerts if needed"""
        unhealthy = [r for r in results if r.status == ComponentHealth.UNHEALTHY]
        degraded = [r for r in results if r.status == ComponentHealth.DEGRADED]
        
        if unhealthy:
            await self._trigger_alert("critical", unhealthy)
        elif degraded:
            await self._trigger_alert("warning", degraded)
    
    async def _trigger_alert(self, severity: str, results: List[HealthCheckResult]):
        """Trigger alert for unhealthy components"""
        alert_data = {
            "severity": severity,
            "timestamp": time.time(),
            "components": [r.to_dict() for r in results]
        }
        
        # Call registered callbacks
        for callback in self._alert_callbacks:
            try:
                await callback(alert_data)
            except Exception as e:
                print(f"Alert callback error: {e}")
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get summary of current health status
        
        Returns:
            Dictionary with health summary
        """
        if not self._results_history:
            return {
                "status": "no_data",
                "components": {},
                "last_check": None
            }
        
        latest = self._results_history[-1]
        
        # Count status by type
        status_counts = {
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "unknown": 0
        }
        
        component_status = {}
        for result in latest:
            status_counts[result.status.value] += 1
            component_status[result.component] = {
                "status": result.status.value,
                "latency_ms": result.latency_ms,
                "details": result.details
            }
        
        # Overall status
        if status_counts["unhealthy"] > 0:
            overall_status = "unhealthy"
        elif status_counts["degraded"] > 0:
            overall_status = "degraded"
        elif status_counts["healthy"] == len(self.components):
            overall_status = "healthy"
        else:
            overall_status = "unknown"
        
        return {
            "status": overall_status,
            "components": component_status,
            "last_check": latest[0].timestamp if latest else None,
            "status_counts": status_counts
        }
    
    # Health check methods for each component
    async def _check_frontend_health(self) -> Tuple[ComponentHealth, Dict[str, Any]]:
        """Check frontend health"""
        # Frontend is client-side, can't check directly from backend
        return ComponentHealth.UNKNOWN, {
            "message": "Frontend health requires client-side check"
        }
    
    async def _check_extension_health(self) -> Tuple[ComponentHealth, Dict[str, Any]]:
        """Check browser extension health"""
        # Extension is client-side, can't check directly from backend
        return ComponentHealth.UNKNOWN, {
            "message": "Extension health requires client-side check"
        }
    
    async def _check_wasm_health(self) -> Tuple[ComponentHealth, Dict[str, Any]]:
        """Check WASM orchestrator health"""
        # WASM orchestrator is client-side, can't check directly from backend
        return ComponentHealth.UNKNOWN, {
            "message": "WASM orchestrator health requires client-side check"
        }
    
    async def _check_backend_health(self) -> Tuple[ComponentHealth, Dict[str, Any]]:
        """Check backend API health"""
        try:
            # Check if we can import key services
            from app.services.cell_generation_service import CellGenerationService
            from app.openai_service import OpenAIService
            
            return ComponentHealth.HEALTHY, {
                "services_available": ["CellGenerationService", "OpenAIService"]
            }
        except ImportError as e:
            return ComponentHealth.UNHEALTHY, {
                "error": f"Failed to import backend services: {str(e)}"
            }
    
    async def _check_mongodb_health(self) -> Tuple[ComponentHealth, Dict[str, Any]]:
        """Check MongoDB health"""
        try:
            from app.database import get_database
            db = await get_database()
            
            # Ping MongoDB
            start = time.time()
            await db.command("ping")
            ping_latency_ms = (time.time() - start) * 1000
            
            # Get server status
            status = await db.command("serverStatus")
            connections = status.get("connections", {})
            
            # Check if we're approaching connection limits
            current = connections.get("current", 0)
            available = connections.get("available", 0)
            total = current + available
            
            if total > 0:
                usage_percent = (current / total) * 100
                if usage_percent > 90:
                    health_status = ComponentHealth.DEGRADED
                else:
                    health_status = ComponentHealth.HEALTHY
            else:
                health_status = ComponentHealth.HEALTHY
            
            return health_status, {
                "connected": True,
                "ping_latency_ms": ping_latency_ms,
                "connections": {
                    "current": current,
                    "available": available,
                    "usage_percent": usage_percent if total > 0 else 0
                }
            }
        except Exception as e:
            return ComponentHealth.UNHEALTHY, {
                "connected": False,
                "error": str(e)
            }
    
    async def _check_redis_health(self) -> Tuple[ComponentHealth, Dict[str, Any]]:
        """Check Redis health"""
        try:
            from app.services.redis_service import redis_service
            
            # Ping Redis
            start = time.time()
            await redis_service.ping()
            ping_latency_ms = (time.time() - start) * 1000
            
            # Get Redis info
            info = await redis_service.get_info()
            memory_info = info.get("memory", {})
            
            # Check memory usage
            used_memory = memory_info.get("used_memory", 0)
            maxmemory = memory_info.get("maxmemory", 0)
            
            if maxmemory > 0:
                memory_usage_percent = (used_memory / maxmemory) * 100
                if memory_usage_percent > 90:
                    health_status = ComponentHealth.DEGRADED
                else:
                    health_status = ComponentHealth.HEALTHY
            else:
                health_status = ComponentHealth.HEALTHY
            
            return health_status, {
                "connected": True,
                "ping_latency_ms": ping_latency_ms,
                "memory": {
                    "used_mb": used_memory / (1024 * 1024),
                    "max_mb": maxmemory / (1024 * 1024) if maxmemory > 0 else None,
                    "usage_percent": memory_usage_percent if maxmemory > 0 else None
                }
            }
        except Exception as e:
            return ComponentHealth.UNHEALTHY, {
                "connected": False,
                "error": str(e)
            }
    
    async def _check_llm_health(self) -> Tuple[ComponentHealth, Dict[str, Any]]:
        """Check LLM provider health"""
        try:
            from app.openai_service import OpenAIService
            
            # Check if we can instantiate the service
            # Note: This doesn't make an actual API call
            service = OpenAIService()
            
            return ComponentHealth.HEALTHY, {
                "available": True,
                "provider": "OpenAI"
            }
        except Exception as e:
            return ComponentHealth.UNHEALTHY, {
                "available": False,
                "error": str(e)
            }
