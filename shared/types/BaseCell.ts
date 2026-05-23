/**
 * @file BaseCell.ts
 * @description BaseCell v1.0 - Core execution interface for cells
 *
 * This file defines the BaseCell interface that provides execution lifecycle,
 * validation, and health checking capabilities for all cell types.
 * It enables headless execution, composition, and testing.
 *
 * Part of BaseCell v1.0 Framework Implementation
 * Epic: Phase 1 - Foundation
 * Task: [BC-TS-001] Create BaseCell Interface (TypeScript)
 */

import { loadCellTypeJson } from '@/utils/cellTypeLoaderUtil'

// ============ SUPPORTING TYPES ============

/**
 * Fragment data structure
 * Compatible with legacy baseCell.ts CellFragment
 */
export interface CellFragment {
  /** Fragment type (e.g., 'memoria', 'code', 'note') */
  type: string
  
  /** Fragment content (usually markdown) */
  conteudo?: string
  
  /** Alternative content field for compatibility */
  content?: string
  
  /** Optional fragment metadata */
  [key: string]: any
}

/**
 * Execution fragment for tracing lifecycle steps
 */
export interface Fragment {
  /** Fragment type (setup, execute, save, show, error) */
  type: 'setup' | 'execute' | 'save' | 'show' | 'error'
  
  /** Execution status */
  status: 'pending' | 'completed' | 'failed'
  
  /** Action name (for execute fragments) */
  action?: string
  
  /** Output from this step */
  output?: any
  
  /** Error message (for failed fragments) */
  error?: string
  
  /** Additional metadata */
  metadata?: Record<string, any>
}

/**
 * Execute action configuration
 */
export interface ExecuteAction {
  /** Action name to execute */
  action: string
  
  /** Parameters for the action */
  params?: Record<string, any>
}

/**
 * Setup configuration
 */
export interface SetupConfig {
  /** Configuration options for setup */
  [key: string]: any
}

/**
 * Save configuration
 */
export interface SaveConfig {
  /** Save options */
  [key: string]: any
}

/**
 * Show configuration
 */
export interface ShowConfig {
  /** Display mode */
  mode?: 'headless' | 'workspace' | 'modal'
  
  /** Grid position (for workspace mode) */
  position?: {
    x?: number
    y?: number
    w?: number
    h?: number
  }
  
  /** Title (for modal mode) */
  title?: string
  
  /** Additional show options */
  [key: string]: any
}

/**
 * Lifecycle configuration for run() method
 */
export interface LifecycleConfig {
  /** Optional setup configuration */
  setup?: SetupConfig
  
  /** Execute action(s) - single or array */
  execute: ExecuteAction | ExecuteAction[]
  
  /** Save configuration - boolean or config object */
  save?: boolean | SaveConfig
  
  /** Show configuration (RenderableCell only) */
  show?: ShowConfig
}

/**
 * Result of cell execution
 */
export interface CellResult {
  /** Cell ID */
  id?: string
  
  /** Execution status */
  status?: 'pending' | 'completed' | 'failed'
  
  /** Whether execution was successful */
  success: boolean
  
  /** Output data from execution */
  output: Record<string, any>
  
  /** R2/S3 artifact references (URLs, IDs) */
  artifacts?: string[]
  
  /** Execution time in milliseconds */
  execution_time: number
  
  /** Execution steps for auditing */
  execution_steps?: string[]
  
  /** Execution fragments for tracing */
  fragments?: Fragment[]
  
  /** Quality score (0-1) if applicable */
  quality_score?: number
  
  /** Error message if failed */
  error?: string
  
  /** Additional metadata */
  metadata?: Record<string, any>
}

/**
 * Cell introspection metadata
 * Loaded from type.json or implemented inline
 */
export interface CellMetadata {
  /** Unique cell type identifier */
  id: string
  
  /** Human-readable name */
  name: string
  
  /** Cell version */
  version: string
  
  /** Description of functionality */
  description: string
  
  /** Input schema */
  inputs: Record<string, any>
  
  /** Output schema */
  outputs: Record<string, any>
  
  /** Tags for categorization */
  tags: string[]
  
  /** LLM configuration (if AI-powered) */
  llm_config?: Record<string, any>
  
  /** Estimated execution duration in seconds */
  estimated_duration_seconds?: number
  
  /** Required resources (e.g., 'gpu', 'redis', 'internet') */
  required_resources?: string[]
}

/**
 * Validation error
 */
export interface ValidationError {
  /** Field name that failed validation */
  field: string
  
  /** Error message */
  message: string
}

/**
 * Environment configuration for cell execution
 */
export interface EnvironmentConfig {
  /** GPU availability */
  has_gpu: boolean
  
  /** GPU VRAM in MB */
  gpu_vram_mb: number
  
  /** Number of CPU cores */
  cpu_cores: number
  
  /** Whether running in headless mode */
  headless_mode: boolean
  
  /** Execution timeout in seconds */
  timeout_seconds: number
  
  /** Internet access allowed */
  allow_internet?: boolean
  
  /** External API access allowed */
  allow_external_api?: boolean
  
  /** Batch size for bulk operations */
  batch_size?: number
  
  /** Cache enabled */
  cache_enabled?: boolean
}

/**
 * Health check result
 */
export interface HealthCheckResult {
  /** Health status */
  status: 'healthy' | 'degraded' | 'unavailable'
  
  /** Whether cell can execute */
  can_execute: boolean
  
  /** Reason if not healthy */
  reason?: string
  
  /** Estimated recovery time in seconds */
  estimated_recovery_seconds?: number
}

// ============ MAIN ABSTRACT CLASS ============

/**
 * BaseCell - Core execution abstract class for all cells
 * 
 * This abstract class defines the fundamental contract that all cell types must implement.
 * It provides execution lifecycle, validation, and health checking capabilities.
 * 
 * Key Features:
 * - Headless execution support (no UI required)
 * - Composability (cells can use other cells)
 * - Testability (pure execution logic)
 * - Introspection (describe() for capabilities)
 * - Default show() implementation with dynamic form generation
 * - Optional instance composition for metadata access
 * 
 * Lifecycle:
 * 1. setup(config) - Called once before first execution
 * 2. execute(input) - Called multiple times for executions
 * 3. teardown() - Called once when cell is destroyed
 * 
 * Instance Composition Pattern:
 * BaseCell can optionally reference its Cell runtime instance to access metadata
 * (assignee_id, initial_data, fragments, version, refs, etc.) when needed.
 * This follows the PipelineItem → NotebookItem composition pattern.
 * 
 * @example
 * ```typescript
 * class CalculatorCell extends BaseCell {
 *   async execute(input: Record<string, any>): Promise<CellResult> {
 *     const { operation, a, b } = input
 *     const result = operation === 'add' ? a + b : a - b
 *     return {
 *       success: true,
 *       output: { result },
 *       execution_time: 5
 *     }
 *   }
 *   
 *   async describe(): Promise<CellMetadata> {
 *     return {
 *       id: 'calculator-cell',
 *       name: 'Calculator',
 *       version: '1.0.0',
 *       description: 'Simple math operations',
 *       inputs: { operation: 'string', a: 'number', b: 'number' },
 *       outputs: { result: 'number' },
 *       tags: ['math', 'calculator']
 *     }
 *   }
 *   
 *   validate(input: Record<string, any>): ValidationError[] {
 *     const errors: ValidationError[] = []
 *     if (!input.operation) {
 *       errors.push({ field: 'operation', message: 'Required' })
 *     }
 *     return errors
 *   }
 *   // Inherits default show() implementation - no override needed
 * }
 * ```
 */
export abstract class BaseCell {
  // ===== INSTANCE COMPOSITION (Optional) =====
  
  /**
   * Optional reference to the Cell runtime instance
   * 
   * When present, provides access to instance metadata:
   * - assignee_id: Who owns this execution
   * - initial_data: Initial configuration
   * - fragments: Execution history
   * - refs: File references
   * - version: Instance version
   * 
   * This follows the PipelineItem → NotebookItem composition pattern.
   * The field is optional to maintain backward compatibility and support
   * both context-aware and utility cells.
   * 
   * @example
   * ```typescript
   * // Context-aware cell
   * class DataProcessingCell implements BaseCell {
   *   cell_instance?: Cell
   *   
   *   async execute(input: Record<string, any>): Promise<CellResult> {
   *     const owner = this.cell_instance?.assignee_id
   *     const config = this.cell_instance?.initial_data
   *     // Use metadata in execution...
   *   }
   * }
   * 
   * // Utility cell (no instance needed)
   * class ValidatorCell implements BaseCell {
   *   // No cell_instance field
   *   async execute(input: Record<string, any>): Promise<CellResult> {
   *     // Pure utility logic...
   *   }
   * }
   * ```
   */
  cell_instance?: {
    id: string
    assignee_id: string
    initial_data: Record<string, any>
    fragments: Array<string | Record<string, any>>
    refs: Record<string, string[]>
    version?: string
    created_at?: string
    updated_at?: string
    [key: string]: any
  }
  
  // ===== REQUIRED ABSTRACT METHODS =====
  
  /**
   * Execute the cell's main logic (REQUIRED)
   * 
   * This is the core method that performs the cell's functionality.
   * It can execute locally (pure JS) or delegate to backend via HTTP.
   * 
   * @param input - Input data for execution
   * @returns Promise resolving to CellResult
   */
  abstract execute(input: Record<string, any>): Promise<CellResult>
  
  /**
   * Describe the cell's capabilities (REQUIRED)
   * 
   * Returns metadata about the cell including inputs, outputs, and configuration.
   * This can load from type.json or return hardcoded values.
   * 
   * @returns Promise resolving to CellMetadata
   */
  abstract describe(): Promise<CellMetadata>
  
  /**
   * Validate input before execution (REQUIRED)
   * 
   * Checks if input meets the cell's requirements.
   * Returns empty array if valid, or list of errors if invalid.
   * 
   * @param input - Input data to validate
   * @returns Array of validation errors (empty if valid)
   */
  abstract validate(input: Record<string, any>): ValidationError[]
  
  // ===== OPTIONAL LIFECYCLE METHODS (with defaults) =====
  
  /**
   * Initialize resources (optional)
   * 
   * Called once before the first execute().
   * Use for lightweight resource allocation (connections, listeners, etc).
   * 
   * Default implementation: no-op
   * Override if cell needs initialization.
   * 
   * @param config - Environment configuration
   * @returns Promise that resolves when setup is complete
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    // Default: no-op
  }
  
  /**
   * Release resources (optional)
   * 
   * Called once when cell is destroyed.
   * Use for cleanup (close connections, remove listeners, etc).
   * 
   * Default implementation: no-op
   * Override if cell allocated resources in setup().
   * 
   * @returns Promise that resolves when teardown is complete
   */
  async teardown(): Promise<void> {
    // Default: no-op
  }
  
  /**
   * Check if cell can execute (optional)
   * 
   * Useful for cells that depend on external resources (backend, GPU, API).
   * Called before execute() to verify readiness.
   * 
   * Default implementation: always healthy
   * Override if cell has dependencies to check.
   * 
   * @returns Promise resolving to HealthCheckResult
   */
  async health_check(): Promise<HealthCheckResult> {
    return createHealthyResult()
  }
  
  /**
   * Load i18n translations for this cell type (optional)
   *
   * Calls the shared cellI18nLoader utility with the cell's own cellTypeName.
   * Useful when a cell needs to ensure its translations are loaded
   * outside of the grid auto-loader (e.g. in standalone viewers or tests).
   *
   * Uses dynamic import to avoid circular dependency (BaseCell
   * is in shared/types, loader is in canonical/shared/utils).
   *
   * Default implementation: loads translations for this cell type.
   * No-op if __cellTypeName is not set (e.g. abstract base, not instantiated).
   *
   * @param locale - Locale to load (defaults to current i18n locale)
   * @returns true if translations were loaded/merged
   */
  async loadI18n(locale?: string): Promise<boolean> {
    const typeName = (this as any).__cellTypeName
    if (!typeName) return false
    try {
      const { loadCellI18n } = await import(
        '#canonical/shared/utils/cellI18nLoader'
      )
      return loadCellI18n(typeName, locale)
    } catch {
      return false
    }
  }

  /**
   * Execute complete cell lifecycle atomically (optional)
   *
   * Executes setup → execute → save → show in one call.
   * Each step adds a Fragment to the result for tracing.
   * On error, aborts execution and returns failed result.
   *
   * Default implementation provided. Can be overridden for custom lifecycle.
   *
   * @param lifecycle - Lifecycle configuration
   * @returns Promise resolving to CellResult with fragments
   *
   * @example
   * ```typescript
   * const result = await cell.run({
   *   setup: { mode: 'production' },
   *   execute: [
   *     { action: 'generate', params: { prompt: 'cat' } },
   *     { action: 'enhance', params: { style: '3d' } }
   *   ],
   *   save: true,
   *   show: { mode: 'modal' }
   * })
   * ```
   */
  async run(lifecycle: LifecycleConfig): Promise<CellResult> {
    const startTime = performance.now()
    const metadata = await this.describe()

    const result: CellResult = {
      id: metadata.id,
      status: 'pending',
      success: false,
      output: {},
      fragments: [],
      execution_time: 0
    }

    try {
      // Step 1: Setup (optional)
      if (lifecycle.setup) {
        const setupConfig = lifecycle.setup as any
        await this.setup(setupConfig)
        result.fragments!.push({
          type: 'setup',
          status: 'completed'
        })
      }

      // Step 2: Execute (required, can be single or array)
      const executeActions = Array.isArray(lifecycle.execute)
        ? lifecycle.execute
        : [lifecycle.execute]

      for (const actionConfig of executeActions) {
        const actionName = actionConfig.action
        const actionParams = actionConfig.params || {}

        if (!actionName) {
          throw new Error("Execute action must have 'action' key")
        }

        // Execute action
        const executeResult = await this.execute(actionParams)

        result.fragments!.push({
          type: 'execute',
          action: actionName,
          output: executeResult.output,
          status: 'completed'
        })

        // Store output for next action
        result.output = executeResult.output
      }

      // Step 3: Save (default: true)
      const saveConfig = lifecycle.save
      if (saveConfig !== false) {
        result.fragments!.push({
          type: 'save',
          status: 'completed'
        })
      }

      // Mark as completed
      result.status = 'completed'
      result.success = true
    } catch (error: any) {
      result.status = 'failed'
      result.success = false
      result.error = error.message
      result.fragments!.push({
        type: 'error',
        status: 'failed',
        error: error.message
      })
    } finally {
      result.execution_time = performance.now() - startTime
    }

    return result
  }
  
  // ===== RENDERING (with default implementation) =====
  
  /**
   * Render the cell in the specified mode
   *
   * Default implementation:
   * 1. Check if custom View.vue component exists
   * 2. If YES: Return the View component (cell handles its own UI)
   * 3. If NO: Load schema from type.json/describe() and generate dynamic form
   * 4. User fills form → clicks Execute → calls execute()
   * 5. Show result dynamically
   *
   * Override this method for custom rendering behavior.
   *
   * @param data - Initial data for the cell
   * @param options - Rendering options (mode, position, title)
   * @returns Promise resolving to Vue component (if custom view) or void (if dynamic form)
   *
   * @example
   * ```typescript
   * // Simple cell - uses default show (inherits)
   * class CalculatorCell extends BaseCell {
   *   // No show() override - gets dynamic form generation
   * }
   *
   * // Complex cell - custom show (overrides)
   * class PngGeneratorCell extends BaseCell {
   *   async show(data, options) {
   *     // Custom implementation with preview, sliders, etc
   *     // Should return Vue component or undefined
   *   }
   * }
   * ```
   */
  async show(data: Record<string, any>, options: ShowConfig): Promise<any> {
    // Store data on instance so View.vue can access via props.cellInstance.__initialData
    if (data && Object.keys(data).length > 0) {
      ;(this as any).__initialData = data
    }

    // Default implementation: Check for custom View.vue first
    // Framework will use this to load cell UI with proper context

    console.log('🎬 🎬 🎬 [BaseCell] show() called, checking for custom view 🎬 🎬 🎬', {
      timestamp: new Date().toISOString(),
    })

    // Check if custom View.vue exists
    const hasCustomView = await this.checkViewComponentExists()

    console.log('🎬 [BaseCell] checkViewComponentExists returned:', {
      hasCustomView,
      timestamp: new Date().toISOString(),
    })

    if (hasCustomView) {
      if (!this.__cellTypeName) {
        throw new Error('Cell type name not set during discovery')
      }

      const cellType = await this.loadCellTypeFromDiscovery(this.__cellTypeName)
      if (!cellType?.default_refs?.view?.[0]) {
        throw new Error(`No view component path for cell type: ${this.__cellTypeName}`)
      }

      return {
        cellTypeName: cellType.name,
        componentPath: cellType.default_refs.view[0],
        cellInstance: this
      }
    }

    // No custom view: generate dynamic form
    const inputSchema = await this.loadPropertySchemaFromTypeDefinition()

    // Fallback: use describe().inputs if type.json unavailable
    const schema = inputSchema || (await this.describe()).inputs

    // Generate and render dynamic form (framework will implement)
    await this.generateDynamicView(schema, options)
  }
  
  /**
   * Load cell's property schema from type.json (source of truth)
   * Returns properties_schema from the canonical type definition
   * Attempts to load from discovery system or direct import
   * 
   * @returns Property schema or null if not found
   */
  protected async loadPropertySchemaFromTypeDefinition(): Promise<Record<string, any> | null> {
    try {
      const cellTypeId = this.getCellTypeId()
      if (!cellTypeId) {
        return null
      }

      // Load cell type definition and extract properties_schema
      const cellType = await this.loadCellTypeFromDiscovery(cellTypeId)
      if (!cellType) {
        return null
      }

      // Return properties_schema if exists, null otherwise triggers fallback to describe()
      return cellType.properties_schema || null
    } catch (error) {
      console.debug('[BaseCell] Could not load property schema from type definition:', error)
      return null
    }
  }
  
  /**
   * Check if custom View.vue component exists
   * Checks type.json default_refs and attempts dynamic import
   * Cells can override this if they have custom detection logic
   * 
   * @returns True if custom view exists, false otherwise
   */
  protected async checkViewComponentExists(): Promise<boolean> {
    console.log('🔍 🔍 🔍 [BaseCell] checkViewComponentExists CALLED 🔍 🔍 🔍')
    try {
      const cellTypeId = this.getCellTypeId()
      console.log('🔍 [BaseCell] checkViewComponentExists - cellTypeId:', { cellTypeId })

      if (!cellTypeId) {
        console.log('[BaseCell] checkViewComponentExists - no cellTypeId, returning false')
        return false
      }

      // Load from discovery system
      const cellType = await this.loadCellTypeFromDiscovery(cellTypeId)
      console.log('🔍 [BaseCell] checkViewComponentExists - loaded cellType:', {
        cellTypeId,
        hasCellType: !!cellType,
        cellTypeKeys: cellType ? Object.keys(cellType) : [],
        default_refs: cellType?.default_refs,
      })

      if (!cellType) {
        console.log('❌ [BaseCell] checkViewComponentExists - cellType is null, returning false')
        return false
      }

      // Check if type.json has view refs
      const viewRefs = cellType.default_refs?.view
      console.log('🔍 [BaseCell] checkViewComponentExists - viewRefs:', {
        viewRefs,
        isArray: Array.isArray(viewRefs),
        length: viewRefs?.length,
      })

      if (!viewRefs || !Array.isArray(viewRefs) || viewRefs.length === 0) {
        console.log('❌ [BaseCell] checkViewComponentExists - no viewRefs, returning FALSE')
        return false
      }

      // If view refs exist in type.json, assume view component exists
      // Actual dynamic import would be handled by the framework/Vue layer
      console.log('✅ ✅ ✅ [BaseCell] checkViewComponentExists - found viewRefs, returning TRUE ✅ ✅ ✅')
      return true
    } catch (error) {
      console.error('❌ ERROR in checkViewComponentExists:', error)
      return false
    }
  }
  
  /**
   * Generate dynamic form and handle execution
   * Converts schema to form fields and delegates to framework for rendering
   * 
   * @param inputSchema - Input schema for form generation
   * @param options - Show options
   */
  protected async generateDynamicView(
    inputSchema: Record<string, any>,
    options: ShowConfig
  ): Promise<void> {
    try {
      // Import DynamicFormGenerator dynamically
      const { DynamicFormGenerator } = await import('@/utils/DynamicFormGenerator')
      
      // Generate form fields from schema
      const formFields = DynamicFormGenerator.generateFormFields(inputSchema)

      if (formFields.length === 0) {
        console.warn('[BaseCell] No form fields generated from schema')
        return
      }

      // Delegate to framework for actual rendering
      // Framework will handle:
      // - Rendering form in modal/workspace
      // - Collecting user input
      // - Calling execute() with form data
      // - Displaying results
      await this.renderDynamicFormComponent({
        formFields,
        schema: inputSchema,
        mode: options.mode,
        onExecute: async (formData: Record<string, any>) => {
          // Validate form data
          const errors = DynamicFormGenerator.validateFormData(formData, inputSchema)
          if (errors.length > 0) {
            console.error('[BaseCell] Form validation failed:', errors)
            return {
              success: false,
              output: { errors },
              execution_time: 0,
              error: 'Validation failed: ' + errors.map(e => e.message).join(', ')
            }
          }

          // Execute cell with validated data
          return await this.execute(formData)
        }
      })
    } catch (error: any) {
      console.error('[BaseCell] Dynamic view generation failed:', error)
      throw error
    }
  }

  /**
   * Get cell type ID from class name or override
   * Converts class name to kebab-case (e.g., PngGeneratorCell → png-generator-cell)
   * Subclasses can override to provide custom cell type ID
   * 
   * @returns Cell type ID or null if cannot be determined
   */
  protected getCellTypeId(): string | null {
    const className = this.constructor.name
    if (!className || className === 'BaseCell') {
      return null
    }

    // Convert PngGeneratorCell → png-generator-cell
    return className
      .replace(/Cell$/, '') // Remove 'Cell' suffix
      .replace(/([a-z])([A-Z])/g, '$1-$2') // Insert hyphen between lowercase and uppercase
      .toLowerCase()
  }

  /**
   * Load cell type definition from discovery system
   * Attempts to import type.json from canonical artifacts
   * Framework can override this to integrate with custom discovery systems
   *
   * @param cellTypeId - Cell type identifier
   * @returns Cell type definition or null if not found
   */
  protected async loadCellTypeFromDiscovery(cellTypeId: string): Promise<any> {
    console.log('📥 📥 📥 [BaseCell] loadCellTypeFromDiscovery START 📥 📥 📥')
    try {
      // PHASE 7: Use semantic cellType.name for URL if available (preserves folder name)
      // This is set by DynamicWorkspace: 3d-mesh-prototyping-cell instead of mesh-prototyping
      const typeFolder = (this as any).__cellTypeName || cellTypeId

      console.log('📥 [BaseCell] loadCellTypeFromDiscovery START', {
        cellTypeId,
        __cellTypeName: (this as any).__cellTypeName,
        typeFolder,
        timestamp: new Date().toISOString(),
      })

      // Use shared utility to load type.json (handles both JSON and reference files)
      // Uses #artifacts/ import map which Vite resolves to actual artifact paths
      const typeJsonUrl = `#artifacts/canonical/cell_types/${typeFolder}/type.json`
      const typeDef = await loadCellTypeJson(typeJsonUrl)

      console.log('✅ [BaseCell] loadCellTypeFromDiscovery SUCCESS ✅', {
        cellTypeId,
        typeFolder,
        hasResult: !!typeDef,
        resultKeys: typeDef ? Object.keys(typeDef) : [],
        default_refs: typeDef?.default_refs,
        'default_refs.view': typeDef?.default_refs?.view,
        timestamp: new Date().toISOString(),
      })

      // Log the FULL cellType object so we can see everything
      console.log('📦 FULL cellType object:', typeDef)

      return typeDef
    } catch (error) {
      console.error(`❌ [BaseCell] loadCellTypeFromDiscovery FAILED for ${cellTypeId}:`, error)
      return null
    }
  }

  /**
   * Render dynamic form component
   * Placeholder for framework integration
   * Framework will override this to handle actual Vue component rendering
   * 
   * @param config - Form rendering configuration
   */
  protected async renderDynamicFormComponent(config: any): Promise<void> {
    // Framework placeholder - to be implemented by Vue layer
    // This method will be called by generateDynamicView()
    // Framework should:
    // 1. Render form component with config.formFields
    // 2. Collect user input
    // 3. Call config.onExecute(formData)
    // 4. Display results
    console.warn('[BaseCell] renderDynamicFormComponent not implemented by framework')
    console.debug('[BaseCell] Form config:', config)
  }
}

/**
 * Type guard to check if an object is a BaseCell instance
 */
export function isBaseCell(obj: any): obj is BaseCell {
  return obj instanceof BaseCell
}

/**
 * Type guard to check if an object has BaseCell-like methods (duck typing)
 * Useful for checking objects from different contexts
 */
export function isBaseCellLike(obj: any): obj is BaseCell {
  return (
    obj !== null &&
    typeof obj === 'object' &&
    typeof obj.execute === 'function' &&
    typeof obj.describe === 'function' &&
    typeof obj.validate === 'function' &&
    typeof obj.show === 'function'
  )
}

/**
 * Helper to create default HealthCheckResult
 */
export function createHealthyResult(): HealthCheckResult {
  return {
    status: 'healthy',
    can_execute: true
  }
}

/**
 * Helper to create default EnvironmentConfig
 */
export function createDefaultEnvironmentConfig(): EnvironmentConfig {
  return {
    has_gpu: false,
    gpu_vram_mb: 0,
    cpu_cores: navigator.hardwareConcurrency || 4,
    headless_mode: false,
    timeout_seconds: 300,
    allow_internet: true,
    allow_external_api: true,
    batch_size: 1,
    cache_enabled: true
  }
}
