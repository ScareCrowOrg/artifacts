"""
Pipeline Prerequisite Validator - Backend Scope Only

Validates 10 backend-validatable prerequisites:
- Backend (5): Generation Service, Complexity, LLM, Discovery, Event Bus
- Infrastructure (2): MongoDB, Redis
- Config (2): Environment vars, Feature flags
- Runtime (1): System resources (CPU/memory, server-side only)

Note: Frontend/Extension/WASM checks (14 prerequisites) are validated 
client-side via useFrontendHealthChecks composable, following local-first 
architecture principles (see LOCAL_FIRST_UNCLASSIFIED_CELL_ARCHITECTURE.md).

Total system prerequisites: 24 (10 backend + 14 frontend)
"""

import time
import asyncio
from typing import Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum


class PrerequisiteStatus(Enum):
    """Status of a prerequisite check"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class Criticality(Enum):
    """
    Criticality level for prerequisites.
    
    Backend-only distribution:
    - CRITICAL: 4 (cell_generation_service, llm_integration, mongodb, environment_vars)
    - HIGH: 2 (event_bus, redis)
    - MEDIUM: 3 (complexity_evaluation, discovery_system, system_resources)
    - LOW: 1 (feature_flags)
    
    Note: Original total distribution across all 24 prerequisites was:
    CRITICAL: 12, HIGH: 8, MEDIUM: 4, LOW: 1
    """
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class PrerequisiteResult:
    """Result of a prerequisite validation"""
    id: str
    name: str
    category: str
    status: PrerequisiteStatus
    criticality: Criticality
    validation_method: str
    monitoring_available: bool
    details: Dict[str, Any]
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "status": self.status.value,
            "criticality": self.criticality.value,
            "validation_method": self.validation_method,
            "monitoring_available": self.monitoring_available,
            "details": self.details,
            "timestamp": self.timestamp
        }


class PipelineValidator:
    """
    Validates backend-side pipeline prerequisites only.
    
    Frontend/Extension/WASM prerequisites are validated client-side
    via useFrontendHealthChecks composable (see cockpit-vue/src/composables/).
    """
    
    def __init__(self):
        self.prerequisites = self._define_prerequisites()
    
    def _define_prerequisites(self) -> List[Dict[str, Any]]:
        """
        Define 10 backend-validatable prerequisites.
        
        Categories:
        - Backend (5): Services that can be checked via imports/connections
        - Infrastructure (2): Database connections (MongoDB, Redis)
        - Configuration (2): Environment variables and feature flags
        - Runtime (1): Server-side system resources (CPU, memory, disk)
        
        Note: Frontend (3), Extension (5), WASM (4), and browser Runtime (2)
        checks are handled client-side for a total of 24 system prerequisites.
        """
        return [
            # Backend (5)
            {
                "id": "backend.cell_generation_service",
                "name": "Cell Generation Service",
                "category": "backend",
                "criticality": Criticality.CRITICAL,
                "validator": self._check_cell_generation_service
            },
            {
                "id": "backend.complexity_evaluation",
                "name": "Complexity Evaluation",
                "category": "backend",
                "criticality": Criticality.MEDIUM,
                "validator": self._check_complexity_evaluation
            },
            {
                "id": "backend.llm_integration",
                "name": "LLM Integration",
                "category": "backend",
                "criticality": Criticality.CRITICAL,
                "validator": self._check_llm_integration
            },
            {
                "id": "backend.discovery_system",
                "name": "Discovery System",
                "category": "backend",
                "criticality": Criticality.MEDIUM,
                "validator": self._check_discovery_system
            },
            {
                "id": "backend.event_bus",
                "name": "Event Bus (Redis Pub/Sub)",
                "category": "backend",
                "criticality": Criticality.HIGH,
                "validator": self._check_event_bus
            },
            
            # Infrastructure (2)
            {
                "id": "infra.mongodb",
                "name": "MongoDB Available",
                "category": "infrastructure",
                "criticality": Criticality.CRITICAL,
                "validator": self._check_mongodb
            },
            {
                "id": "infra.redis",
                "name": "Redis Connected",
                "category": "infrastructure",
                "criticality": Criticality.HIGH,
                "validator": self._check_redis
            },
            
            # Configuration (2)
            {
                "id": "config.environment_vars",
                "name": "Environment Variables",
                "category": "configuration",
                "criticality": Criticality.CRITICAL,
                "validator": self._check_environment_vars
            },
            {
                "id": "config.feature_flags",
                "name": "Feature Flags",
                "category": "configuration",
                "criticality": Criticality.LOW,
                "validator": self._check_feature_flags
            },
            
            # Runtime (1) - Server-side only
            {
                "id": "runtime.system_resources",
                "name": "System Resources (Server)",
                "category": "runtime",
                "criticality": Criticality.MEDIUM,
                "validator": self._check_system_resources
            }
        ]
    
    async def validate_all(self) -> List[PrerequisiteResult]:
        """
        Validate all backend prerequisites in parallel.
        
        Returns:
            List of PrerequisiteResult for all 10 backend prerequisites
        """
        tasks = [
            self._validate_prerequisite(prereq)
            for prereq in self.prerequisites
        ]
        return await asyncio.gather(*tasks)
    
    async def validate_by_category(self, category: str) -> List[PrerequisiteResult]:
        """
        Validate prerequisites for a specific category
        
        Args:
            category: Category to validate (frontend, extension, wasm, backend, infrastructure, configuration, runtime)
            
        Returns:
            List of PrerequisiteResult for the category
        """
        filtered = [p for p in self.prerequisites if p["category"] == category]
        tasks = [self._validate_prerequisite(prereq) for prereq in filtered]
        return await asyncio.gather(*tasks)
    
    async def validate_critical_only(self) -> List[PrerequisiteResult]:
        """
        Validate only critical prerequisites
        
        Returns:
            List of PrerequisiteResult for critical prerequisites
        """
        filtered = [p for p in self.prerequisites if p["criticality"] == Criticality.CRITICAL]
        tasks = [self._validate_prerequisite(prereq) for prereq in filtered]
        return await asyncio.gather(*tasks)
    
    async def _validate_prerequisite(self, prereq: Dict[str, Any]) -> PrerequisiteResult:
        """Validate a single prerequisite"""
        try:
            validator = prereq["validator"]
            result = await validator()
            
            return PrerequisiteResult(
                id=prereq["id"],
                name=prereq["name"],
                category=prereq["category"],
                status=result["status"],
                criticality=prereq["criticality"],
                validation_method=result.get("method", "unknown"),
                monitoring_available=result.get("monitoring", False),
                details=result.get("details", {}),
                timestamp=time.time()
            )
        except Exception as e:
            return PrerequisiteResult(
                id=prereq["id"],
                name=prereq["name"],
                category=prereq["category"],
                status=PrerequisiteStatus.UNKNOWN,
                criticality=prereq["criticality"],
                validation_method="error",
                monitoring_available=False,
                details={"error": str(e)},
                timestamp=time.time()
            )
    
    # Backend validators
    async def _check_cell_generation_service(self) -> Dict[str, Any]:
        """Check if cell generation service is available"""
        try:
            # Check if service is importable and initialized
            from app.services.cell_generation_service import CellGenerationService
            return {
                "status": PrerequisiteStatus.HEALTHY,
                "method": "import_check",
                "monitoring": True,
                "details": {"available": True, "service": "CellGenerationService"}
            }
        except ImportError as e:
            return {
                "status": PrerequisiteStatus.UNHEALTHY,
                "method": "import_check",
                "monitoring": False,
                "details": {"available": False, "error": str(e)}
            }
    
    async def _check_complexity_evaluation(self) -> Dict[str, Any]:
        """Check complexity evaluation functionality"""
        try:
            from app.services.cell_generation_service import CellGenerationService
            # Check if method exists
            if not hasattr(CellGenerationService, '_evaluate_complexity'):
                return {
                    "status": PrerequisiteStatus.UNHEALTHY,
                    "method": "method_check",
                    "monitoring": True,
                    "details": {
                        "available": False,
                        "message": "Method _evaluate_complexity not found in CellGenerationService",
                        "issue": "Implementation missing or method renamed"
                    }
                }
            
            # Try to instantiate and test (if possible without dependencies)
            try:
                # This is a deeper check - would need actual testing with mock data
                return {
                    "status": PrerequisiteStatus.DEGRADED,
                    "method": "method_check",
                    "monitoring": True,
                    "details": {
                        "available": True,
                        "message": "Method exists but functional test not implemented",
                        "warning": "Cannot verify actual complexity evaluation without test data"
                    }
                }
            except Exception as test_error:
                return {
                    "status": PrerequisiteStatus.DEGRADED,
                    "method": "method_check",
                    "monitoring": True,
                    "details": {
                        "available": True,
                        "message": "Method exists but instantiation failed",
                        "test_error": str(test_error)
                    }
                }
        except ImportError as e:
            return {
                "status": PrerequisiteStatus.UNHEALTHY,
                "method": "import_check",
                "monitoring": False,
                "details": {
                    "available": False,
                    "error": str(e),
                    "issue": "CellGenerationService cannot be imported"
                }
            }
        except Exception as e:
            return {
                "status": PrerequisiteStatus.UNKNOWN,
                "method": "method_check",
                "monitoring": False,
                "details": {"error": str(e)}
            }
    
    async def _check_llm_integration(self) -> Dict[str, Any]:
        """Check LLM integration functionality"""
        try:
            from app.openai_service import OpenAIService
            import os
            
            # Check if API key is configured
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return {
                    "status": PrerequisiteStatus.UNHEALTHY,
                    "method": "config_check",
                    "monitoring": True,
                    "details": {
                        "available": True,
                        "configured": False,
                        "issue": "OPENAI_API_KEY environment variable not set"
                    }
                }
            
            # Service is importable and key is configured
            return {
                "status": PrerequisiteStatus.DEGRADED,
                "method": "import_and_config_check",
                "monitoring": True,
                "details": {
                    "available": True,
                    "configured": True,
                    "service": "OpenAIService",
                    "warning": "API key configured but actual connectivity not tested (would incur costs)"
                }
            }
        except ImportError as e:
            return {
                "status": PrerequisiteStatus.UNHEALTHY,
                "method": "import_check",
                "monitoring": False,
                "details": {
                    "available": False,
                    "error": str(e),
                    "issue": "OpenAIService cannot be imported"
                }
            }
    
    async def _check_discovery_system(self) -> Dict[str, Any]:
        """Check discovery system operational status"""
        try:
            # First check if file exists
            import os
            from app.config import BASE_DIR
            discovery_path = os.path.join(BASE_DIR, "app", "services", "action_discovery.py")
            
            if not os.path.exists(discovery_path):
                return {
                    "status": PrerequisiteStatus.UNHEALTHY,
                    "method": "file_check",
                    "monitoring": False,
                    "details": {
                        "available": False,
                        "message": "Discovery service file not found",
                        "expected_path": discovery_path
                    }
                }
            
            # Try to import and check for key functionality
            try:
                from app.services.action_discovery import ActionDiscoveryService
                
                # Check if service can be instantiated (light check)
                return {
                    "status": PrerequisiteStatus.DEGRADED,
                    "method": "import_and_file_check",
                    "monitoring": True,
                    "details": {
                        "available": True,
                        "file_exists": True,
                        "warning": "Service importable but LAD validation rules not tested"
                    }
                }
            except ImportError as import_error:
                return {
                    "status": PrerequisiteStatus.DEGRADED,
                    "method": "import_check",
                    "monitoring": False,
                    "details": {
                        "available": False,
                        "file_exists": True,
                        "import_error": str(import_error),
                        "message": "File exists but service cannot be imported"
                    }
                }
        except Exception as e:
            return {
                "status": PrerequisiteStatus.UNKNOWN,
                "method": "file_check",
                "monitoring": False,
                "details": {"error": str(e)}
            }
    
    async def _check_event_bus(self) -> Dict[str, Any]:
        """Check Redis pub/sub event bus connectivity"""
        try:
            from app.services.redis_pubsub_service import RedisPubSubService
            
            # Try to test actual connection
            try:
                from app.services.redis_service import redis_service
                # Test if we can ping Redis
                await redis_service.ping()
                return {
                    "status": PrerequisiteStatus.HEALTHY,
                    "method": "connection_test",
                    "monitoring": True,
                    "details": {
                        "available": True,
                        "service": "RedisPubSubService",
                        "connected": True
                    }
                }
            except Exception as conn_error:
                return {
                    "status": PrerequisiteStatus.DEGRADED,
                    "method": "import_check",
                    "monitoring": True,
                    "details": {
                        "available": True,
                        "service": "RedisPubSubService",
                        "connected": False,
                        "connection_error": str(conn_error),
                        "message": "Service importable but Redis connection failed"
                    }
                }
        except ImportError as e:
            return {
                "status": PrerequisiteStatus.UNHEALTHY,
                "method": "import_check",
                "monitoring": False,
                "details": {
                    "available": False,
                    "error": str(e),
                    "issue": "RedisPubSubService cannot be imported"
                }
            }
    
    # Infrastructure validators
    async def _check_mongodb(self) -> Dict[str, Any]:
        """Check MongoDB availability"""
        try:
            from app.database import get_database
            db = await get_database()
            # Try to ping MongoDB
            await db.command("ping")
            return {
                "status": PrerequisiteStatus.HEALTHY,
                "method": "ping",
                "monitoring": True,
                "details": {"available": True, "connected": True}
            }
        except Exception as e:
            return {
                "status": PrerequisiteStatus.UNHEALTHY,
                "method": "ping",
                "monitoring": True,
                "details": {"available": False, "error": str(e)}
            }
    
    async def _check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity"""
        try:
            from app.services.redis_service import redis_service
            # Try to ping Redis
            await redis_service.ping()
            return {
                "status": PrerequisiteStatus.HEALTHY,
                "method": "ping",
                "monitoring": True,
                "details": {"available": True, "connected": True}
            }
        except Exception as e:
            return {
                "status": PrerequisiteStatus.UNHEALTHY,
                "method": "ping",
                "monitoring": True,
                "details": {"available": False, "error": str(e)}
            }
    
    # Configuration validators
    async def _check_environment_vars(self) -> Dict[str, Any]:
        """Check environment variables configuration"""
        import os
        required_vars = [
            "MONGODB_URI",
            "REDIS_URL",
            "JWT_SECRET"
        ]
        optional_vars = [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY"
        ]
        
        missing_required = [var for var in required_vars if not os.getenv(var)]
        missing_optional = [var for var in optional_vars if not os.getenv(var)]
        
        if missing_required:
            return {
                "status": PrerequisiteStatus.UNHEALTHY,
                "method": "env_check",
                "monitoring": True,
                "details": {
                    "configured": False,
                    "missing_required_vars": missing_required,
                    "missing_optional_vars": missing_optional,
                    "issue": f"Missing critical environment variables: {', '.join(missing_required)}"
                }
            }
        
        if missing_optional:
            return {
                "status": PrerequisiteStatus.DEGRADED,
                "method": "env_check",
                "monitoring": True,
                "details": {
                    "configured": True,
                    "required_vars_ok": True,
                    "missing_optional_vars": missing_optional,
                    "warning": f"Optional vars not set: {', '.join(missing_optional)}"
                }
            }
        
        return {
            "status": PrerequisiteStatus.HEALTHY,
            "method": "env_check",
            "monitoring": True,
            "details": {
                "configured": True,
                "required_vars": required_vars,
                "optional_vars": optional_vars,
                "all_configured": True
            }
        }
    
    async def _check_feature_flags(self) -> Dict[str, Any]:
        """Check feature flags configuration"""
        try:
            from app.config import config
            flags = {
                "use_real_llm": getattr(config, "use_real_llm", None),
                "enable_hypnosis_loop": getattr(config, "enable_hypnosis_loop", None),
            }
            return {
                "status": PrerequisiteStatus.HEALTHY,
                "method": "config_check",
                "monitoring": True,
                "details": {"flags": flags}
            }
        except Exception as e:
            return {
                "status": PrerequisiteStatus.DEGRADED,
                "method": "config_check",
                "monitoring": False,
                "details": {"error": str(e)}
            }
    
    # Runtime validators (server-side only)
    async def _check_system_resources(self) -> Dict[str, Any]:
        """Check server-side system resources (CPU, memory, disk)"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Check if we have at least 50MB free memory
            memory_ok = memory.available > 50 * 1024 * 1024
            # Check if we have at least 1GB free disk
            disk_ok = disk.free > 1 * 1024 * 1024 * 1024
            
            if memory_ok and disk_ok:
                status = PrerequisiteStatus.HEALTHY
            elif memory_ok or disk_ok:
                status = PrerequisiteStatus.DEGRADED
            else:
                status = PrerequisiteStatus.UNHEALTHY
            
            return {
                "status": status,
                "method": "psutil",
                "monitoring": True,
                "details": {
                    "memory_available_mb": round(memory.available / (1024 * 1024), 2),
                    "memory_percent_used": memory.percent,
                    "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
                    "disk_percent_used": disk.percent
                }
            }
        except Exception as e:
            return {
                "status": PrerequisiteStatus.UNKNOWN,
                "method": "psutil",
                "monitoring": False,
                "details": {"error": str(e)}
            }
