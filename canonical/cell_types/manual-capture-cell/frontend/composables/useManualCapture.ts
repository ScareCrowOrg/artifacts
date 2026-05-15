/**
 * @file useManualCapture.ts
 * @description Composable for manual-capture-cell ephemeral cell functionality
 *
 * Delegates data logic to ManualCaptureCell (BaseCell) and handles
 * UI-side effects (creating file-editor-v2 cells in the layout).
 *
 * Key Behaviors:
 * - This is an EPHEMERAL cell - no state is persisted
 * - Actions create NEW file-editor-v2 cells instead of persisting
 * - Input content is cleared after each action
 */

import { ref, type Ref } from 'vue'
import type { ManualCaptureCellData } from '../types'
import type { ManualCaptureCell } from '../ManualCaptureCell'

export interface UseManualCaptureReturn {
  inputContent: Ref<string>
  isProcessing: Ref<boolean>
  captureContent: (createCellFn: (content: string, fileName: string, language: string) => Promise<void>) => Promise<void>
  generateWireframe: (createCellFn: (content: string, fileName: string, language: string) => Promise<void>) => Promise<void>
  insertContent: (content: string) => void
  validationErrors: Ref<string[]>
}

/**
 * Composable for manual capture cell functionality
 * @param cellData - Cell data (ephemeral - not persisted)
 * @param cellInstance - ManualCaptureCell instance for validation and execution
 * @returns Manual capture interface
 */
export function useManualCapture(
  cellData: Ref<ManualCaptureCellData>,
  cellInstance: ManualCaptureCell
): UseManualCaptureReturn {
  const inputContent = ref<string>('')
  const isProcessing = ref<boolean>(false)
  const validationErrors = ref<string[]>([])

  /**
   * Capture content using BaseCell and create a file-editor-v2 cell
   * @param createCellFn - Function to create a new file-editor-v2 cell
   */
  async function captureContent(
    createCellFn: (content: string, fileName: string, language: string) => Promise<void>
  ): Promise<void> {
    const content = inputContent.value.trim()

    // Validate via BaseCell
    validationErrors.value = []
    const errors = cellInstance.validate({ action: 'capture', content })
    if (errors.length > 0) {
      validationErrors.value = errors.map(e => e.message)
      throw new Error(errors[0].message)
    }

    isProcessing.value = true
    try {
      // Execute via BaseCell
      const result = await cellInstance.execute({ action: 'capture', content })
      if (!result.success) {
        throw new Error(result.error || 'Capture failed')
      }

      // Create file-editor-v2 cell with the result
      await createCellFn(
        result.output.content,
        result.output.fileName,
        result.output.language
      )

      inputContent.value = ''
    } finally {
      isProcessing.value = false
    }
  }

  /**
   * Generate wireframe using BaseCell and create a file-editor-v2 cell
   * @param createCellFn - Function to create a new file-editor-v2 cell
   */
  async function generateWireframe(
    createCellFn: (content: string, fileName: string, language: string) => Promise<void>
  ): Promise<void> {
    const htmlContent = inputContent.value.trim()

    // Validate via BaseCell
    validationErrors.value = []
    const errors = cellInstance.validate({ action: 'wireframe', content: htmlContent })
    if (errors.length > 0) {
      validationErrors.value = errors.map(e => e.message)
      throw new Error(errors[0].message)
    }

    isProcessing.value = true
    try {
      // Execute via BaseCell (wireframe generation logic lives in the cell)
      const result = await cellInstance.execute({ action: 'wireframe', content: htmlContent })
      if (!result.success) {
        throw new Error(result.error || 'Wireframe generation failed')
      }

      await createCellFn(
        result.output.content,
        result.output.fileName,
        result.output.language
      )

      inputContent.value = ''
    } finally {
      isProcessing.value = false
    }
  }

  /**
   * Insert content programmatically (e.g., from external sources)
   * @param content - Content to insert
   */
  function insertContent(content: string): void {
    inputContent.value = content
  }

  return {
    inputContent,
    isProcessing,
    captureContent,
    generateWireframe,
    insertContent,
    validationErrors,
  }
}
