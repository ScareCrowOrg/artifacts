/**
 * @file BaseBookImpl.ts
 * @description Abstract base implementation of BaseBook with DAG executor
 * 
 * This file provides a concrete implementation of the BaseBook interface,
 * handling DAG validation, topological sorting, cell lifecycle management,
 * and state transfer. Subclasses only need to implement getDAG() and describe().
 * 
 * Part of BaseCell v1.0 Framework - Book Pattern Implementation
 */

import type {
  BaseBook,
  DAGDefinition,
  DAGNode,
  ExecutionContext,
  BookResult,
  CellRegistry,
  CellFactory
} from './BaseBook'
import type {
  BaseCell,
  EnvironmentConfig,
  HealthCheckResult,
  CellResult
} from './BaseCell'
import {
  validateDAG,
  topologicalSort,
  resolveInput
} from './BaseBook'
import { createLogger } from '@/utils/logger'

const log = createLogger('books:BaseBook')

/**
 * Default cell registry implementation
 */
class DefaultCellRegistry implements CellRegistry {
  private factories = new Map<string, CellFactory>()
  
  register(cellType: string, factory: CellFactory): void {
    this.factories.set(cellType, factory)
    log.debug('Registered cell type', { cellType })
  }
  
  create(cellType: string): BaseCell {
    const factory = this.factories.get(cellType)
    if (!factory) {
      throw new Error(`Cell type not registered: ${cellType}`)
    }
    return factory()
  }
  
  has(cellType: string): boolean {
    return this.factories.has(cellType)
  }
  
  listTypes(): string[] {
    return Array.from(this.factories.keys())
  }
}

// Global cell registry
const globalRegistry = new DefaultCellRegistry()

/**
 * Register a cell type globally
 * 
 * @param cellType - Unique cell type identifier
 * @param factory - Factory function to create cell instances
 */
export function registerCellType(cellType: string, factory: CellFactory): void {
  globalRegistry.register(cellType, factory)
}

/**
 * Get the global cell registry
 */
export function getCellRegistry(): CellRegistry {
  return globalRegistry
}

/**
 * Abstract base implementation of BaseBook
 * 
 * Provides complete DAG execution logic and helpers for all modes.
 * 
 * Subclasses must implement:
 * - getExecutionMode(): Declare 'dag', 'script', or 'hybrid'
 * - describe(): Define book metadata
 * 
 * For DAG mode, also implement:
 * - getDAG(): Define the workflow structure
 * 
 * For Script/Hybrid mode, also implement:
 * - execute(): Custom execution logic
 * 
 * @example DAG Mode
 * ```typescript
 * class MyWorkflowBook extends AbstractBaseBook {
 *   getExecutionMode(): ExecutionMode { return 'dag' }
 *   
 *   getDAG(): DAGDefinition {
 *     return {
 *       nodes: [
 *         { id: 'step1', cellType: 'calculator', input: { a: 1, b: 2, operation: 'add' } },
 *         { id: 'step2', cellType: 'calculator', input: (ctx) => ({ 
 *           a: ctx.outputs.step1.result, 
 *           b: 10, 
 *           operation: 'multiply' 
 *         }) }
 *       ],
 *       edges: [{ from: 'step1', to: 'step2' }]
 *     }
 *   }
 *   
 *   async describe() {
 *     return {
 *       id: 'my-workflow-book',
 *       name: 'My Workflow',
 *       version: '1.0.0',
 *       description: 'Adds then multiplies',
 *       inputs: {},
 *       outputs: { result: { type: 'number' } },
 *       tags: ['math', 'book']
 *     }
 *   }
 * }
 * ```
 * 
 * @example Script Mode
 * ```typescript
 * class RetryBook extends AbstractBaseBook {
 *   getExecutionMode(): ExecutionMode { return 'script' }
 *   
 *   async execute(input: Record<string, any>): Promise<BookResult> {
 *     let retries = 0
 *     while (retries < 3) {
 *       const cell = this.registry.create('my-cell')
 *       const result = await cell.execute(input)
 *       if (result.success) return { success: true, output: result.output, execution_time: 0 }
 *       retries++
 *     }
 *     return { success: false, output: {}, execution_time: 0, error: 'Max retries exceeded' }
 *   }
 * }
 * ```
 * 
 * @example Hybrid Mode
 * ```typescript
 * class HybridBook extends AbstractBaseBook {
 *   getExecutionMode(): ExecutionMode { return 'hybrid' }
 *   
 *   async execute(input: Record<string, any>): Promise<BookResult> {
 *     // Script logic
 *     const config = this.prepareConfig(input)
 *     
 *     // Use DAG for parallel execution
 *     const results = await this.executeDAG({
 *       nodes: [
 *         { id: 'a', cellType: 'cell-a', input: config.a },
 *         { id: 'b', cellType: 'cell-b', input: config.b }
 *       ],
 *       edges: []
 *     }, { bookInput: input })
 *     
 *     return { success: true, output: results, execution_time: 0 }
 *   }
 * }
 * ```
 */
export abstract class AbstractBaseBook implements BaseBook {
  private cells = new Map<string, BaseCell>()
  private _isSetup = false
  private registry: CellRegistry
  
  constructor(registry?: CellRegistry) {
    this.registry = registry || globalRegistry
  }
  
  /**
   * Get execution mode - must be implemented by subclasses
   * Defaults to 'dag' for backward compatibility
   */
  getExecutionMode(): import('./BaseBook').ExecutionMode {
    return 'dag'
  }
  
  /**
   * Get DAG definition - must be implemented by subclasses for DAG mode
   * Optional for script mode
   */
  getDAG?(): DAGDefinition
  
  /**
   * Describe book capabilities - must be implemented by subclasses
   */
  abstract describe(): Promise<import('./BaseCell').CellMetadata>
  
  /**
   * Setup all cells in the DAG (for DAG mode) or prepare for script mode
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    if (this._isSetup) {
      log.debug('Book already setup', { book: this.constructor.name })
      return
    }
    
    log.info('Setting up book', { book: this.constructor.name, mode: this.getExecutionMode() })
    
    const mode = this.getExecutionMode()
    
    // For DAG mode, setup cells based on DAG definition
    if (mode === 'dag') {
      const dag = this.getDAG?.()
      if (!dag) {
        throw new Error(`Book in 'dag' mode must implement getDAG()`)
      }
      
      // Validate DAG
      const errors = validateDAG(dag)
      if (errors.length > 0) {
        throw new Error(`Invalid DAG: ${errors.join(', ')}`)
      }
      
      // Instantiate all cells
      for (const node of dag.nodes) {
        if (!this.registry.has(node.cellType)) {
          throw new Error(`Cell type not registered: ${node.cellType}`)
        }
        
        const cell = this.registry.create(node.cellType)
        this.cells.set(node.id, cell)
        log.debug('Instantiated cell', { nodeId: node.id, cellType: node.cellType })
      }
      
      // Setup all cells in parallel
      await Promise.all(
        Array.from(this.cells.values()).map(cell => 
          cell.setup ? cell.setup(config) : Promise.resolve()
        )
      )
    }
    // For script/hybrid mode, no automatic setup - subclass handles it
    
    this._isSetup = true
    log.info('Book setup complete', { book: this.constructor.name, cellCount: this.cells.size })
  }
  
  /**
   * Teardown all cells in the DAG
   */
  async teardown(): Promise<void> {
    if (!this._isSetup) {
      log.debug('Book not setup, skipping teardown', { book: this.constructor.name })
      return
    }
    
    log.info('Tearing down book', { book: this.constructor.name })
    
    // Teardown all cells in parallel
    await Promise.all(
      Array.from(this.cells.values()).map(cell =>
        cell.teardown ? cell.teardown() : Promise.resolve()
      )
    )
    
    this.cells.clear()
    this._isSetup = false
    log.info('Book teardown complete', { book: this.constructor.name })
  }
  
  /**
   * Execute the book's workflow
   * 
   * Dispatches to appropriate execution strategy based on mode:
   * - DAG mode: Execute via topological sort
   * - Script mode: Delegate to subclass execute() implementation
   * - Hybrid mode: Delegate to subclass execute() (which can use executeDAG helper)
   */
  async execute(input: Record<string, any>): Promise<BookResult> {
    const mode = this.getExecutionMode()
    
    if (mode === 'dag') {
      return this.executeDAGMode(input)
    } else {
      // Script and Hybrid modes delegate to subclass implementation
      throw new Error(`Book in '${mode}' mode must implement execute() method`)
    }
  }
  
  /**
   * Execute in DAG mode
   * Orchestrates cells via topological sort
   * 
   * @private Internal method for DAG execution
   */
  private async executeDAGMode(input: Record<string, any>): Promise<BookResult> {
    const startTime = performance.now()
    
    if (!this._isSetup) {
      throw new Error('Book not setup - call setup() before execute()')
    }
    
    const dag = this.getDAG?.()
    if (!dag) {
      throw new Error('DAG mode requires getDAG() implementation')
    }
    
    const nodeMap = new Map(dag.nodes.map(n => [n.id, n]))
    
    // Initialize execution context
    const context: ExecutionContext = {
      outputs: {},
      bookInput: input,
      metadata: {
        startTime,
        completedNodes: [],
        failedNodes: []
      }
    }
    
    const nodeResults: Record<string, CellResult> = {}
    const executionTrace: BookResult['executionTrace'] = []
    
    try {
      // Get execution order via topological sort
      const executionOrder = topologicalSort(dag)
      log.debug('Execution order determined', { order: executionOrder })
      
      // Execute nodes in order
      for (const nodeId of executionOrder) {
        const node = nodeMap.get(nodeId)!
        const cell = this.cells.get(nodeId)!
        
        context.metadata.currentNode = nodeId
        
        const nodeStartTime = performance.now()
        log.debug('Executing node', { nodeId, cellType: node.cellType })
        
        try {
          // Resolve input for this node
          const resolvedInput = resolveInput(node.input, context)
          log.debug('Resolved input', { nodeId, input: resolvedInput })
          
          // Execute cell
          const result = await cell.execute(resolvedInput)
          
          const nodeEndTime = performance.now()
          
          // Store result
          nodeResults[nodeId] = result
          context.outputs[nodeId] = result.output
          
          executionTrace.push({
            nodeId,
            startTime: nodeStartTime,
            endTime: nodeEndTime,
            success: result.success,
            error: result.error
          })
          
          if (result.success) {
            context.metadata.completedNodes.push(nodeId)
            log.debug('Node completed successfully', { 
              nodeId, 
              executionTime: nodeEndTime - nodeStartTime 
            })
          } else {
            context.metadata.failedNodes.push(nodeId)
            
            // Check if node is optional
            if (!node.optional) {
              log.error('Required node failed', { nodeId, cellType: node.cellType, error: result.error })
              
              // Aggregate output from completed nodes
              const aggregatedOutput = this.aggregateOutput(context, dag)
              
              return {
                success: false,
                output: aggregatedOutput,
                execution_time: performance.now() - startTime,
                error: `Node '${nodeId}' (${node.cellType}) failed: ${result.error}`,
                nodeResults,
                executionTrace
              }
            } else {
              log.warn('Optional node failed, continuing', { nodeId, error: result.error })
            }
          }
        } catch (error: any) {
          const nodeEndTime = performance.now()
          
          executionTrace.push({
            nodeId,
            startTime: nodeStartTime,
            endTime: nodeEndTime,
            success: false,
            error: error.message
          })
          
          context.metadata.failedNodes.push(nodeId)
          
          if (!node.optional) {
            log.error('Node execution threw error', { nodeId, cellType: node.cellType, error: error.message })
            
            const aggregatedOutput = this.aggregateOutput(context, dag)
            
            return {
              success: false,
              output: aggregatedOutput,
              execution_time: performance.now() - startTime,
              error: `Node '${nodeId}' (${node.cellType}) threw error: ${error.message}`,
              nodeResults,
              executionTrace
            }
          } else {
            log.warn('Optional node threw error, continuing', { nodeId, cellType: node.cellType, error: error.message })
          }
        }
      }
      
      // All nodes completed successfully
      const totalTime = performance.now() - startTime
      const aggregatedOutput = this.aggregateOutput(context, dag)
      
      log.info('Book execution completed', {
        book: this.constructor.name,
        totalTime,
        completedNodes: context.metadata.completedNodes.length,
        failedNodes: context.metadata.failedNodes.length
      })
      
      return {
        success: true,
        output: aggregatedOutput,
        execution_time: totalTime,
        nodeResults,
        executionTrace,
        execution_steps: context.metadata.completedNodes
      }
    } catch (error: any) {
      log.error('Book execution failed', { error: error.message })
      
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: `Book execution failed: ${error.message}`,
        nodeResults,
        executionTrace
      }
    }
  }
  
  /**
   * Helper for hybrid mode: Execute a DAG within script execution
   * 
   * Allows script-mode books to run parallel cell execution for specific sub-workflows.
   * 
   * @param dag - DAG definition to execute
   * @param initialContext - Initial context (including bookInput)
   * @returns Aggregated outputs from DAG execution
   * 
   * @example
   * ```typescript
   * async execute(input: Record<string, any>): Promise<BookResult> {
   *   // Script logic
   *   const config = await this.prepareConfig(input)
   *   
   *   // Execute DAG for parallel generation
   *   const results = await this.executeDAG({
   *     nodes: [
   *       { id: 'gen1', cellType: 'generator', input: config.option1 },
   *       { id: 'gen2', cellType: 'generator', input: config.option2 }
   *     ],
   *     edges: []
   *   }, { bookInput: input })
   *   
   *   // More script logic
   *   return this.postProcess(results)
   * }
   * ```
   */
  protected async executeDAG(
    dag: DAGDefinition,
    initialContext: Record<string, any>
  ): Promise<Record<string, any>> {
    log.debug('Executing DAG in hybrid mode', { nodeCount: dag.nodes.length })
    
    // Validate DAG
    const errors = validateDAG(dag)
    if (errors.length > 0) {
      throw new Error(`Invalid DAG: ${errors.join(', ')}`)
    }
    
    // Create temporary cells for this DAG
    const tempCells = new Map<string, BaseCell>()
    for (const node of dag.nodes) {
      if (!this.registry.has(node.cellType)) {
        throw new Error(`Cell type not registered: ${node.cellType}`)
      }
      tempCells.set(node.id, this.registry.create(node.cellType))
    }
    
    // Setup context
    const context: ExecutionContext = {
      outputs: {},
      bookInput: initialContext.bookInput || initialContext,
      metadata: {
        startTime: performance.now(),
        completedNodes: [],
        failedNodes: []
      }
    }
    
    // Execute in topological order
    const executionOrder = topologicalSort(dag)
    const nodeMap = new Map(dag.nodes.map(n => [n.id, n]))
    
    for (const nodeId of executionOrder) {
      const node = nodeMap.get(nodeId)!
      const cell = tempCells.get(nodeId)!
      
      // Resolve input
      const resolvedInput = resolveInput(node.input, context)
      
      // Execute
      const result = await cell.execute(resolvedInput)
      
      if (!result.success && !node.optional) {
        throw new Error(`DAG node '${nodeId}' failed: ${result.error}`)
      }
      
      // Store output
      context.outputs[nodeId] = result.output
      context.metadata.completedNodes.push(nodeId)
    }
    
    log.debug('DAG execution completed in hybrid mode', { 
      completedNodes: context.metadata.completedNodes.length 
    })
    
    return context.outputs
  }
  
  /**
   * Aggregate output from all node results
   * By default, returns outputs from all completed nodes
   * Subclasses can override to customize output format
   */
  protected aggregateOutput(context: ExecutionContext, dag: DAGDefinition): Record<string, any> {
    return context.outputs
  }
  
  /**
   * Health check for book
   * Aggregates health from all cells
   */
  async health_check(): Promise<HealthCheckResult> {
    if (!this._isSetup) {
      return {
        status: 'unavailable',
        can_execute: false,
        reason: 'Book not setup'
      }
    }
    
    try {
      // Check health of all cells
      const healthChecks = await Promise.all(
        Array.from(this.cells.entries()).map(async ([nodeId, cell]) => ({
          nodeId,
          health: cell.health_check ? await cell.health_check() : { status: 'healthy' as const, can_execute: true }
        }))
      )
      
      // Book is healthy only if all cells are healthy
      const allHealthy = healthChecks.every(c => c.health.status === 'healthy')
      if (allHealthy) {
        return {
          status: 'healthy',
          can_execute: true
        }
      }
      
      // If any cell is unavailable, book is unavailable
      const anyUnavailable = healthChecks.some(c => c.health.status === 'unavailable')
      if (anyUnavailable) {
        const unavailableCells = healthChecks
          .filter(c => c.health.status === 'unavailable')
          .map(c => c.nodeId)
        
        return {
          status: 'unavailable',
          can_execute: false,
          reason: `Cells unavailable: ${unavailableCells.join(', ')}`,
          estimated_recovery_seconds: Math.max(
            ...healthChecks.map(c => c.health.estimated_recovery_seconds || 0)
          )
        }
      }
      
      // Otherwise book is degraded
      const degradedCells = healthChecks
        .filter(c => c.health.status === 'degraded')
        .map(c => c.nodeId)
      
      return {
        status: 'degraded',
        can_execute: true, // Degraded means can still execute with reduced functionality
        reason: `Cells degraded: ${degradedCells.join(', ')}`,
        estimated_recovery_seconds: Math.max(
          ...healthChecks.map(c => c.health.estimated_recovery_seconds || 0)
        )
      }
    } catch (error: any) {
      log.error('Health check failed', { error: error.message })
      return {
        status: 'unavailable',
        can_execute: false,
        reason: `Health check failed: ${error.message}`
      }
    }
  }
}
