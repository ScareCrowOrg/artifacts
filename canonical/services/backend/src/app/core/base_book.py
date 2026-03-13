"""
BaseBook - Abstract Base Class for Backend Books

This module defines the BaseBook ABC that provides DAG-based orchestration
for composing multiple cells into workflows.

Part of BaseCell v1.0 Framework - Book Pattern Implementation
Issue: BaseCell/BaseBook Instance Composition Pattern

Architecture Notes:
- Books are orchestrators that coordinate cell execution
- Books define execution order via DAG
- Books handle state transfer between cells
- Books should not contain business logic (delegate to cells)
- Books can optionally reference their Book runtime instance for metadata access
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .base_cell import (
    CellMetadata,
    CellResult,
    EnvironmentConfig,
    HealthCheckResult,
    HealthStatus,
)

# ============ BOOK-SPECIFIC TYPES ============


class DAGNode:
    """Node in the execution DAG"""

    def __init__(
        self,
        id: str,
        cell_type: str,
        input: Dict[str, Any],
        label: Optional[str] = None,
        optional: bool = False,
    ):
        self.id = id
        self.cell_type = cell_type
        self.input = input
        self.label = label
        self.optional = optional


class DAGEdge:
    """Edge in the execution DAG"""

    def __init__(
        self,
        from_node: str,
        to_node: str,
        field: Optional[str] = None,
        target_field: Optional[str] = None,
    ):
        self.from_node = from_node
        self.to_node = to_node
        self.field = field
        self.target_field = target_field


class DAGDefinition:
    """DAG definition for book execution"""

    def __init__(self, nodes: List[DAGNode], edges: List[DAGEdge]):
        self.nodes = nodes
        self.edges = edges


class BookResult(CellResult):
    """
    Result of book execution
    Extends CellResult with book-specific information
    """

    def __init__(
        self,
        success: bool,
        output: Dict[str, Any],
        node_results: Optional[Dict[str, CellResult]] = None,
        execution_trace: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ):
        super().__init__(success=success, output=output, **kwargs)
        self.node_results = node_results or {}
        self.execution_trace = execution_trace or []


# ============ MAIN INTERFACE ============


class BaseBook(ABC):
    """
    Abstract base class for backend books (Python)

    Books are orchestrators that compose multiple cells into workflows.
    They define execution order via DAG and handle state transfer between cells.

    Key Differences from Cells:
    - Cells are atomic executors (do one thing)
    - Books are orchestrators (coordinate multiple cells)
    - Cells should not contain other cells
    - Books should not contain business logic (delegate to cells)

    Instance Composition Pattern:
    - BaseBook can optionally reference its Book runtime instance
    - This enables access to metadata (assignee_id, initial_data, fragments, cells, etc.)
    - Follows the PipelineItem → NotebookItem composition pattern
    - The instance is optional to maintain backward compatibility

    Responsibilities:
    - Define DAG structure (nodes + edges)
    - Instantiate and manage cell lifecycles
    - Execute cells in correct order
    - Transfer state between cells
    - Aggregate results

    Lifecycle:
    1. setup(config) - Initialize all cells in the DAG
    2. execute(input) - Execute DAG with topological sort
    3. teardown() - Cleanup all cells

    Example (Context-Aware Book):
        class ImageProcessingBook(BaseBook):
            def __init__(self, book_instance: Optional['Book'] = None):
                self.book_instance = book_instance

            def get_dag(self) -> DAGDefinition:
                return DAGDefinition(
                    nodes=[
                        DAGNode(
                            id='generate',
                            cell_type='png-generator',
                            input={'prompt': '{{bookInput.prompt}}'}
                        ),
                        DAGNode(
                            id='enhance',
                            cell_type='image-enhancer',
                            input={'image': '{{outputs.generate.png}}'}
                        )
                    ],
                    edges=[
                        DAGEdge(from_node='generate', to_node='enhance')
                    ]
                )

            async def describe(self) -> CellMetadata:
                return CellMetadata(
                    id='image-processing-book',
                    name='Image Processing Book',
                    version='1.0.0',
                    description='Generate and enhance images',
                    inputs={'prompt': {'type': 'string', 'required': True}},
                    outputs={'enhancedImage': {'type': 'string'}},
                    tags=['image', 'book', 'composition']
                )
    """

    def __init__(self, book_instance: Optional[Any] = None):
        """
        Initialize the BaseBook.

        Args:
            book_instance: Optional Book instance for metadata access.
                          When provided, enables context-aware execution.
                          When None, book operates independently.
        """
        self.book_instance = book_instance

    # ===== ABSTRACT METHODS (must implement) =====

    @abstractmethod
    async def execute(self, input: Dict[str, Any]) -> BookResult:
        """
        Execute the book's DAG workflow

        Orchestrates execution of all cells in the DAG according to
        dependency order. Handles state transfer and error propagation.

        Args:
            input: Input data for the book

        Returns:
            BookResult with success, output, node_results, execution_trace

        Raises:
            Exception: If execution fails catastrophically
        """

    @abstractmethod
    async def describe(self) -> CellMetadata:
        """
        Describe the book's capabilities

        Returns metadata about the book including inputs, outputs,
        composed cells, and execution characteristics.

        Returns:
            CellMetadata with inputs/outputs/tags

        Example:
            return CellMetadata(
                id='workflow-book',
                name='Workflow Book',
                version='1.0.0',
                description='Multi-step workflow',
                inputs={'data': {'type': 'object', 'required': True}},
                outputs={'result': {'type': 'object'}},
                tags=['workflow', 'book', 'orchestration']
            )
        """

    @abstractmethod
    def get_dag(self) -> DAGDefinition:
        """
        Get the DAG definition for this book

        Defines the workflow structure with nodes and edges.
        Subclasses must implement this to define their orchestration.

        Returns:
            DAGDefinition with nodes and edges

        Example:
            return DAGDefinition(
                nodes=[
                    DAGNode(id='step1', cell_type='validator', input={'data': '{{bookInput.data}}'}),
                    DAGNode(id='step2', cell_type='processor', input={'data': '{{outputs.step1.validated}}'})
                ],
                edges=[
                    DAGEdge(from_node='step1', to_node='step2')
                ]
            )
        """

    # ===== LIFECYCLE METHODS (must implement) =====

    async def setup(self, config: EnvironmentConfig) -> None:
        """
        Setup all cells in the DAG

        Initializes all cells that will be used in execution.
        Should be called once before first execute().

        Default implementation: no-op
        Override if book needs initialization.

        Args:
            config: Environment configuration

        Example:
            async def setup(self, config: EnvironmentConfig) -> None:
                # Initialize cell registry or resources
                self.cell_instances = {}
                for node in self.get_dag().nodes:
                    cell = create_cell(node.cell_type)
                    await cell.setup(config)
                    self.cell_instances[node.id] = cell
        """

    async def teardown(self) -> None:
        """
        Teardown all cells in the DAG

        Cleans up all cells that were initialized.
        Should be called once when book is no longer needed.

        Default implementation: no-op
        Override if book allocated resources in setup().

        Example:
            async def teardown(self) -> None:
                # Cleanup all cells
                for cell in self.cell_instances.values():
                    await cell.teardown()
                self.cell_instances.clear()
        """

    async def health_check(self) -> HealthCheckResult:
        """
        Check if book can execute

        Aggregates health checks from all cells in the DAG.
        Book is healthy only if all cells are healthy.

        Default implementation: always healthy
        Override if book has dependencies to check.

        Returns:
            HealthCheckResult with status and can_execute flag

        Example:
            async def health_check(self) -> HealthCheckResult:
                # Check all cells
                for node in self.get_dag().nodes:
                    cell = self.cell_instances.get(node.id)
                    if cell:
                        result = await cell.health_check()
                        if result.status != HealthStatus.HEALTHY:
                            return HealthCheckResult(
                                status=HealthStatus.DEGRADED,
                                reason=f"Cell {node.id} is {result.status.value}"
                            )

                return HealthCheckResult(status=HealthStatus.HEALTHY)
        """
        return HealthCheckResult(status=HealthStatus.HEALTHY)


# ============ HELPER FUNCTIONS ============


def validate_dag(dag: DAGDefinition) -> List[str]:
    """
    Validates DAG structure
    Checks for cycles, missing nodes, invalid edges, etc.

    Args:
        dag: DAG definition to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check for empty DAG
    if not dag.nodes:
        errors.append("DAG must have at least one node")
        return errors

    # Build node ID set
    node_ids = {node.id for node in dag.nodes}

    # Check for duplicate node IDs
    if len(node_ids) != len(dag.nodes):
        errors.append("DAG contains duplicate node IDs")

    # Validate edges reference valid nodes
    for edge in dag.edges:
        if edge.from_node not in node_ids:
            errors.append(f"Edge references non-existent source node: {edge.from_node}")
        if edge.to_node not in node_ids:
            errors.append(f"Edge references non-existent target node: {edge.to_node}")

    # Check for cycles using DFS
    visited = set()
    recursion_stack = set()

    # Build adjacency list
    adjacency = {node.id: [] for node in dag.nodes}
    for edge in dag.edges:
        adjacency[edge.from_node].append(edge.to_node)

    def has_cycle(node_id: str) -> bool:
        visited.add(node_id)
        recursion_stack.add(node_id)

        for neighbor in adjacency.get(node_id, []):
            if neighbor not in visited:
                if has_cycle(neighbor):
                    return True
            elif neighbor in recursion_stack:
                return True

        recursion_stack.remove(node_id)
        return False

    for node in dag.nodes:
        if node.id not in visited:
            if has_cycle(node.id):
                errors.append("DAG contains a cycle - must be acyclic")
                break

    return errors


def topological_sort(dag: DAGDefinition) -> List[str]:
    """
    Performs topological sort on DAG
    Returns nodes in execution order

    Args:
        dag: DAG definition to sort

    Returns:
        List of node IDs in execution order

    Raises:
        ValueError: If DAG is invalid or contains cycles
    """
    # Validate first
    errors = validate_dag(dag)
    if errors:
        raise ValueError(f"Invalid DAG: {', '.join(errors)}")

    # Build adjacency list and in-degree map
    adjacency = {node.id: [] for node in dag.nodes}
    in_degree = {node.id: 0 for node in dag.nodes}

    for edge in dag.edges:
        adjacency[edge.from_node].append(edge.to_node)
        in_degree[edge.to_node] += 1

    # Kahn's algorithm for topological sort
    queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
    result = []

    while queue:
        node_id = queue.pop(0)
        result.append(node_id)

        for neighbor in adjacency.get(node_id, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # If result doesn't contain all nodes, there's a cycle
    if len(result) != len(dag.nodes):
        raise ValueError("DAG contains a cycle")

    return result
