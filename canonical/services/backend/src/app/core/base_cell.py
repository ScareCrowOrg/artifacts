"""
BaseCell - Abstract Base Class for Backend Cells

This module defines the BaseCell ABC that provides execution lifecycle,
validation, and health checking capabilities for all backend cell types.

Part of BaseCell v1.0 Framework Implementation
Epic: Phase 1 - Foundation
Task: [BC-PY-001] Create BaseCell ABC (Python)

Architecture Notes:
- Cells register jobs in Redis (lightweight orchestration)
- Windows-worker manages GPU/VRAM resources (heavy computation)
- Setup/teardown manage lightweight resources only (connections, listeners)
"""

import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# ============ SUPPORTING TYPES ============


class HealthStatus(Enum):
    """Health status enumeration"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class EnvironmentConfig:
    """
    Runtime environment configuration

    Note: has_gpu and gpu_vram_mb are informational only.
    Actual GPU/VRAM is managed by windows-worker, not by cells.
    """

    has_gpu: bool
    gpu_vram_mb: int
    cpu_cores: int
    headless_mode: bool
    timeout_seconds: int = 300
    allow_internet: bool = True
    allow_external_api: bool = True
    batch_size: int = 1
    cache_enabled: bool = True


@dataclass
class CellResult:
    """Result of cell execution"""

    success: bool
    output: Dict[str, Any]
    id: Optional[str] = None
    status: Optional[str] = None  # 'pending', 'completed', 'failed'
    artifacts: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    quality_score: Optional[float] = None
    error: Optional[str] = None
    execution_steps: List[str] = field(default_factory=list)
    fragments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON response"""
        return {
            "id": self.id,
            "status": self.status,
            "success": self.success,
            "output": self.output,
            "artifacts": self.artifacts,
            "execution_time": self.execution_time,
            "quality_score": self.quality_score,
            "error": self.error,
            "execution_steps": self.execution_steps,
            "fragments": self.fragments,
            "metadata": self.metadata,
        }


@dataclass
class HealthCheckResult:
    """Health status of cell"""

    status: HealthStatus
    reason: Optional[str] = None
    estimated_recovery_seconds: Optional[float] = None

    @property
    def can_execute(self) -> bool:
        """Whether cell can execute"""
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON response"""
        return {
            "status": self.status.value,
            "can_execute": self.can_execute,
            "reason": self.reason,
            "estimated_recovery_seconds": self.estimated_recovery_seconds,
        }


@dataclass
class CellMetadata:
    """Cell introspection metadata"""

    id: str
    name: str
    version: str
    description: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    tags: List[str]
    llm_config: Optional[Dict[str, Any]] = None
    estimated_duration_seconds: Optional[float] = None
    required_resources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON response"""
        return asdict(self)


@dataclass
class ValidationError:
    """Validation error"""

    field: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        """Convert to dict for JSON response"""
        return {"field": self.field, "message": self.message}


# ============ MAIN INTERFACE ============


class BaseCell(ABC):
    """
    Abstract base class for backend cells (Python)

    Lifecycle:
    1. setup(config) - Called once before first execution
       - Allocates lightweight resources (Redis connections, listeners)
       - Does NOT allocate GPU/VRAM (managed by windows-worker)

    2. execute(input) - Called multiple times for executions
       - Validates input
       - Registers job in Redis queue
       - Polls for result from windows-worker
       - Returns structured CellResult

    3. teardown() - Called once when cell is destroyed
       - Releases lightweight resources (closes connections)
       - Does NOT release GPU/VRAM (not cell's responsibility)

    Instance Composition Pattern:
    - BaseCell can optionally reference its Cell runtime instance
    - This enables access to metadata (assignee_id, initial_data, fragments, etc.)
    - Follows the PipelineItem → NotebookItem composition pattern
    - The instance is optional to maintain backward compatibility

    Power of Default:
    - setup(), teardown(), health_check() have default implementations
    - Simple cells only need to implement: execute(), describe(), validate()

    Example (Utility Cell - No Instance):
        class CalculatorCell(BaseCell):
            async def execute(self, input: Dict[str, Any]) -> CellResult:
                operation = input['operation']
                a = input['a']
                b = input['b']

                result = a + b if operation == 'add' else a - b

                return CellResult(
                    success=True,
                    output={'result': result},
                    execution_time=0.005
                )

            async def describe(self) -> CellMetadata:
                return CellMetadata(
                    id='calculator-cell',
                    name='Calculator',
                    version='1.0.0',
                    description='Simple math operations',
                    inputs={'operation': 'string', 'a': 'number', 'b': 'number'},
                    outputs={'result': 'number'},
                    tags=['math', 'calculator']
                )

            def validate(self, input: Dict[str, Any]) -> List[ValidationError]:
                errors = []
                if 'operation' not in input:
                    errors.append(ValidationError('operation', 'Required'))
                if 'a' not in input or not isinstance(input['a'], (int, float)):
                    errors.append(ValidationError('a', 'Must be a number'))
                if 'b' not in input or not isinstance(input['b'], (int, float)):
                    errors.append(ValidationError('b', 'Must be a number'))
                return errors

    Example (Context-Aware Cell - With Instance):
        class DataProcessingCell(BaseCell):
            def __init__(self, cell_instance: Optional['Cell'] = None):
                self.cell_instance = cell_instance

            async def execute(self, input: Dict[str, Any]) -> CellResult:
                # Access metadata when available
                owner = self.cell_instance.assignee_id if self.cell_instance else None
                config = self.cell_instance.initial_data if self.cell_instance else {}

                # Process with context
                result = self.process_with_context(input, owner=owner, config=config)

                return CellResult(
                    success=True,
                    output=result,
                    execution_time=10
                )
    """

    def __init__(self, cell_instance: Optional[Any] = None):
        """
        Initialize the BaseCell.

        Args:
            cell_instance: Optional Cell instance for metadata access.
                          When provided, enables context-aware execution.
                          When None, cell operates as pure utility.
        """
        self.cell_instance = cell_instance

    # ===== ABSTRACT METHODS (must implement) =====

    @abstractmethod
    async def execute(self, input: Dict[str, Any]) -> CellResult:
        """
        Execute the cell's main logic

        For cells with GPU operations:
        1. Validate input
        2. Register job in Redis queue (e.g., 'scareverse:rembg-jobs:queue')
        3. Poll for result from Redis status key (e.g., 'scareverse:rembg-status:{job_id}')
        4. Return structured CellResult

        For cells with local operations:
        1. Validate input
        2. Execute logic directly
        3. Return structured CellResult

        Args:
            input: Input data (merged default_initial_data + user input)

        Returns:
            CellResult with success, output, artifacts, execution_time

        Raises:
            Exception: If execution fails catastrophically
        """

    @abstractmethod
    async def describe(self) -> CellMetadata:
        """
        Describe cell capabilities

        Returns metadata about the cell including inputs, outputs, and configuration.
        This can load from type.json or return hardcoded values.

        Returns:
            CellMetadata with inputs/outputs/tags/llm_config

        Example:
            return CellMetadata(
                id='png-generator-cell',
                name='PNG Generator',
                version='1.0.0',
                description='Generate and manipulate PNG images',
                inputs={
                    'prompt': 'string',
                    'remove_background': 'boolean'
                },
                outputs={
                    'image_url': 'string',
                    'image_base64': 'string'
                },
                tags=['image', 'generation', 'png'],
                required_resources=['redis', 'windows-worker']
            )
        """

    @abstractmethod
    def validate(self, input: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate input against schema

        Checks if input meets the cell's requirements.
        Returns empty list if valid, or list of errors if invalid.

        Args:
            input: Input data to validate

        Returns:
            List of ValidationError (empty if valid)
            Format: [ValidationError(field="prompt", message="Required")]

        Example:
            errors = []
            if 'prompt' not in input:
                errors.append(ValidationError('prompt', 'Required'))
            if input.get('width', 0) < 1:
                errors.append(ValidationError('width', 'Must be positive'))
            return errors
        """

    # ===== LIFECYCLE METHODS (optional override) =====

    async def setup(self, config: EnvironmentConfig) -> None:
        """
        One-time initialization (lightweight resources only)

        Allocates lightweight resources:
        - Redis connections for job queueing
        - HTTP clients
        - Event listeners
        - Configuration loading

        Does NOT allocate:
        - GPU/VRAM (managed by windows-worker)
        - Heavy models (loaded by windows-worker)
        - Large datasets (loaded on-demand)

        Default implementation: no-op
        Override only if cell needs initialization.

        Args:
            config: Environment configuration

        Example:
            async def setup(self, config: EnvironmentConfig) -> None:
                # Connect to Redis for job queueing
                self.redis_client = await get_redis_client()
                logger.info("Setup complete - Redis connected")
        """

    async def teardown(self) -> None:
        """
        One-time cleanup (lightweight resources only)

        Releases lightweight resources:
        - Closes Redis connections
        - Closes HTTP clients
        - Removes event listeners

        Does NOT release:
        - GPU/VRAM (managed by windows-worker)
        - Models (managed by windows-worker)

        Default implementation: no-op
        Override only if cell allocated resources in setup().

        Example:
            async def teardown(self) -> None:
                # Close Redis connection
                if hasattr(self, 'redis_client') and self.redis_client:
                    await self.redis_client.close()
                logger.info("Teardown complete - Redis disconnected")
        """

    async def health_check(self) -> HealthCheckResult:
        """
        Check if cell can execute

        Verifies:
        - Redis accessibility (for job queueing)
        - External API availability (if needed)
        - Queue saturation levels

        Does NOT verify:
        - GPU/VRAM availability (windows-worker's responsibility)
        - Model loading status (windows-worker's responsibility)

        Default implementation: always healthy
        Override if cell has dependencies to check.

        Returns:
            HealthCheckResult with status and can_execute flag

        Example:
            async def health_check(self) -> HealthCheckResult:
                try:
                    # Check Redis connectivity
                    await self.redis_client.ping()

                    # Check queue size (optional)
                    queue_size = await self.redis_client.llen('scareverse:rembg-jobs:queue')
                    if queue_size > 100:
                        return HealthCheckResult(
                            status=HealthStatus.DEGRADED,
                            reason=f"Queue saturated ({queue_size} jobs)"
                        )

                    return HealthCheckResult(status=HealthStatus.HEALTHY)
                except Exception as e:
                    return HealthCheckResult(
                        status=HealthStatus.UNAVAILABLE,
                        reason=f"Redis connection failed: {str(e)}"
                    )
        """
        return HealthCheckResult(status=HealthStatus.HEALTHY)

    # ===== ATOMIC EXECUTION =====

    async def run(self, lifecycle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute complete cell lifecycle atomically

        Executes setup → execute → save in one call.
        Each step adds a fragment to the result for tracing.
        On error, aborts execution and returns failed result.

        Args:
            lifecycle: Lifecycle configuration with keys:
                - setup: Optional setup configuration (dict)
                - execute: Execute action(s) - single dict or list of dicts
                  Each execute dict must have 'action' key and optional 'params'
                - save: Optional save flag (bool) or config (dict), default True

        Returns:
            Dict with keys:
                - id: Cell ID (from describe())
                - status: 'pending', 'completed', or 'failed'
                - success: Boolean success flag
                - output: Output data from execution
                - fragments: List of execution fragments for tracing
                - error: Error message if failed
                - execution_time: Total execution time

        Example:
            result = await cell.run({
                'setup': {'mode': 'production'},
                'execute': [
                    {'action': 'generate', 'params': {'prompt': 'cat'}},
                    {'action': 'enhance', 'params': {'style': '3d'}}
                ],
                'save': True
            })
        """

        # Initialize result
        metadata = await self.describe()
        result = {
            "id": metadata.id,
            "status": "pending",
            "success": False,
            "output": {},
            "fragments": [],
            "execution_time": 0.0,
        }

        start_time = time.time()

        try:
            # Step 1: Setup (optional)
            if lifecycle.get("setup"):
                setup_config = lifecycle["setup"]
                # Convert dict to EnvironmentConfig if needed
                if isinstance(setup_config, dict):
                    env_config = EnvironmentConfig(**setup_config)
                else:
                    env_config = setup_config

                await self.setup(env_config)
                result["fragments"].append({"type": "setup", "status": "completed"})

            # Step 2: Execute (required, can be single or array)
            execute_actions = lifecycle.get("execute")
            if not execute_actions:
                raise ValueError("Lifecycle configuration must include 'execute' key")

            if not isinstance(execute_actions, list):
                execute_actions = [execute_actions]

            for action_config in execute_actions:
                action_name = action_config.get("action")
                action_params = action_config.get("params", {})

                if not action_name:
                    raise ValueError("Execute action must have 'action' key")

                # Execute action
                # Note: Subclasses should implement execute_action() or similar
                # For now, we call execute() with the params
                execute_result = await self.execute(action_params)

                result["fragments"].append(
                    {
                        "type": "execute",
                        "action": action_name,
                        "output": execute_result.output,
                        "status": "completed",
                    }
                )

                # Store output for next action
                result["output"] = execute_result.output

            # Step 3: Save (default: true)
            save_config = lifecycle.get("save", True)
            if save_config is not False:
                # Implement save logic here or in subclass
                # For now, just mark as completed
                result["fragments"].append({"type": "save", "status": "completed"})

            # Mark as completed
            result["status"] = "completed"
            result["success"] = True

        except Exception as e:
            result["status"] = "failed"
            result["success"] = False
            result["error"] = str(e)
            result["fragments"].append(
                {"type": "error", "status": "failed", "error": str(e)}
            )

        finally:
            result["execution_time"] = time.time() - start_time

        return result

    # ===== UTILITY METHODS (future enhancements) =====

    async def ask_ai(self, prompt: str, model: str = None) -> str:
        """
        Wrapper for LLM calls (future implementation)

        Single point of change for AI model configuration.
        Switch from Mistral to Llama 3? Change one line here,
        and all AI-powered cells get the upgrade.

        This will be implemented in v1.1 with Ollama integration.

        Args:
            prompt: Prompt to send to LLM
            model: Optional model override (default from config)

        Returns:
            LLM response as string

        Raises:
            NotImplementedError: Currently not implemented (v1.1)
        """
        raise NotImplementedError("ask_ai will be implemented in v1.1")


# ============ HELPER FUNCTIONS ============


def create_healthy_result() -> HealthCheckResult:
    """Create default healthy result"""
    return HealthCheckResult(status=HealthStatus.HEALTHY)


def create_default_environment_config() -> EnvironmentConfig:
    """Create default environment configuration"""
    import multiprocessing
    import os

    return EnvironmentConfig(
        has_gpu=False,  # Detection logic should be implemented
        gpu_vram_mb=0,
        cpu_cores=multiprocessing.cpu_count(),
        headless_mode=os.getenv("HEADLESS_MODE", "false").lower() == "true",
        timeout_seconds=300,
        allow_internet=True,
        allow_external_api=True,
        batch_size=1,
        cache_enabled=True,
    )
