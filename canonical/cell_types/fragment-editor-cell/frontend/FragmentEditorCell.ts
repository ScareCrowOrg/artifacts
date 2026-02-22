/**
 * @file FragmentEditorCell.ts
 * @description Fragment Editor Cell - BaseCell implementation for fragment editing
 * 
 * This cell provides fragment editing capabilities within the Dynamic Workspace.
 * It allows users to create, edit, and load fragments (markdown content) for cells.
 * 
 * Part of BaseCell v1.0 Framework Implementation
 * Epic: Classic Workspace Deprecation
 * Task: Create fragment-editor-cell
 */

import { BaseCell } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError } from '@/types/BaseCell'
import { apiFetch } from '@/services/apiService'

/**
 * Fragment editor actions
 */
export type FragmentAction = 'create' | 'edit' | 'load'

/**
 * Fragment editor input interface
 */
export interface FragmentEditorInput {
  /** Action to perform */
  action: FragmentAction
  
  /** Cell ID (required for create/edit) */
  cellId?: string
  
  /** Fragment ID (required for edit/load) */
  fragmentId?: string
  
  /** Fragment content (required for create/edit) */
  content?: string
}

/**
 * Fragment editor output interface
 */
export interface FragmentEditorOutput {
  /** Fragment ID */
  fragmentId?: string
  
  /** Fragment content */
  content?: string
  
  /** Cell ID */
  cellId?: string
  
  /** Success message */
  message?: string
}

/**
 * FragmentEditorCell - BaseCell implementation for fragment editing
 * 
 * This cell provides a headless-first interface for managing cell fragments.
 * It supports three primary actions:
 * - create: Create a new fragment for a cell
 * - edit: Update an existing fragment
 * - load: Load fragment data by ID
 * 
 * The cell uses the existing `/api/cells/{cell_id}/update` endpoint,
 * following the rule that cells must NOT create new API endpoints.
 * 
 * @example
 * ```typescript
 * const cell = new FragmentEditorCell()
 * 
 * // Create new fragment
 * const result = await cell.execute({
 *   action: 'create',
 *   cellId: 'cell-123',
 *   content: '# My Fragment\n\nContent...'
 * })
 * 
 * // Edit existing fragment
 * const result = await cell.execute({
 *   action: 'edit',
 *   cellId: 'cell-123',
 *   fragmentId: 'fragment-456',
 *   content: '# Updated Fragment'
 * })
 * 
 * // Load fragment
 * const result = await cell.execute({
 *   action: 'load',
 *   fragmentId: 'fragment-456'
 * })
 * ```
 */
export class FragmentEditorCell extends BaseCell {
  /**
   * Execute fragment operation
   * 
   * Handles create, edit, and load operations for fragments.
   * Uses existing API endpoints - no new endpoints created.
   * 
   * @param input - Fragment editor input parameters
   * @returns CellResult with operation outcome
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()
    
    try {
      // Validate input
      const errors = this.validate(input)
      if (errors.length > 0) {
        return {
          success: false,
          output: { errors },
          execution_time: performance.now() - startTime,
          error: 'Validation failed: ' + errors.map(e => e.message).join(', ')
        }
      }
      
      const { action, cellId, fragmentId, content } = input as FragmentEditorInput
      
      // Handle different actions
      switch (action) {
        case 'create':
          return await this.createFragment(cellId!, content!, startTime)
          
        case 'edit':
          return await this.editFragment(cellId!, fragmentId!, content!, startTime)
          
        case 'load':
          return await this.loadFragment(fragmentId!, startTime)
          
        default:
          return {
            success: false,
            output: {},
            execution_time: performance.now() - startTime,
            error: `Unknown action: ${action}`
          }
      }
    } catch (error: any) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message || 'Unknown error occurred'
      }
    }
  }
  
  /**
   * Create a new fragment for a cell
   * 
   * @param cellId - Target cell ID
   * @param content - Fragment content (markdown)
   * @param startTime - Execution start time
   * @returns CellResult with created fragment
   */
  private async createFragment(
    cellId: string,
    content: string,
    startTime: number
  ): Promise<CellResult> {
    try {
      // First, get the current cell to retrieve existing fragments
      const cellResponse = await apiFetch(`/api/cells/${cellId}`, {
        method: 'GET'
      })
      
      if (!cellResponse.ok) {
        throw new Error('Failed to load cell data')
      }
      
      const cellData = await cellResponse.json()
      const existingFragments = cellData.fragments || []
      
      // Create new fragment object
      const newFragment = {
        tipo: 'memoria',
        conteudo: content,
        resultado: null,
        timestamp: new Date().toISOString()
      }
      
      // Append to existing fragments
      const updatedFragments = [...existingFragments, newFragment]
      
      // Update cell with new fragments array
      const updateResponse = await apiFetch(`/api/cells/${cellId}/update`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          fragments: updatedFragments
        })
      })
      
      if (!updateResponse.ok) {
        throw new Error('Failed to save fragment')
      }
      
      const result = await updateResponse.json()
      
      return {
        success: true,
        output: {
          fragmentId: (existingFragments.length).toString(),
          content,
          cellId,
          message: 'Fragment created successfully'
        },
        execution_time: performance.now() - startTime
      }
    } catch (error: any) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message || 'Failed to create fragment'
      }
    }
  }
  
  /**
   * Edit an existing fragment
   * 
   * @param cellId - Target cell ID
   * @param fragmentId - Fragment index to edit
   * @param content - Updated fragment content
   * @param startTime - Execution start time
   * @returns CellResult with updated fragment
   */
  private async editFragment(
    cellId: string,
    fragmentId: string,
    content: string,
    startTime: number
  ): Promise<CellResult> {
    try {
      // Get current cell data
      const cellResponse = await apiFetch(`/api/cells/${cellId}`, {
        method: 'GET'
      })
      
      if (!cellResponse.ok) {
        throw new Error('Failed to load cell data')
      }
      
      const cellData = await cellResponse.json()
      const fragments = cellData.fragments || []
      
      // Parse fragment ID as index
      const fragmentIndex = parseInt(fragmentId, 10)
      
      if (isNaN(fragmentIndex) || fragmentIndex < 0 || fragmentIndex >= fragments.length) {
        throw new Error('Invalid fragment ID')
      }
      
      // Update fragment at index
      fragments[fragmentIndex] = {
        ...fragments[fragmentIndex],
        conteudo: content,
        timestamp: new Date().toISOString()
      }
      
      // Update cell with modified fragments
      const updateResponse = await apiFetch(`/api/cells/${cellId}/update`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          fragments
        })
      })
      
      if (!updateResponse.ok) {
        throw new Error('Failed to update fragment')
      }
      
      return {
        success: true,
        output: {
          fragmentId,
          content,
          cellId,
          message: 'Fragment updated successfully'
        },
        execution_time: performance.now() - startTime
      }
    } catch (error: any) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message || 'Failed to edit fragment'
      }
    }
  }
  
  /**
   * Load fragment data by ID
   * 
   * Note: This requires knowing the cell ID as well, since fragments
   * are stored within cells. In practice, the cellId should be provided
   * along with fragmentId for load operations.
   * 
   * @param fragmentId - Fragment ID to load (format: cellId:fragmentIndex)
   * @param startTime - Execution start time
   * @returns CellResult with fragment data
   */
  private async loadFragment(
    fragmentId: string,
    startTime: number
  ): Promise<CellResult> {
    try {
      // Parse fragmentId as cellId:fragmentIndex
      const parts = fragmentId.split(':')
      if (parts.length !== 2) {
        throw new Error('Invalid fragment ID format. Expected: cellId:fragmentIndex')
      }
      
      const [cellId, indexStr] = parts
      const fragmentIndex = parseInt(indexStr, 10)
      
      if (isNaN(fragmentIndex)) {
        throw new Error('Invalid fragment index')
      }
      
      // Get cell data
      const cellResponse = await apiFetch(`/api/cells/${cellId}`, {
        method: 'GET'
      })
      
      if (!cellResponse.ok) {
        throw new Error('Failed to load cell data')
      }
      
      const cellData = await cellResponse.json()
      const fragments = cellData.fragments || []
      
      if (fragmentIndex < 0 || fragmentIndex >= fragments.length) {
        throw new Error('Fragment not found')
      }
      
      const fragment = fragments[fragmentIndex]
      
      return {
        success: true,
        output: {
          fragmentId,
          content: fragment.conteudo || fragment.content || '',
          cellId,
          message: 'Fragment loaded successfully'
        },
        execution_time: performance.now() - startTime
      }
    } catch (error: any) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message || 'Failed to load fragment'
      }
    }
  }
  
  /**
   * Describe the cell's capabilities
   * 
   * @returns Cell metadata with input/output schema
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'fragment-editor-cell',
      name: 'Fragment Editor',
      version: '1.0.0',
      description: 'Create and edit cell fragments with markdown support',
      inputs: {
        action: {
          type: 'enum',
          required: true,
          values: ['create', 'edit', 'load'],
          description: 'Action to perform'
        },
        cellId: {
          type: 'string',
          required: false,
          description: 'Cell ID (required for create/edit)'
        },
        fragmentId: {
          type: 'string',
          required: false,
          description: 'Fragment ID (required for edit/load)'
        },
        content: {
          type: 'string',
          required: false,
          description: 'Fragment content (required for create/edit)'
        }
      },
      outputs: {
        fragmentId: { type: 'string' },
        content: { type: 'string' },
        cellId: { type: 'string' },
        message: { type: 'string' }
      },
      tags: ['content', 'editor', 'fragments', 'markdown']
    }
  }
  
  /**
   * Validate input parameters
   * 
   * @param input - Input parameters to validate
   * @returns Array of validation errors (empty if valid)
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    const { action, cellId, fragmentId, content } = input
    
    // Validate action
    if (!action) {
      errors.push({
        field: 'action',
        message: 'Action is required'
      })
    } else if (!['create', 'edit', 'load'].includes(action)) {
      errors.push({
        field: 'action',
        message: 'Action must be one of: create, edit, load'
      })
    }
    
    // Validate action-specific requirements
    if (action === 'create') {
      if (!cellId) {
        errors.push({
          field: 'cellId',
          message: 'cellId is required for create action'
        })
      }
      if (!content || !content.trim()) {
        errors.push({
          field: 'content',
          message: 'content is required for create action'
        })
      }
    }
    
    if (action === 'edit') {
      if (!cellId) {
        errors.push({
          field: 'cellId',
          message: 'cellId is required for edit action'
        })
      }
      if (!fragmentId) {
        errors.push({
          field: 'fragmentId',
          message: 'fragmentId is required for edit action'
        })
      }
      if (!content || !content.trim()) {
        errors.push({
          field: 'content',
          message: 'content is required for edit action'
        })
      }
    }
    
    if (action === 'load') {
      if (!fragmentId) {
        errors.push({
          field: 'fragmentId',
          message: 'fragmentId is required for load action'
        })
      }
    }
    
    return errors
  }
}
