/**
 * @file useManualCapture.ts
 * @description Composable for manual-capture-cell ephemeral cell functionality
 * 
 * This composable provides the core logic for the manual capture cell, including:
 * - Content capture functionality
 * - Wireframe generation from HTML
 * - Creating file-editor-v2 cells with captured/generated content
 * 
 * Key Behaviors:
 * - This is an EPHEMERAL cell - no state is persisted
 * - Actions create NEW file-editor-v2 cells instead of persisting
 * - Input content is cleared after each action
 */

import { ref, type Ref } from 'vue'
import type { ManualCaptureCellData } from '../types'

export interface UseManualCaptureReturn {
  inputContent: Ref<string>
  isProcessing: Ref<boolean>
  captureContent: (createCellFn: (content: string, fileName: string, language: string) => Promise<void>) => Promise<void>
  generateWireframe: (createCellFn: (content: string, fileName: string, language: string) => Promise<void>) => Promise<void>
  insertContent: (content: string) => void
}

/**
 * Composable for manual capture cell functionality
 * @param cellData - Cell data (ephemeral - not persisted)
 * @returns Manual capture interface
 */
export function useManualCapture(cellData: Ref<ManualCaptureCellData>): UseManualCaptureReturn {
  const inputContent = ref<string>('')
  const isProcessing = ref<boolean>(false)

  /**
   * Generate ASCII wireframe from HTML string
   * @param htmlString - HTML content to parse
   * @returns ASCII wireframe representation
   */
  function generateWireframeAscii(htmlString: string): string {
    const parser = new DOMParser()
    const doc = parser.parseFromString(htmlString, 'text/html')

    // Generate element signature (tag + classes)
    function getSignature(elemento: Element): string {
      return elemento.tagName.toLowerCase() + '|' + (elemento.className || '')
    }

    // Draw box for element
    function drawBox(conteudo: string, nivel: number): string {
      const indent = '  '.repeat(nivel)
      return `${indent}+--- ${conteudo} ---+`
    }

    // Traverse DOM tree recursively
    function traverse(elemento: Element, nivel: number = 0): string {
      if (elemento.nodeType !== 1) return ''

      const tag = elemento.tagName.toLowerCase()
      const classes = elemento.className
        ? `.${elemento.className.split(' ').join(' .')}`
        : ''
      const texto = elemento.textContent?.trim() || ''
      let conteudo = `<${tag}${classes}>`
      if (texto && texto.length < 40) conteudo += ` "${texto}"`

      let resultado = drawBox(conteudo, nivel)

      // Group children by signature
      const filhos = Array.from(elemento.children)
      const grupos: Record<string, Element[]> = {}
      filhos.forEach((child) => {
        const sig = getSignature(child)
        if (!grupos[sig]) grupos[sig] = []
        grupos[sig].push(child)
      })

      for (const sig in grupos) {
        const grupo = grupos[sig]
        if (grupo.length > 1) {
          // Show first and indicate repetitions
          resultado += '\n' + traverse(grupo[0], nivel + 1)
          resultado += `\n${'  '.repeat(nivel + 1)}... (${grupo.length - 1} repetidos)`
        } else {
          resultado += '\n' + traverse(grupo[0], nivel + 1)
        }
      }

      return resultado
    }

    let resultado = ''
    for (const child of Array.from(doc.body.children)) {
      resultado += traverse(child) + '\n'
    }

    return resultado
  }

  /**
   * Capture content and create a file-editor-v2 cell with it
   * @param createCellFn - Function to create a new file-editor-v2 cell
   */
  async function captureContent(
    createCellFn: (content: string, fileName: string, language: string) => Promise<void>
  ): Promise<void> {
    const content = inputContent.value.trim()
    if (!content) {
      throw new Error('No content to capture')
    }

    isProcessing.value = true
    try {
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19)
      const fileName = `captured-content-${timestamp}.md`
      
      await createCellFn(content, fileName, 'markdown')
      
      // Clear input after successful capture
      inputContent.value = ''
    } finally {
      isProcessing.value = false
    }
  }

  /**
   * Generate wireframe and create a file-editor-v2 cell with it
   * @param createCellFn - Function to create a new file-editor-v2 cell
   */
  async function generateWireframe(
    createCellFn: (content: string, fileName: string, language: string) => Promise<void>
  ): Promise<void> {
    const htmlContent = inputContent.value.trim()
    if (!htmlContent) {
      throw new Error('No HTML content to generate wireframe from')
    }

    isProcessing.value = true
    try {
      const wireframeAscii = generateWireframeAscii(htmlContent)
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19)
      const fileName = `wireframe-${timestamp}.txt`
      
      await createCellFn(wireframeAscii, fileName, 'plaintext')
      
      // Clear input after successful generation
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
  }
}
