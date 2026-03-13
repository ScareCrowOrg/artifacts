"""
Cells API Router - RESTful endpoints for ScareVerse cell management.

Implements CRUD and execution endpoints for cells.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import logging
import asyncio
import sys
import importlib.util
import inspect
from pathlib import Path
from datetime import datetime

from ..models import (
    User,
    Cell,
    NotebookItemType,
    CreateCellRequest,
    ExecuteCellRequest,
    ExecuteEphemeralCellRequest,
    UpdateCellRequest,
    CellRunRequest,
    CellStatus,
    Fragment,
    CellGenerationRequest,
    CellGenerationResponse,
    CellPromotionRequest,
    CellPromotionResponse,
)
from ..database import db
from ..auth import get_current_user_required
from ..permissions import has_permission, check_resource_ownership, get_user_permissions
from ..core.exceptions import (
    CellNotFoundException,
    ValidationException,
    SaveFailedException,
    ServerException,
)
from ..services.cell_generation_service import CellGenerationService
from ..services.cell_validation_service import CellValidationService
from ..services.cell_promotion_service import CellPromotionService
from ..services.redis_pubsub_service import RedisPubSubService
from ..config import BASE_DIR

logger = logging.getLogger(__name__)

# Constants
EPHEMERAL_CATEGORY = "ephemeral"  # Category marker for ephemeral (non-persistent) cells

# Cache for dynamically loaded cell modules to prevent sys.modules pollution
_cell_module_cache = {}

# Create cells router
cells_router = APIRouter(prefix="/cells", tags=["Cells"])

# Services will be initialized with Redis on first use
# We use a lazy initialization pattern to ensure Redis is available
# Thread-safe locks to prevent race conditions during initialization
_generation_service = None
_validation_service = None
_promotion_service = None
_service_lock = asyncio.Lock()


async def get_generation_service() -> CellGenerationService:
    """Get or initialize Cell Generation Service with Redis (thread-safe)."""
    global _generation_service
    async with _service_lock:
        if _generation_service is None:
            from ..services.redis_pubsub_service import get_pubsub_service

            redis_service = await get_pubsub_service()
            _generation_service = CellGenerationService(
                redis_service=redis_service, use_real_llm=True  # Enable real LLM for MVP 2
            )
            # Start Hypnosis Loop listener for auto-correction
            await _generation_service.start_hypnosis_loop_listener()
    return _generation_service


async def get_validation_service() -> CellValidationService:
    """Get or initialize Cell Validation Service with Redis (thread-safe)."""
    global _validation_service
    async with _service_lock:
        if _validation_service is None:
            from ..services.redis_pubsub_service import get_pubsub_service

            redis_service = await get_pubsub_service()
            _validation_service = CellValidationService(redis_service=redis_service)
            # Start re-validation listener for auto-corrected cells
            await _validation_service.start_revalidation_listener()
    return _validation_service


async def get_promotion_service() -> CellPromotionService:
    """Get or initialize Cell Promotion Service with Redis (thread-safe)."""
    global _promotion_service
    async with _service_lock:
        if _promotion_service is None:
            from ..services.redis_pubsub_service import get_pubsub_service

            redis_service = await get_pubsub_service()
            _promotion_service = CellPromotionService(redis_service=redis_service)
    return _promotion_service


@cells_router.get("/list", response_model=List[Cell])
async def list_cells(
    assignee_id: str = None, current_user: User = Depends(has_permission(["cells.read_own"]))
):
    """
    List cells for the authenticated user or a specific user.

    Required permission: `cells.read_own` (list own) or `cells.read_any` (list all)
    """
    try:
        user_permissions = await get_user_permissions(current_user)

        # Get all cells
        try:
            all_cells = await db.find_many("cells", current_user=current_user, model_class=Cell)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        # Ensure all are Cell instances
        all_cells = [Cell(**c) if not isinstance(c, Cell) else c for c in all_cells]

        # Admin or viewer can see all cells
        if "cells.read_any" in user_permissions or "*" in user_permissions:
            # If specific user requested, filter by that user
            if assignee_id:
                filtered_cells = [c for c in all_cells if c.assignee_id == assignee_id]
            else:
                # Return all cells
                filtered_cells = all_cells
        else:
            # Regular user sees only their own cells
            user_id = assignee_id or current_user.id
            filtered_cells = [c for c in all_cells if c.assignee_id == user_id]

        return filtered_cells

    except Exception as e:
        logger.error(f"Error listing cells: {e}")
        raise ServerException(f"Error listing cells: {str(e)}")


@cells_router.get("/types/list", response_model=List[NotebookItemType])
async def list_notebook_item_types(current_user: User = Depends(get_current_user_required)):
    """
    List notebook item types.

    Returns all NotebookItemType instances (serves both cells and books).
    Replaces the deprecated TipoCelula endpoint.

    Note: NotebookItemType is the unified abstraction for both cell types
    and book types. Clients can filter by type if needed.
    """
    try:
        try:
            tipos = await db.find_many(
                "notebook_item_types",
                current_user=current_user,
                model_class=NotebookItemType,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        logger.info(f"[TYPES-LIST] Listed {len(tipos)} notebook item types")
        if not tipos:
            logger.warning("[TYPES-LIST] No notebook item types found! Check CanonicalQueryEngine initialization.")
        return tipos

    except Exception as e:
        logger.error(f"Error listing notebook item types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing notebook item types: {str(e)}",
        )


@cells_router.get("/{cell_id}", response_model=Cell)
async def get_cell(cell_id: str, current_user: User = Depends(has_permission(["cells.read_own"]))):
    """
    Get a specific cell by ID.

    Required permission: `cells.read_own` (own) or `cells.read_any` (any)

    **Phase 1B - Unified Lookup**:
    - Searches across all storage layers (sandbox → canonical → MongoDB)
    - Uses L1 Redis cache for performance (~5ms cached hits)
    - Returns cell from any location transparently
    """
    try:
        # Phase 1B: Use unified lookup (checks sandbox → MongoDB with L1 cache)
        try:
            cell = await db.find_one(
                "cells",
                cell_id,
                current_user=current_user,
                model_class=Cell,
                resource_owner_id=current_user.id,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not cell:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Cell {cell_id} not found"
            )

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=cell.assignee_id,
            current_user=current_user,
            admin_permission="cells.read_any",
        )

        logger.info(f"Cell {cell_id} retrieved")
        return cell

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cell: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting cell: {str(e)}",
        )


@cells_router.post("/create", response_model=Cell, status_code=status.HTTP_201_CREATED)
async def create_cell(
    request: CreateCellRequest,
    scope: str = "sandbox",  # Phase 1B: DEFAULT is sandbox (local-first)
    current_user: User = Depends(has_permission(["cells.create"]))
):
    """
    Create a new cell.

    Required permission: `cells.create`

    **Phase 1B - Local-First Architecture**:
    - `scope="sandbox"` (DEFAULT): Creates cell in private sandbox (artifacts/sandbox/{user_id}/)
      - Never auto-published to MongoDB
      - Private, local-only storage
      - User must explicitly publish via POST /{id}/publish
    - `scope="published"`: Creates cell directly in MongoDB (shared, not recommended until stable)

    Now supports NotebookItemType for type-driven behavior.

    Example request body:
    ```json
    {
        "notebook_item_type_id": "uuid_do_notebook_item_type",
        "assignee_id": "uuid_do_usuario",
        "initial_data": {"title": "My Cell", "content": "Initial content"}
    }
    ```
    """
    try:
        from ..models import NotebookItemType

        # Use the notebook_item_type_id
        type_id = request.notebook_item_type_id

        if not type_id:
            raise ValidationException(
                "notebook_item_type_id must be provided", field="notebook_item_type_id"
            )

        # Fetch NotebookItemType (TipoCelula is deprecated)
        try:
            notebook_item_type = await db.find_one(
                "notebook_item_types",
                type_id,
                current_user=current_user,
                model_class=NotebookItemType,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not notebook_item_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NotebookItemType {type_id} not found",
            )

        # Verify that the user exists
        try:
            user = await db.find_one(
                "users",
                request.assignee_id,
                current_user=current_user,
                model_class=User,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {request.assignee_id} not found",
            )

        logger.debug(request)

        # Build initial_data by merging type defaults with request overrides
        cell_data = {}
        if notebook_item_type and notebook_item_type.default_initial_data:
            cell_data.update(notebook_item_type.default_initial_data)

        # Override with request data (using English field name)
        request_data = getattr(request, "initial_data", {}) or {}
        if request_data:
            cell_data.update(request_data)

        logger.debug(f"Merged initial_data: {cell_data}")

        # Build refs by merging type defaults with request overrides
        cell_refs = {}
        if notebook_item_type:
            if notebook_item_type.default_refs:
                cell_refs.update(notebook_item_type.default_refs)

            # Check if instance overrides are allowed
            if notebook_item_type.allow_instance_override_refs and request.refs:
                cell_refs.update(request.refs)
        elif request.refs:
            # If no type or type allows overrides, use request refs
            cell_refs = request.refs

        logger.info(f"Criando célula para usuário {request.assignee_id} com tipo {type_id}")
        logger.debug(f"Initial data: {cell_data}, refs: {cell_refs}")
        logger.info(f"[CELL-CREATE] Merged initial_data: {cell_data}")
        logger.info(
            f"[CELL-CREATE] fileName={cell_data.get('fileName')}, filePath={cell_data.get('filePath')}"
        )

        # Extract category from initial_data to core field (migration from old schema)
        # This ensures category is a core cell property, not just initialization data
        category = cell_data.pop("category", None)  # Remove from initial_data

        # Check if this is an ephemeral cell (should not be persisted)
        # Ephemeral cells have category="ephemeral" as a core field
        is_ephemeral = category == EPHEMERAL_CATEGORY

        logger.info(f"[CELL-CREATE] Category extracted: '{category}', is_ephemeral={is_ephemeral}")

        # Create Cell with NotebookItem fields
        celula = Cell(
            assignee_id=request.assignee_id,
            notebook_item_type_id=type_id,
            source_book_id=request.source_book_id,
            initial_data=cell_data,  # No longer contains category
            refs=cell_refs,
            status=CellStatus.PENDING,
            title=request.title,
            content=request.content,
            category=category,  # Set as core field
        )

        # Only persist non-ephemeral cells to database
        if not is_ephemeral:
            # Unified insert - routing via resource_owner_id
            cell_dict = celula.model_dump(mode="json")
            result_id = await db.insert(
                collection="cells",
                document=cell_dict,
                current_user=current_user,
                resource_owner_id=request.assignee_id if scope == "sandbox" else None,
            )
            if scope == "sandbox":
                logger.info(f"Cell {celula.id} created in sandbox (local, private)")
            else:
                logger.info(f"Cell {celula.id} created and persisted in MongoDB (published)")
        else:
            logger.info(f"Ephemeral cell {celula.id} created (not persisted in database)")

        # Return cell with scope metadata
        celula_dict = celula.model_dump()
        celula_dict["_scope"] = scope if not is_ephemeral else "ephemeral"
        celula_dict["_location"] = (
            "sandbox" if scope == "sandbox" and not is_ephemeral
            else "mongodb" if not is_ephemeral
            else "memory"
        )
        return Cell(**celula_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar célula: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar célula: {str(e)}",
        )


@cells_router.post("/{cell_id}/execute", response_model=Cell)
async def execute_cell(
    cell_id: str,
    request: ExecuteCellRequest,
    current_user: User = Depends(has_permission(["cells.execute_own"])),
):
    """
    Execute a cell using the new adapter architecture.

    Required permission: `cells.execute_own` or `cells.execute_any`

    This endpoint:
    1. Gets the Cell (pure data model)
    2. Creates a CellAdapter to wrap the cell
    3. Creates a PipelineItem instance to manage execution
    4. Executes via the adapter, which orchestrates the ingestion_graph
    5. Updates cell state and returns
    """
    try:
        # Find the cell
        try:
            cells = await db.find_many("cells", current_user=current_user, model_class=Cell)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        cell = None
        user_id = None
        session_id = "default"

        for c in cells:
            if c.id == cell_id:
                cell = c
                user_id = c.assignee_id
                break

        if not cell:
            raise CellNotFoundException(cell_id)

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=cell.assignee_id,
            current_user=current_user,
            admin_permission="cells.execute_any",
        )

        # Import PipelineItem and CellAdapter
        from ..core.models import PipelineItem
        from ..models import CellAdapter

        # Create a CellAdapter wrapping the pure cell model
        cell_adapter = CellAdapter(cell=cell)

        # Merge execution parameters into initial_data for the pipeline
        execution_data = {**cell.initial_data, **request.parameters}

        # Create a PipelineItem for execution management
        pipeline_item = PipelineItem(
            notebook_item_id=cell.id,
            notebook_item_data=cell,  # Direct reference to the NotebookItem
            cell_id=cell.id,
            cell_type_id=cell.notebook_item_type_id,
            assignee_id=cell.assignee_id,
            data=execution_data,
        )

        # Update cell state to RUNNING before execution
        cell.status = CellStatus.RUNNING
        # FIX Issue #1206 (2025-12-11): Cell documents use assignee_id, not user_id/session_id
        # These parameters would create a query like {"id": "...", "user_id": "...", "session_id": "..."}
        # but Cell documents don't have user_id or session_id fields, causing "document not found" errors
        await db.update(
            "cells",
            cell_id,
            {"status": CellStatus.RUNNING.value},
            user_id=None,  # Cell docs don't have this field
            session_id=None,  # Cell docs don't have this field
            is_canonical=False,
        )

        # Execute via the adapter (this will orchestrate the ingestion_graph)
        try:
            result_pipeline_item = await cell_adapter.execute_in_pipeline(pipeline_item)

            # Update cell state based on execution result
            if result_pipeline_item.status == "completed":
                cell.status = CellStatus.COMPLETED
            elif result_pipeline_item.status == "error":
                cell.status = CellStatus.ERROR

            # Merge execution fragments into cell's fragments for traceability
            # The adapter may have added fragments to notebook_item_data during execution
            updates = {
                "status": cell.status.value,
                "fragments": cell.fragments,  # Updated fragments from execution
            }

        except Exception as exec_error:
            # Handle execution failure
            cell.status = CellStatus.ERROR
            cell.fragments.append(
                {
                    "tipo": "error",
                    "conteudo": f"Execution failed: {str(exec_error)}",
                    "metadata": {"execution_error": True},
                }
            )

            updates = {"status": CellStatus.ERROR.value, "fragments": cell.fragments}

            logger.error(f"Error during cell execution {cell_id}: {exec_error}")

        # Update cell in database
        # FIX Issue #1206 (2025-12-11): Cell documents use assignee_id, not user_id/session_id
        await db.update(
            "cells", cell_id, updates, user_id=None, session_id=None, is_canonical=False
        )

        # Retrieve updated cell
        try:
            updated_cell = await db.find_one(
                "cells",
                cell_id,
                current_user=current_user,
                model_class=Cell,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        logger.info(f"Cell {cell_id} executed with state {updated_cell.status}")
        return updated_cell

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing cell: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing cell: {str(e)}",
        )


@cells_router.post("/execute-ephemeral")
async def execute_ephemeral_cell(
    request: ExecuteEphemeralCellRequest,
    current_user: User = Depends(has_permission(["cells.execute_own"])),
):
    """
    Execute an ephemeral cell without persistence.

    This endpoint enables execution of cell logic defined in artifacts/canonical/cell_types/
    without requiring a persisted cell instance. Designed for:
    - Utility cells (like asset-prototyping-cell, png-generator-cell)
    - Cells marked with category: "ephemeral" in their type.json
    - One-off transformations and tool usage

    Required permission: `cells.execute_own` or `cells.execute_any`

    Args:
        request: ExecuteEphemeralCellRequest containing:
            - cell_type: The cell type ID (e.g., "asset-prototyping-cell")
            - input_data: Data to pass to the cell's execution logic

    Returns:
        Dict with execution results from the cell's backend logic

    Raises:
        404: Cell type not found
        400: Invalid cell type or missing execution logic
        500: Execution error
    """
    try:
        cell_type_id = request.cell_type
        input_data = request.input_data

        logger.info(f"Executing ephemeral cell: type={cell_type_id}, user={current_user.id}")

        # Step 1: Find the cell type definition in canonical artifacts
        # This validates that only trusted, canonical cell types can be executed
        try:
            cell_types = await db.find_many(
                "notebook_item_types",
                current_user=current_user,
                model_class=NotebookItemType,
            )
            logger.info(f"[execute_ephemeral_cell] Found {len(cell_types)} notebook_item_types from DB")
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        cell_type = None

        for ct in cell_types:
            if ct.id == cell_type_id:
                cell_type = ct
                break

        if not cell_type:
            logger.error(f"Cell type {cell_type_id} not found in canonical artifacts (searched {len(cell_types)} types)")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cell type '{cell_type_id}' not found",
            )

        # Step 2: Locate the cell's backend script
        # Only canonical cell types in artifacts/canonical/cell_types/ are trusted
        cell_backend_path = (
            BASE_DIR
            / "artifacts"
            / "canonical"
            / "cell_types"
            / cell_type_id
            / "backend"
            / "scripts"
            / "main.py"
        )

        if not cell_backend_path.exists():
            logger.error(
                f"Backend script not found for cell type {cell_type_id} at {cell_backend_path}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cell type '{cell_type_id}' does not have a backend execution script",
            )

        # Security: Validate the backend path is within canonical artifacts
        try:
            cell_backend_path = cell_backend_path.resolve()
            canonical_base = (BASE_DIR / "artifacts" / "canonical" / "cell_types").resolve()
            if not str(cell_backend_path).startswith(str(canonical_base)):
                logger.error(f"Security: Attempted path traversal for cell type {cell_type_id}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Invalid cell type path"
                )
        except Exception as e:
            logger.error(f"Path validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid cell type path"
            )

        logger.debug(f"Loading cell backend script from: {cell_backend_path}")

        # Step 3: Dynamically import the cell's execution module
        # Use module cache to prevent sys.modules pollution and improve performance
        module_key = f"cell_{cell_type_id}_main"

        if module_key in _cell_module_cache:
            logger.debug(f"Using cached module for cell type {cell_type_id}")
            cell_module = _cell_module_cache[module_key]
        else:
            spec = importlib.util.spec_from_file_location(module_key, cell_backend_path)
            if not spec or not spec.loader:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to load cell backend script for '{cell_type_id}'",
                )

            cell_module = importlib.util.module_from_spec(spec)

            # Add cell scripts directory to sys.path for relative imports
            scripts_dir = str(cell_backend_path.parent)
            sys.path.insert(0, scripts_dir)

            try:
                spec.loader.exec_module(cell_module)
            finally:
                # Clean up sys.path after module execution
                if scripts_dir in sys.path:
                    sys.path.remove(scripts_dir)

            # Cache the module (limited cache prevents memory leaks)
            # If cache grows too large, clear oldest entries (LRU-like behavior)
            if len(_cell_module_cache) > 100:
                # Remove oldest entry (first inserted)
                oldest_key = next(iter(_cell_module_cache))
                logger.debug(f"Module cache full, removing oldest: {oldest_key}")
                del _cell_module_cache[oldest_key]

            _cell_module_cache[module_key] = cell_module
            logger.debug(f"Cached module for cell type {cell_type_id}")

        # Step 4: Execute the cell logic
        # Standard interface: execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]
        if not hasattr(cell_module, "execute_cell"):
            logger.error(f"Cell backend script for {cell_type_id} missing 'execute_cell' function")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cell type '{cell_type_id}' backend script missing 'execute_cell' function",
            )

        execute_func = cell_module.execute_cell

        # Merge default_initial_data with user input_data and add current user context
        cell_data = {**cell_type.default_initial_data, **input_data, "user_id": current_user.id}

        logger.debug(f"Executing cell with data: {cell_data}")

        # Execute (handle both sync and async functions)
        if inspect.iscoroutinefunction(execute_func):
            result = await execute_func(cell_data)
        else:
            result = execute_func(cell_data)

        # Validate execution result and log appropriately
        if isinstance(result, dict):
            if result.get("success") == False:
                logger.error(f"Ephemeral cell {cell_type_id} failed: {result.get('error', 'Unknown error')}")
            elif result.get("fallback"):
                logger.warning(f"Ephemeral cell {cell_type_id} executed with fallback: {result.get('error', 'Unknown error')}")
            else:
                logger.info(f"Ephemeral cell {cell_type_id} executed successfully")
        else:
            logger.info(f"Ephemeral cell {cell_type_id} executed successfully")

        # Return the result directly - execute_cell() already returns the proper structure
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing ephemeral cell: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing ephemeral cell: {str(e)}",
        )


@cells_router.post("/run")
async def cell_run(
    request: CellRunRequest, current_user: User = Depends(has_permission(["cells.execute_own"]))
):
    """
    Execute complete cell lifecycle atomically (run method).

    This endpoint executes a cell's complete lifecycle in one atomic operation:
    setup → execute → save → show (if RenderableCell).

    Each step generates a fragment for tracing. On error, execution aborts and
    returns a failed result with error fragment.

    Required permission: `cells.execute_own` or `cells.execute_any`

    Example request:
    ```json
    {
        "cell_id": "png-generator-cell",
        "lifecycle": {
            "setup": {
                "mode": "production"
            },
            "execute": [
                {
                    "action": "generate",
                    "params": {"prompt": "a cute cat"}
                }
            ],
            "save": true
        }
    }
    ```

    Returns CellResult with:
    - id: Cell ID
    - status: 'pending', 'completed', or 'failed'
    - success: Boolean success flag
    - output: Output data from execution
    - fragments: List of execution fragments for tracing
    - error: Error message if failed
    - execution_time: Total execution time
    """
    try:
        logger.info(f"[CELL_RUN] Executing cell {request.cell_id}")

        # Validate lifecycle configuration
        lifecycle_config = request.lifecycle
        if not isinstance(lifecycle_config, dict):
            logger.error("[CELL_RUN] Invalid lifecycle configuration - must be dict")
            return {
                "id": request.cell_id,
                "status": "failed",
                "success": False,
                "error": "Invalid lifecycle configuration",
                "fragments": [
                    {
                        "type": "error",
                        "status": "failed",
                        "error": "Invalid lifecycle configuration",
                    }
                ],
                "execution_time": 0.0,
                "output": {},
            }

        # Validate cell exists
        try:
            cell = await db.find_one(
                "cells",
                request.cell_id,
                current_user=current_user,
                model_class=Cell,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not cell:
            logger.error(f"[CELL_RUN] Cell {request.cell_id} not found")
            return {
                "id": request.cell_id,
                "status": "failed",
                "success": False,
                "error": f"Cell {request.cell_id} not found",
                "fragments": [
                    {
                        "type": "error",
                        "status": "failed",
                        "error": f"Cell {request.cell_id} not found",
                    }
                ],
                "execution_time": 0.0,
                "output": {},
            }

        # Check ownership
        await check_resource_ownership(
            resource_user_id=cell.assignee_id,
            current_user=current_user,
            admin_permission="cells.execute_any",
        )

        # Get cell type to load backend
        cell_type_id = cell.notebook_item_type_id
        logger.info(f"[CELL_RUN] Loading backend for cell type: {cell_type_id}")

        # Load cell type definition
        try:
            cell_type = await db.find_one(
                "notebook_item_types",
                cell_type_id,
                current_user=current_user,
                model_class=NotebookItemType,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not cell_type:
            logger.error(f"[CELL_RUN] Cell type {cell_type_id} not found")
            return {
                "id": request.cell_id,
                "status": "failed",
                "success": False,
                "error": f"Cell type {cell_type_id} not found",
                "fragments": [
                    {
                        "type": "error",
                        "status": "failed",
                        "error": f"Cell type {cell_type_id} not found",
                    }
                ],
                "execution_time": 0.0,
                "output": {},
            }

        # Load cell backend module
        backend_path = (
            BASE_DIR
            / "artifacts"
            / "canonical"
            / "cell_types"
            / cell_type_id
            / "backend"
            / "scripts"
            / "main.py"
        )

        if not backend_path.exists():
            logger.error(f"[CELL_RUN] Backend not found at {backend_path}")
            return {
                "id": request.cell_id,
                "status": "failed",
                "success": False,
                "error": f"Backend script not found for cell type {cell_type_id}",
                "fragments": [
                    {
                        "type": "error",
                        "status": "failed",
                        "error": f"Backend script not found for cell type {cell_type_id}",
                    }
                ],
                "execution_time": 0.0,
                "output": {},
            }

        # Dynamically load cell module
        module_name = f"cell_{cell_type_id}_backend"

        if module_name in _cell_module_cache:
            cell_module = _cell_module_cache[module_name]
        else:
            spec = importlib.util.spec_from_file_location(module_name, backend_path)
            if not spec or not spec.loader:
                raise ServerException(f"Failed to load module spec for {cell_type_id}")

            cell_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cell_module)
            _cell_module_cache[module_name] = cell_module

        # Get cell instance (if cell implements BaseCell with run method)
        if hasattr(cell_module, "get_cell_instance"):
            cell_instance = cell_module.get_cell_instance()

            # Check if cell has run() method
            if hasattr(cell_instance, "run"):
                logger.info(f"[CELL_RUN] Calling cell.run() for {request.cell_id}")
                result = await cell_instance.run(request.lifecycle)
                logger.info(f"[CELL_RUN] Execution completed: {result.get('status')}")
                return result
            else:
                logger.warning(f"[CELL_RUN] Cell {cell_type_id} doesn't implement run() method")
                return {
                    "id": request.cell_id,
                    "status": "failed",
                    "success": False,
                    "error": f"Cell type {cell_type_id} does not implement run() method",
                    "fragments": [
                        {
                            "type": "error",
                            "status": "failed",
                            "error": f"Cell type {cell_type_id} does not implement run() method",
                        }
                    ],
                    "execution_time": 0.0,
                    "output": {},
                }
        else:
            logger.error(f"[CELL_RUN] Cell backend doesn't provide get_cell_instance()")
            return {
                "id": request.cell_id,
                "status": "failed",
                "success": False,
                "error": f"Cell backend does not provide get_cell_instance() function",
                "fragments": [
                    {
                        "type": "error",
                        "status": "failed",
                        "error": f"Cell backend does not provide get_cell_instance() function",
                    }
                ],
                "execution_time": 0.0,
                "output": {},
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CELL_RUN] Error: {str(e)}", exc_info=True)
        return {
            "id": request.cell_id,
            "status": "failed",
            "success": False,
            "error": str(e),
            "fragments": [{"type": "error", "status": "failed", "error": str(e)}],
            "execution_time": 0.0,
            "output": {},
        }


@cells_router.put("/{cell_id}/update", response_model=Cell)
@cells_router.put("/{cell_id}")
async def update_cell(
    cell_id: str,
    request: UpdateCellRequest,
    scope: str = "sandbox",  # Phase 1B: DEFAULT is sandbox
    current_user: User = Depends(has_permission(["cells.update_own"])),
):
    """
    Update a cell.

    Required permission: `cells.update_own` (own) or `cells.update_any` (any)

    **Phase 1B - Scope-Aware Update**:
    - `scope="sandbox"` (DEFAULT): Updates cell in sandbox only
    - `scope="published"`: Updates cell in MongoDB (requires explicit choice)

    Can update data (specific properties), state and/or fragments.
    """
    try:
        # Phase 1B: Find cell using unified lookup
        try:
            cell = await db.find_one(
                "cells",
                cell_id,
                current_user=current_user,
                model_class=Cell,
                resource_owner_id=current_user.id,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not cell:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Cell {cell_id} not found"
            )

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=cell.assignee_id,
            current_user=current_user,
            admin_permission="cells.update_any",
        )

        # Prepare updates
        updates = {}

        if request.initial_data is not None:
            updates["initial_data"] = request.initial_data

        if request.status:
            updates["status"] = request.status.value

        if request.fragments:
            updates["fragments"] = request.fragments

        # Update semantic fields
        if request.title is not None:
            updates["title"] = request.title

        if request.content is not None:
            updates["content"] = request.content

        # Update metadata and history (Issue #1206)
        if request.metadata is not None:
            # Validate metadata is a dict
            if not isinstance(request.metadata, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="metadata must be a dictionary"
                )
            updates["metadata"] = request.metadata

        if request.history is not None:
            # Validate history is a list
            if not isinstance(request.history, list):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="history must be a list"
                )
            updates["history"] = request.history

        logger.info(f"Updating cell {cell_id} with updates: {updates}, scope: {scope}")

        # Unified update - routing via resource_owner_id
        success = await db.update(
            collection="cells",
            doc_id=cell_id,
            updates=updates,
            current_user=current_user,
            resource_owner_id=current_user.id if scope == "sandbox" else None,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update cell"
            )

        logger.info(f"Cell {cell_id} updated successfully in {scope}")
        
        # Retrieve updated cell
        try:
            updated_cell = await db.find_one(
                "cells",
                cell_id,
                current_user=current_user,
                model_class=Cell,
                resource_owner_id=current_user.id,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        logger.info(f"Cell {cell_id} updated")
        return updated_cell

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating cell: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating cell: {str(e)}",
        )


@cells_router.delete("/{cell_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cell(
    cell_id: str,
    scope: str = "sandbox",  # Phase 1B: DEFAULT is sandbox (local-first)
    current_user: User = Depends(has_permission(["cells.delete_own"]))
):
    """
    Delete a cell.

    Required permission: `cells.delete_own` (own) or `cells.delete_any` (any)

    **Phase 1B - Scope-Aware Delete**:
    - `scope="sandbox"` (DEFAULT): Deletes cell from sandbox only
    - `scope="published"`: Deletes cell from MongoDB (requires explicit choice)
    """
    try:
        # Phase 1B: Find cell using unified lookup
        try:
            cell = await db.find_one(
                "cells",
                cell_id,
                current_user=current_user,
                model_class=Cell,
                resource_owner_id=current_user.id,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not cell:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Cell {cell_id} not found"
            )

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=cell.assignee_id,
            current_user=current_user,
            admin_permission="cells.delete_any",
        )

        # Phase 1B: Use scope-aware delete
        if scope == "sandbox":
            # Delete from sandbox (local, private)
            success = db._sandbox.delete_from_sandbox(current_user.id, cell_id)
            if success:
                await db._invalidate_l1_cache("cells", current_user.id)
        else:
            # Delete from MongoDB (published)
            success = await db.delete(
                "cells",
                cell_id,
                user_id=None,
                session_id=None,
                is_canonical=False,
            )
            if success:
                await db._invalidate_l1_cache("cells", current_user.id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete cell from {scope}"
            )

        logger.info(f"Cell {cell_id} deleted from {scope}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting cell: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting cell: {str(e)}",
        )


@cells_router.post("/{cell_id}/publish", status_code=status.HTTP_200_OK)
async def publish_cell(
    cell_id: str,
    current_user: User = Depends(has_permission(["cells.update_own"])),
):
    """
    Publish cell from sandbox to MongoDB (EXPLICIT user action).

    Required permission: `cells.update_own` (own) or `cells.update_any` (any)

    **Phase 1B - Explicit Publication Workflow**:
    1. Finds cell in sandbox (user's private workspace)
    2. Validates ownership and permissions
    3. Moves cell from sandbox to MongoDB (shared, persistent)
    4. Optionally keeps sandbox copy (for local reference)

    **Privacy Guarantee**:
    - Only explicitly published cells reach MongoDB
    - Sandbox cells NEVER auto-sync
    - User controls what gets shared

    Returns:
        dict: Publication status with IDs and locations
    """
    try:
        # Phase 1B: Find cell in sandbox first
        try:
            cell = await db.find_one(
                "cells",
                cell_id,
                current_user=current_user,
                model_class=Cell,
                resource_owner_id=current_user.id,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not cell:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cell {cell_id} not found in sandbox"
            )

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=cell.assignee_id,
            current_user=current_user,
            admin_permission="cells.update_any",
        )

        # Publish to MongoDB: read from sandbox → insert to runtime
        try:
            # Read from sandbox
            sandbox_cell = await db.find_one(
                "cells",
                cell_id,
                current_user=current_user,
                model_class=Cell,
                resource_owner_id=current_user.id,
            )

            if not sandbox_cell:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cell not found in sandbox",
                )

            # Insert into MongoDB (without resource_owner_id → runtime)
            published_id = await db.insert(
                "cells",
                sandbox_cell.model_dump(mode="json"),
                current_user=current_user,
                resource_owner_id=None,  # ← Routes to runtime/MongoDB
            )

            if not published_id:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to publish cell"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error publishing cell: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to publish cell"
            )

        logger.info(f"Cell {cell_id} published successfully (user={current_user.id})")

        return {
            "id": published_id,
            "status": "published",
            "location": "mongodb",
            "sandbox_copy_kept": True,
            "message": f"Cell {cell_id} successfully published to MongoDB"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing cell: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error publishing cell: {str(e)}",
        )


@cells_router.post(
    "/generate", response_model=CellGenerationResponse, status_code=status.HTTP_202_ACCEPTED
)
async def generate_cell_code(
    request: CellGenerationRequest, current_user: User = Depends(has_permission(["cells.generate"]))
):
    """
    Generate code for a cell using AI (Cell Factory MVP 1).

    This endpoint initiates AI-driven code generation for an unclassified cell.
    The generation process is asynchronous and publishes progress updates via
    the Event Bus.

    Required permission: `cells.generate`

    Workflow:
    1. Validate cell exists and user has access
    2. Publish `cell/generate/request` event to Event Bus
    3. Backend Cell Generation Service processes request
    4. Progress updates published to `cell/generate/progress`
    5. Final result published to `cell/generate/response`

    Example request:
    ```json
    {
        "cell_id": "uuid-of-unclassified-cell",
        "content": "Create a bar chart showing sales by month",
        "format": "svg",
        "model": "gpt-4"
    }
    ```

    Returns HTTP 202 Accepted immediately. Client should subscribe to Event Bus
    for progress and completion events.
    """
    # DEBUG LOG: Request entry
    logger.info("=" * 80)
    logger.info("[GENERATE ENDPOINT] 🚀 Request RECEIVED")
    logger.info(f"📍 Cell ID: {request.cell_id}")
    logger.info(f"📝 Content length: {len(request.content) if request.content else 0}")
    logger.info(f"🎨 Format: {request.format}")
    logger.info(f"🤖 Model: {request.model}")
    logger.info(
        f"👤 User: {current_user.id} (Email: {current_user.email}, Name: {current_user.name})"
    )
    logger.info(f"⏰ Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 80)

    try:
        # DEBUG LOG: Cell lookup
        logger.info(f"[GENERATE ENDPOINT] 🔍 Looking up cell {request.cell_id} in database")

        # Validate cell exists
        try:
            cell = await db.find_one(
                "cells",
                request.cell_id,
                current_user=current_user,
                model_class=Cell,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not cell:
            logger.error(f"[GENERATE ENDPOINT] ❌ Cell {request.cell_id} NOT FOUND in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Cell {request.cell_id} not found"
            )

        logger.info(f"[GENERATE ENDPOINT] ✅ Cell {request.cell_id} found")
        logger.info(f"📊 Cell details: type={cell.type}, assignee={cell.assignee_id}")

        # DEBUG LOG: Ownership check
        logger.info(f"[GENERATE ENDPOINT] 🔐 Checking ownership for user {current_user.id}")

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=cell.assignee_id,
            current_user=current_user,
            admin_permission="cells.generate_any",
        )

        logger.info(f"[GENERATE ENDPOINT] ✅ Ownership validated")

        # DEBUG LOG: Service initialization
        logger.info(f"[GENERATE ENDPOINT] 🏭 Getting generation service")

        # Use Cell Generation Service to generate code
        gen_service = await get_generation_service()

        logger.info(f"[GENERATE ENDPOINT] ✅ Generation service ready")
        logger.info(f"[GENERATE ENDPOINT] 🤖 Calling gen_service.generate_cell_code()")

        result = await gen_service.generate_cell_code(request, cell)

        logger.info(f"[GENERATE ENDPOINT] ✅ Generation service returned")
        logger.info(f"📊 Result: {result}")

        # DEBUG LOG: Validation step
        logger.info(f"[GENERATE ENDPOINT] ✔️ Getting validation service")

        # Automatically validate generated code
        val_service = await get_validation_service()

        logger.info(f"[GENERATE ENDPOINT] 🔍 Validating generated code")

        is_valid, errors = await val_service.validate_cell(cell, auto_correct=True)

        logger.info(
            f"[GENERATE ENDPOINT] ✅ Cell generation completed for cell {request.cell_id}. "
            f"Validation: {'passed' if is_valid else 'failed'}"
        )

        response = CellGenerationResponse(
            success=True,
            cell_id=request.cell_id,
            stream_available=True,
            message=f"Code generation completed for cell {request.cell_id}. "
            f"Validation: {'passed' if is_valid else 'requires review'}. "
            f"Generated {result.get('refs_count', 0)} refs.",
        )

        logger.info(f"[GENERATE ENDPOINT] 📤 Returning success response")
        logger.info("=" * 80)

        return response

    except HTTPException as http_exc:
        logger.error(
            f"[GENERATE ENDPOINT] ⚠️ HTTP Exception: {http_exc.status_code} - {http_exc.detail}"
        )
        logger.error("=" * 80)
        raise
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"[GENERATE ENDPOINT] 💥 UNEXPECTED EXCEPTION")
        logger.error(f"Type: {type(e).__name__}")
        logger.error(f"Message: {str(e)}")
        logger.error(f"Stack trace:", exc_info=True)
        logger.error("=" * 80)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error initiating cell generation: {str(e)}",
        )


@cells_router.post(
    "/promote", response_model=CellPromotionResponse, status_code=status.HTTP_201_CREATED
)
async def promote_cell(
    request: CellPromotionRequest, current_user: User = Depends(has_permission(["cells.promote"]))
):
    """
    Promote an unclassified cell to a typed cell (Cell Factory MVP 1).

    This endpoint promotes a validated unclassified cell with dynamic refs
    to a new typed cell. The process includes:
    - Creating a new NotebookItemType definition
    - Migrating assets from OPFS to MongoDB GridFS
    - Registering the new cell type in the system
    - Updating the Layout Book with the new cell type
    - Creating a new cell instance of the new type

    Required permission: `cells.promote`

    Workflow:
    1. Validate cell exists and has validated dynamic refs
    2. Publish `cell/promote/request` event to Event Bus
    3. Backend Cell Promotion Service processes request:
       a. Create NotebookItemType definition
       b. Migrate OPFS assets to MongoDB GridFS
       c. Register new cell type
       d. Update Layout Book
       e. Create new cell instance
    4. Publish `cell/promote/complete` event
    5. Return promotion response

    Example request:
    ```json
    {
        "cell_id": "uuid-of-unclassified-cell",
        "new_type_name": "custom-sales-chart",
        "new_type_description": "Interactive sales chart component",
        "category": "generated"
    }
    ```

    Returns HTTP 201 Created with the new cell type and cell instance IDs.
    """
    try:
        from ..models import UnclassifiedCellData, DynamicRef

        # Validate cell exists
        try:
            cell = await db.find_one(
                "cells",
                request.cell_id,
                current_user=current_user,
                model_class=Cell,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not cell:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Cell {request.cell_id} not found"
            )

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=cell.assignee_id,
            current_user=current_user,
            admin_permission="cells.promote_any",
        )

        # Validate cell has dynamic refs
        cell_data = cell.initial_data or {}
        if isinstance(cell_data, dict):
            dynamic_refs = cell_data.get("dynamic_refs", [])
        else:
            dynamic_refs = []

        if not dynamic_refs:
            raise ValidationException(
                "Cell has no dynamic refs. Generate code first before promoting.",
                field="dynamic_refs",
            )

        # Validate all refs are validated
        unvalidated_refs = [
            ref for ref in dynamic_refs if isinstance(ref, dict) and not ref.get("validated", False)
        ]
        if unvalidated_refs:
            raise ValidationException(
                f"Cell has {len(unvalidated_refs)} unvalidated refs. All refs must be validated before promotion.",
                field="dynamic_refs",
            )

        # Use Cell Promotion Service to promote cell
        # Use Cell Promotion Service to promote cell
        promo_service = await get_promotion_service()
        promotion_response = await promo_service.promote_cell(request, cell, current_user)

        logger.info(f"Cell promotion completed for cell {request.cell_id}")

        return promotion_response

    except HTTPException:
        raise
    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"Error promoting cell: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error promoting cell: {str(e)}",
        )
