/**
 * @file BaseBook.ts
 * @description BaseBook - DAG-based orchestration interface for composing cells
 * 
 * This file defines the BaseBook interface that enables orchestration of multiple
 * cells via DAG (Directed Acyclic Graph) execution patterns. Books separate
 * orchestration concerns from atomic cell execution, enabling:
 * - Reusable cell composition
 * - Declarative workflow definition
 * - Automatic state transfer between cells
 * - Parallel execution where possible
 * 
 * Part of BaseCell v1.0 Framework - Book Pattern Implementation
 * Issue: Implement BaseBook for DAG-based Cell Orchestration
 */

import type { 
  BaseCell, 
  CellResult, 
  EnvironmentConfig, 
  HealthCheckResult,
  CellMetadata 
} from './BaseCell'

// ============ DAG TYPES ============

/**
 * Node in the execution DAG
 * Each node represents a cell execution step
 */
export interface DAGNode {
  /** Unique identifier for this node */
  id: string
  
  /** Cell type identifier (must match a registered cell) */
  cellType: string
  
  /** Input mapping - can reference outputs from previous nodes */
  input: Record<string, any> | ((context: ExecutionContext) => Record<string, any>)
  
  /** Optional label for debugging/visualization */
  label?: string
  
  /** Whether this node can fail without failing the entire book */
  optional?: boolean
}

/**
 * Edge in the execution DAG
 * Defines dependency relationships between nodes
 */
export interface DAGEdge {
  /** Source node ID (dependency) */
  from: string
  
  /** Target node ID (dependent) */
  to: string
  
  /** Optional output field to pass from source to target */
  field?: string
  
  /** Optional target field name (defaults to same as source field) */
  targetField?: string
}

/**
 * DAG definition for book execution
 */
export interface DAGDefinition {
  /** All nodes in the DAG */
  nodes: DAGNode[]
  
  /** All edges defining dependencies */
  edges: DAGEdge[]
}

/**
 * Execution context passed between nodes
 * Accumulates outputs from completed nodes
 */
export interface ExecutionContext {
  /** Outputs from completed nodes, keyed by node ID */
  outputs: Record<string, any>
  
  /** Input data provided to the book */
  bookInput: Record<string, any>
  
  /** Execution metadata */
  metadata: {
    startTime: number
    currentNode?: string
    completedNodes: string[]
    failedNodes: string[]
  }
}

/**
 * Result of book execution
 * Extends CellResult with book-specific information
 */
export interface BookResult extends CellResult {
  /** Results from individual nodes */
  nodeResults?: Record<string, CellResult>
  
  /** Final aggregated output from book */
  output: Record<string, any>
  
  /** DAG execution trace for debugging */
  executionTrace?: {
    nodeId: string
    startTime: number
    endTime: number
    success: boolean
    error?: string
  }[]
}

// ============ BOOK REGISTRY ============

/**
 * Cell factory function
 * Creates instances of cells for use in books
 */
export type CellFactory = () => BaseCell

/**
 * Registry of available cells
 * Books use this to instantiate cells by type
 */
export interface CellRegistry {
  /** Register a cell type */
  register(cellType: string, factory: CellFactory): void
  
  /** Create an instance of a registered cell */
  create(cellType: string): BaseCell
  
  /** Check if a cell type is registered */
  has(cellType: string): boolean
  
  /** Get all registered cell types */
  listTypes(): string[]
}

// ============ BASE BOOK INTERFACE ============

/**
 * Execution mode for books
 * - 'dag': Declarative, parallel execution via DAG definition
 * - 'script': Imperative, flexible execution with custom execute() method
 * - 'hybrid': Combination of both - script with DAG helper methods
 */
export type ExecutionMode = 'dag' | 'script' | 'hybrid'

/**
 * BaseBook - Abstract orchestrator for composing cells via DAG or Script
 * 
 * Books are orchestrators that compose multiple cells into workflows.
 * They support three execution modes:
 * 1. DAG Mode: Declarative, parallel execution (default for backward compatibility)
 * 2. Script Mode: Imperative, flexible execution with loops/conditionals
 * 3. Hybrid Mode: Best of both - parallel DAG execution within script logic
 * 
 * Key Differences from Cells:
 * - Cells are atomic executors (do one thing)
 * - Books are orchestrators (coordinate multiple cells)
 * - Cells should not contain other cells
 * - Books should not contain business logic (delegate to cells)
 * 
 * Responsibilities:
 * - Declare execution mode (getExecutionMode)
 * - Define workflow structure (DAG for 'dag' mode, execute() for 'script'/'hybrid')
 * - Instantiate and manage cell lifecycles
 * - Execute cells in correct order
 * - Transfer state between cells
 * - Aggregate results
 * 
 * Instance Composition Pattern:
 * BaseBook can optionally reference its Book runtime instance to access metadata
 * (assignee_id, initial_data, fragments, cells, etc.) when needed.
 * This follows the PipelineItem → NotebookItem composition pattern.
 * 
 * Lifecycle:
 * 1. setup(config) - Initialize all cells
 * 2. execute(input) - Execute workflow (DAG or Script based on mode)
 * 3. teardown() - Cleanup all cells
 * 
 * @example DAG Mode
 * ```typescript
 * class ImageProcessingBook implements BaseBook {
 *   getExecutionMode(): ExecutionMode { return 'dag' }
 *   
 *   getDAG(): DAGDefinition {
 *     return {
 *       nodes: [
 *         { id: 'generate', cellType: 'png-generator', input: (ctx) => ({ prompt: ctx.bookInput.prompt }) },
 *         { id: 'enhance', cellType: 'image-enhancer', input: (ctx) => ({ image: ctx.outputs.generate.png }) }
 *       ],
 *       edges: [{ from: 'generate', to: 'enhance' }]
 *     }
 *   }
 * }
 * ```
 * 
 * @example Script Mode
 * ```typescript
 * class AutomationBook implements BaseBook {
 *   getExecutionMode(): ExecutionMode { return 'script' }
 *   
 *   async execute(input: Record<string, any>): Promise<BookResult> {
 *     // Imperative logic with loops, conditionals, etc.
 *     let retries = 0
 *     while (retries < 3) {
 *       const result = await this.runCell('planning-cell', input)
 *       if (result.confidence > 0.8) break
 *       retries++
 *     }
 *     return { success: true, output: result }
 *   }
 * }
 * ```
 * 
 * @example Hybrid Mode
 * ```typescript
 * class NPCGenerationBook implements BaseBook {
 *   getExecutionMode(): ExecutionMode { return 'hybrid' }
 *   
 *   async execute(input: Record<string, any>): Promise<BookResult> {
 *     // Script logic to prepare
 *     const config = await this.planGeneration(input)
 *     
 *     // Use DAG for parallel generation
 *     const results = await this.executeDAG(config.dag, { bookInput: input })
 *     
 *     // Script logic to post-process
 *     return this.validateAndAggregate(results)
 *   }
 * }
 * ```
 */
export interface BaseBook {
  // ===== INSTANCE COMPOSITION (Optional) =====
  
  /**
   * Optional reference to the Book runtime instance
   * 
   * When present, provides access to instance metadata:
   * - assignee_id: Who owns this execution
   * - initial_data: Initial configuration
   * - fragments: Execution history
   * - refs: File references
   * - name: Book name
   * - cells: UUIDs of cells in this book
   * 
   * This follows the PipelineItem → NotebookItem composition pattern.
   * The field is optional to maintain backward compatibility and support
   * both context-aware and utility books.
   * 
   * @example
   * ```typescript
   * // Context-aware book
   * class WorkflowBook implements BaseBook {
   *   book_instance?: Book
   *   
   *   async execute(input: Record<string, any>): Promise<BookResult> {
   *     const owner = this.book_instance?.assignee_id
   *     const config = this.book_instance?.initial_data
   *     // Use metadata in execution...
   *   }
   * }
   * ```
   */
  book_instance?: {
    id: string
    assignee_id: string
    name: string
    description: string
    initial_data: Record<string, any>
    fragments: Array<string | Record<string, any>>
    refs: Record<string, string[]>
    cells: string[]
    children?: string[]
    created_at?: string
    updated_at?: string
    [key: string]: any
  }
  
  // ===== EXECUTION MODE =====
  
  /**
   * Get the execution mode for this book
   * 
   * Determines how the book's workflow is executed:
   * - 'dag': Declarative execution via getDAG() (default)
   * - 'script': Imperative execution via execute() method
   * - 'hybrid': Combination - execute() can use executeDAG() helper
   * 
   * @returns Execution mode ('dag', 'script', or 'hybrid')
   */
  getExecutionMode(): ExecutionMode
  
  // ===== EXECUTION =====
  
  /**
   * Execute the book's workflow
   * 
   * - DAG Mode: Auto-generated from getDAG() (orchestrates cells via topological sort)
   * - Script Mode: Custom implementation with imperative logic
   * - Hybrid Mode: Custom implementation that can use executeDAG() helper
   * 
   * @param input - Input data for the book
   * @returns Promise resolving to BookResult
   */
  execute(input: Record<string, any>): Promise<BookResult>
  
  /**
   * Describe the book's capabilities
   * 
   * Returns metadata about the book including inputs, outputs,
   * composed cells, and execution characteristics.
   * 
   * @returns Promise resolving to CellMetadata
   */
  describe(): Promise<CellMetadata>
  
  /**
   * Get the DAG definition for this book
   * 
   * REQUIRED for mode='dag'
   * OPTIONAL for mode='script' (not used)
   * OPTIONAL for mode='hybrid' (used by executeDAG() helper)
   * 
   * @returns DAG definition with nodes and edges, or undefined
   */
  getDAG?(): DAGDefinition
  
  /**
   * Setup all cells in the DAG
   * 
   * Initializes all cells that will be used in execution.
   * Should be called once before first execute().
   * 
   * @param config - Environment configuration
   * @returns Promise that resolves when setup is complete
   */
  setup(config: EnvironmentConfig): Promise<void>
  
  /**
   * Teardown all cells in the DAG
   * 
   * Cleans up all cells that were initialized.
   * Should be called once when book is no longer needed.
   * 
   * @returns Promise that resolves when teardown is complete
   */
  teardown(): Promise<void>
  
  /**
   * Check if book can execute
   * 
   * Aggregates health checks from all cells in the DAG.
   * Book is healthy only if all cells are healthy.
   * 
   * @returns Promise resolving to HealthCheckResult
   */
  health_check(): Promise<HealthCheckResult>
}

// ============ DAG UTILITIES ============

/**
 * Validates DAG structure
 * Checks for cycles, missing nodes, invalid edges, etc.
 * 
 * @param dag - DAG definition to validate
 * @returns Array of validation errors (empty if valid)
 */
export function validateDAG(dag: DAGDefinition): string[] {
  const errors: string[] = []
  
  // Check for empty DAG
  if (dag.nodes.length === 0) {
    errors.push('DAG must have at least one node')
    return errors
  }
  
  // Build node ID set
  const nodeIds = new Set(dag.nodes.map(n => n.id))
  
  // Check for duplicate node IDs
  if (nodeIds.size !== dag.nodes.length) {
    errors.push('DAG contains duplicate node IDs')
  }
  
  // Validate edges reference valid nodes
  for (const edge of dag.edges) {
    if (!nodeIds.has(edge.from)) {
      errors.push(`Edge references non-existent source node: ${edge.from}`)
    }
    if (!nodeIds.has(edge.to)) {
      errors.push(`Edge references non-existent target node: ${edge.to}`)
    }
  }
  
  // Check for cycles using DFS
  const visited = new Set<string>()
  const recursionStack = new Set<string>()
  
  // Build adjacency list
  const adjacency = new Map<string, string[]>()
  for (const node of dag.nodes) {
    adjacency.set(node.id, [])
  }
  for (const edge of dag.edges) {
    adjacency.get(edge.from)?.push(edge.to)
  }
  
  function hasCycle(nodeId: string): boolean {
    visited.add(nodeId)
    recursionStack.add(nodeId)
    
    const neighbors = adjacency.get(nodeId) || []
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) {
        if (hasCycle(neighbor)) {
          return true
        }
      } else if (recursionStack.has(neighbor)) {
        return true
      }
    }
    
    recursionStack.delete(nodeId)
    return false
  }
  
  for (const node of dag.nodes) {
    if (!visited.has(node.id)) {
      if (hasCycle(node.id)) {
        errors.push('DAG contains a cycle - must be acyclic')
        break
      }
    }
  }
  
  return errors
}

/**
 * Performs topological sort on DAG
 * Returns nodes in execution order
 * 
 * @param dag - DAG definition to sort
 * @returns Array of node IDs in execution order
 * @throws Error if DAG is invalid or contains cycles
 */
export function topologicalSort(dag: DAGDefinition): string[] {
  // Validate first
  const errors = validateDAG(dag)
  if (errors.length > 0) {
    throw new Error(`Invalid DAG: ${errors.join(', ')}`)
  }
  
  // Build adjacency list and in-degree map
  const adjacency = new Map<string, string[]>()
  const inDegree = new Map<string, number>()
  
  for (const node of dag.nodes) {
    adjacency.set(node.id, [])
    inDegree.set(node.id, 0)
  }
  
  for (const edge of dag.edges) {
    adjacency.get(edge.from)?.push(edge.to)
    inDegree.set(edge.to, (inDegree.get(edge.to) || 0) + 1)
  }
  
  // Kahn's algorithm for topological sort
  const queue: string[] = []
  const result: string[] = []
  
  // Start with nodes that have no dependencies
  for (const nodeId of inDegree.keys()) {
    if (inDegree.get(nodeId) === 0) {
      queue.push(nodeId)
    }
  }
  
  while (queue.length > 0) {
    const nodeId = queue.shift()!
    result.push(nodeId)
    
    const neighbors = adjacency.get(nodeId) || []
    for (const neighbor of neighbors) {
      const newDegree = (inDegree.get(neighbor) || 0) - 1
      inDegree.set(neighbor, newDegree)
      
      if (newDegree === 0) {
        queue.push(neighbor)
      }
    }
  }
  
  // If result doesn't contain all nodes, there's a cycle
  if (result.length !== dag.nodes.length) {
    throw new Error('DAG contains a cycle')
  }
  
  return result
}

/**
 * Helper to resolve input references
 * Replaces {{bookInput.field}} and {{outputs.nodeId.field}} with actual values
 * 
 * @param input - Input object (possibly with template strings)
 * @param context - Execution context with bookInput and outputs
 * @returns Resolved input object
 */
export function resolveInput(
  input: Record<string, any> | ((context: ExecutionContext) => Record<string, any>),
  context: ExecutionContext
): Record<string, any> {
  // If input is a function, call it with context
  if (typeof input === 'function') {
    return input(context)
  }
  
  // Otherwise resolve template strings
  const resolved: Record<string, any> = {}
  
  for (const [key, value] of Object.entries(input)) {
    if (typeof value === 'string') {
      // Check for {{bookInput.field}} pattern
      const bookInputMatch = value.match(/^\{\{bookInput\.(.+)\}\}$/)
      if (bookInputMatch) {
        const field = bookInputMatch[1]
        resolved[key] = context.bookInput[field]
        continue
      }
      
      // Check for {{outputs.nodeId.field}} pattern
      const outputMatch = value.match(/^\{\{outputs\.([^.]+)\.(.+)\}\}$/)
      if (outputMatch) {
        const nodeId = outputMatch[1]
        const fieldPath = outputMatch[2]
        
        // Handle nested field paths like "data.glb_url"
        const fields = fieldPath.split('.')
        let result: any = context.outputs[nodeId]
        for (const field of fields) {
          result = result?.[field]
        }
        resolved[key] = result
        continue
      }
    }
    
    // No template, use value as-is
    resolved[key] = value
  }
  
  return resolved
}
