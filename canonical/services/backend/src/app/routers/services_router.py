"""
Service Management API router for Cockpit.

Implements comprehensive service management functionality:
- GET /services/status - Get status of all monitored services
- POST /services/{service_id}/start - Start a service
- POST /services/{service_id}/stop - Stop a service
- POST /services/{service_id}/restart - Restart a service
- GET /services/config - Get service configurations
- POST /services/config - Update service configurations
- POST /services/config/test - Test connectivity to a service
- GET /services/{service_id}/logs - Get recent logs for a service
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_current_user_required
from ..config import BASE_DIR
from ..models import User

logger = logging.getLogger(__name__)

# Create router
services_router = APIRouter(prefix="/services", tags=["services"])


# Pydantic models
class ServiceStatus(BaseModel):
    """Status information for a service."""

    id: str
    name: str
    status: str  # running, stopped, error, unknown
    pid: Optional[int] = None
    uptime: Optional[float] = None  # seconds
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    port: Optional[int] = None
    last_check: str


class ServiceConfig(BaseModel):
    """Configuration for a service."""

    id: str
    name: str
    endpoint: str
    port: int
    enabled: bool = True
    auto_start: bool = False
    env_vars: Optional[Dict[str, str]] = None
    start_command: Optional[str] = None
    stop_command: Optional[str] = None


class ConfigUpdate(BaseModel):
    """Request to update service configuration."""

    services: List[ServiceConfig]


class ConnectivityTest(BaseModel):
    """Request to test connectivity to a service."""

    endpoint: str
    port: int
    timeout: int = Field(default=5, ge=1, le=30)


class ServiceAction(BaseModel):
    """Response for service control actions."""

    success: bool
    message: str
    service_id: str


def _parse_service_port(env_var: str, default: str) -> int:
    """
    Parse service port from environment variable with error handling.

    Args:
        env_var: Environment variable name
        default: Default port value as string

    Returns:
        Port number as integer

    Raises:
        ValueError: If the port value is invalid
    """
    port_str = os.getenv(env_var, default)
    try:
        port = int(port_str)
        if not (1 <= port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {port}")
        return port
    except ValueError as e:
        logger.error("Invalid port value for %s='%s': %s", env_var, port_str, e)
        logger.warning("Using default port %s for %s", default, env_var)
        return int(default)


# Service definitions
# These represent the key services in the ScareVerseLab ecosystem
# Defaults can be overridden via environment variables
#
# Phase 1B Update: Using VITE_API_BASE_* variables for consistency
# - VITE_API_BASE_PORT replaces SERVICE_BACKEND_PORT
# - VITE_API_BASE_URL replaces SERVICE_BACKEND_ENDPOINT
MONITORED_SERVICES = {
    "backend": {
        "name": "Backend API (FastAPI)",
        "process_name": "uvicorn",
        "default_port": _parse_service_port("VITE_API_BASE_PORT", "5050"),
        "default_endpoint": os.getenv("VITE_API_BASE_URL", "http://localhost:5050")
        + "/api",
    },
    "frontend": {
        "name": "Frontend Dev Server (Vite)",
        "process_name": "node",
        "process_args": ["vite"],
        "default_port": _parse_service_port("SERVICE_FRONTEND_PORT", "5173"),
        "default_endpoint": os.getenv(
            "SERVICE_FRONTEND_ENDPOINT", "http://localhost:5173"
        ),
    },
}


def get_service_process(service_id: str) -> Optional[psutil.Process]:
    """
    Find the process for a given service.
    Returns the Process object if found, None otherwise.
    """
    service_def = MONITORED_SERVICES.get(service_id)
    if not service_def:
        return None

    process_name = service_def.get("process_name")
    process_args = service_def.get("process_args", [])

    try:
        for proc in psutil.process_iter(["name", "cmdline", "pid"]):
            try:
                proc_name = proc.info.get("name", "").lower()
                cmdline = proc.info.get("cmdline", [])

                # Check if process name matches
                if process_name.lower() in proc_name:
                    # If process_args specified, verify them
                    if process_args:
                        cmdline_str = " ".join(cmdline).lower()
                        if all(arg.lower() in cmdline_str for arg in process_args):
                            return proc
                    else:
                        return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logger.error("Error finding process for service %s: %s", service_id, e)

    return None


def get_process_info(proc: psutil.Process) -> Dict[str, Any]:
    """
    Extract relevant information from a process.
    """
    try:
        with proc.oneshot():
            return {
                "pid": proc.pid,
                "uptime": time.time() - proc.create_time(),
                "memory_mb": proc.memory_info().rss / 1024 / 1024,
                "cpu_percent": proc.cpu_percent(interval=0.1),
            }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {}


@services_router.get("/status", response_model=List[ServiceStatus])
async def get_services_status(_current_user: User = Depends(get_current_user_required)):
    """
    Get the current status of all monitored services.

    Required: authenticated user

    Returns a list of service status objects with runtime information.
    """
    statuses = []

    for service_id, service_def in MONITORED_SERVICES.items():
        proc = get_service_process(service_id)

        if proc:
            proc_info = get_process_info(proc)
            status = ServiceStatus(
                id=service_id,
                name=service_def["name"],
                status="running",
                pid=proc_info.get("pid"),
                uptime=proc_info.get("uptime"),
                memory_mb=proc_info.get("memory_mb"),
                cpu_percent=proc_info.get("cpu_percent"),
                port=service_def.get("default_port"),
                last_check=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
        else:
            status = ServiceStatus(
                id=service_id,
                name=service_def["name"],
                status="stopped",
                port=service_def.get("default_port"),
                last_check=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )

        statuses.append(status)

    logger.info("Retrieved status for %s services", len(statuses))
    return statuses


@services_router.get("/config")
async def get_services_config(_current_user: User = Depends(get_current_user_required)):
    """
    Get service configurations from localStorage or defaults.

    Required: authenticated user

    Returns default configurations for all services.
    Actual localStorage is managed on the frontend.
    """
    configs = []

    for service_id, service_def in MONITORED_SERVICES.items():
        config = ServiceConfig(
            id=service_id,
            name=service_def["name"],
            endpoint=service_def.get("default_endpoint") or "",
            port=service_def.get("default_port") or 0,
            enabled=True,
            auto_start=False,
        )
        configs.append(config)

    return {
        "services": configs,
        "version": "1.0.0",
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@services_router.post("/config")
async def update_services_config(
    config_update: ConfigUpdate, _current_user: User = Depends(get_current_user_required)
):
    """
    Validate service configuration updates.

    Note: Actual persistence is handled in frontend localStorage.
    This endpoint validates the configuration structure.
    """
    try:
        # Validate each service config
        for service_config in config_update.services:
            # Validate service ID exists
            if service_config.id not in MONITORED_SERVICES:
                raise HTTPException(
                    status_code=400, detail=f"Unknown service ID: {service_config.id}"
                )

            # Validate port range
            if service_config.port and not (1 <= service_config.port <= 65535):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid port for {service_config.id}: {service_config.port}",
                )

        logger.info("Validated configuration for %s services", len(config_update.services))
        return {
            "status": "ok",
            "message": "Configuration validated successfully",
            "services_updated": len(config_update.services),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error validating configuration: %s", e)
        raise HTTPException(status_code=500, detail="Configuration validation failed") from e


@services_router.post("/config/test")
async def test_connectivity(
    test: ConnectivityTest, _current_user: User = Depends(get_current_user_required)
):
    """
    Test connectivity to a service endpoint.

    Attempts to connect to the specified endpoint and port.
    Returns success/failure with diagnostic information.
    """
    import socket

    try:
        # Parse endpoint to get host
        endpoint = test.endpoint.replace("http://", "").replace("https://", "")
        host = endpoint.split(":")[0].split("/")[0]

        # Try to connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(test.timeout)

        result = sock.connect_ex((host, test.port))
        sock.close()

        if result == 0:
            return {
                "success": True,
                "message": f"Successfully connected to {host}:{test.port}",
                "endpoint": test.endpoint,
                "port": test.port,
                "response_time_ms": test.timeout * 1000,  # Approximate
            }
        else:
            return {
                "success": False,
                "message": f"Failed to connect to {host}:{test.port}",
                "endpoint": test.endpoint,
                "port": test.port,
                "error_code": result,
            }
    except socket.timeout:
        return {
            "success": False,
            "message": f"Connection timeout after {test.timeout}s",
            "endpoint": test.endpoint,
            "port": test.port,
        }
    except Exception as e:
        logger.error("Error testing connectivity: %s", e)
        return {
            "success": False,
            "message": "Connection test failed due to an error",
            "endpoint": test.endpoint,
            "port": test.port,
        }


@services_router.get("/{service_id}/logs")
async def get_service_logs(
    service_id: str,
    lines: int = 50,
    _current_user: User = Depends(get_current_user_required),
):
    """
    Get recent log entries for a service.

    Required: authenticated user

    Returns the last N lines from the service's log file.
    Log file locations are determined by service configuration.
    """
    if service_id not in MONITORED_SERVICES:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_id}")

    # Define log file paths for known services
    # Paths can be overridden via environment variables or use BASE_DIR
    log_paths = {
        "backend": Path(
            os.getenv("LOG_PATH_BACKEND", str(BASE_DIR / "backend" / "backend.log"))
        ),
    }

    log_path = log_paths.get(service_id)

    if not log_path or not log_path.exists():
        return {
            "service_id": service_id,
            "logs": [],
            "message": "No logs available for this service",
        }

    try:
        # Read last N lines from log file
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        return {
            "service_id": service_id,
            "logs": [line.strip() for line in recent_lines],
            "total_lines": len(recent_lines),
            "log_file": str(log_path),
        }
    except Exception as e:
        logger.error("Error reading logs for %s: %s", service_id, e)
        raise HTTPException(status_code=500, detail="Failed to read service logs") from e


@services_router.post("/{service_id}/start")
async def start_service(
    service_id: str, _current_user: User = Depends(get_current_user_required)
):
    """
    Start a service.

    Note: This is a placeholder. Actual service management requires
    proper orchestration and permissions. For MVP, returns status only.
    """
    if service_id not in MONITORED_SERVICES:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_id}")

    # Check if already running
    proc = get_service_process(service_id)
    if proc:
        return ServiceAction(
            success=False,
            message=f"Service {service_id} is already running",
            service_id=service_id,
        )

    # For MVP: Return informational message
    # Full implementation would use subprocess to start services
    logger.warning("Service start requested for %s but not implemented", service_id)
    return ServiceAction(
        success=False,
        message=f"Service management not fully implemented. Please start {service_id} manually.",
        service_id=service_id,
    )


@services_router.post("/{service_id}/stop")
async def stop_service(
    service_id: str, _current_user: User = Depends(get_current_user_required)
):
    """
    Stop a service.

    Note: This is a placeholder. Actual service management requires
    proper orchestration and permissions. For MVP, returns status only.
    """
    if service_id not in MONITORED_SERVICES:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_id}")

    # Check if running
    proc = get_service_process(service_id)
    if not proc:
        return ServiceAction(
            success=False,
            message=f"Service {service_id} is not running",
            service_id=service_id,
        )

    # For MVP: Return informational message
    # Full implementation would gracefully terminate the process
    logger.warning("Service stop requested for %s but not implemented", service_id)
    return ServiceAction(
        success=False,
        message=f"Service management not fully implemented. Please stop {service_id} manually.",
        service_id=service_id,
    )


@services_router.post("/{service_id}/restart")
async def restart_service(
    service_id: str, _current_user: User = Depends(get_current_user_required)
):
    """
    Restart a service.

    Note: This is a placeholder. Actual service management requires
    proper orchestration and permissions. For MVP, returns status only.
    """
    if service_id not in MONITORED_SERVICES:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_id}")

    # For MVP: Return informational message
    logger.warning("Service restart requested for %s but not implemented", service_id)
    return ServiceAction(
        success=False,
        message=f"Service management not fully implemented. Please restart {service_id} manually.",
        service_id=service_id,
    )
