/**
 * @file ManualCaptureCell.ts
 * @description ManualCaptureCell - BaseCell implementation for manual content capture and wireframe generation
 *
 * Provides two actions:
 * - 'capture': Captures raw text content and returns it as a markdown file payload
 * - 'wireframe': Parses HTML content and generates an ASCII wireframe representation
 *
 * Part of BaseCell v1.0 Framework Implementation
 */

import { BaseCell, createHealthyResult } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError, EnvironmentConfig, HealthCheckResult } from '@/types/BaseCell'

/**
 * ManualCaptureCell - Ephemeral cell for manual content capture
 *
 * This cell handles two distinct workflows:
 * 1. Content Capture: Takes raw text and returns it as captured markdown content
 * 2. Wireframe Generation: Parses HTML DOM and generates ASCII wireframe diagrams
 *
 * The cell is ephemeral (non-persisted) - results are used to create
 * file-editor-v2 cells in the workspace via the View.vue layer.
 *
 * @example
 * ```typescript
 * const cell = new ManualCaptureCell()
 *
 * // Capture content
 * const result = await cell.execute({
 *   action: 'capture',
 *   content: '# Hello World'
 * })
 * // => { success: true, output: { content: '# Hello World', fileName: 'captured-content-...', language: 'markdown' } }
 *
 * // Generate wireframe
 * const result = await cell.execute({
 *   action: 'wireframe',
 *   content: '<div><h1>Title</h1><p>Text</p></div>'
 * })
 * // => { success: true, output: { content: '+--- <div> ---+\\n  +--- <h1> "Title" ---+...', fileName: 'wireframe-...', language: 'plaintext' } }
 * ```
 */
export class ManualCaptureCell extends BaseCell {
  /**
   * Execute manual capture cell action
   *
   * Actions:
   * - 'capture': Returns content as-is for file editor creation
   * - 'wireframe': Parses HTML and generates ASCII wireframe
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()

    try {
      const { action, content } = input

      if (action === 'capture') {
        if (!content || !content.trim()) {
          return {
            success: false,
            output: {},
            execution_time: performance.now() - startTime,
            error: 'No content to capture'
          }
        }

        const timestamp = this.generateTimestamp()
        return {
          success: true,
          output: {
            content: content.trim(),
            fileName: `captured-content-${timestamp}.md`,
            language: 'markdown'
          },
          execution_time: performance.now() - startTime,
          execution_steps: ['validate', 'capture']
        }
      }

      if (action === 'wireframe') {
        if (!content || !content.trim()) {
          return {
            success: false,
            output: {},
            execution_time: performance.now() - startTime,
            error: 'No HTML content to generate wireframe from'
          }
        }

        const wireframe = this.generateWireframeAscii(content)
        const timestamp = this.generateTimestamp()
        return {
          success: true,
          output: {
            content: wireframe,
            fileName: `wireframe-${timestamp}.txt`,
            language: 'plaintext'
          },
          execution_time: performance.now() - startTime,
          execution_steps: ['validate', 'parse-html', 'generate-wireframe']
        }
      }

      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: `Unknown action: ${action}. Supported actions: 'capture', 'wireframe'`
      }
    } catch (error: any) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message || 'Manual capture execution failed'
      }
    }
  }

  /**
   * Describe manual capture cell capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'manual-capture-cell',
      name: 'Manual Capture',
      version: '1.0.0',
      description: 'Ephemeral cell for manual content capture and wireframe generation. Captures text content or parses HTML into ASCII wireframe diagrams.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform: "capture" or "wireframe"',
          required: true,
          enum: ['capture', 'wireframe']
        },
        content: {
          type: 'string',
          description: 'Text content to capture (for "capture") or HTML to parse (for "wireframe")',
          required: true
        }
      },
      outputs: {
        content: {
          type: 'string',
          description: 'Captured content or generated wireframe ASCII'
        },
        fileName: {
          type: 'string',
          description: 'Suggested file name for the file-editor-v2 cell'
        },
        language: {
          type: 'string',
          description: 'Language for syntax highlighting (markdown or plaintext)'
        }
      },
      tags: ['capture', 'utility', 'data-entry', 'headless-capable'],
      estimated_duration_seconds: 0.01,
      required_resources: []
    }
  }

  /**
   * Validate input before execution
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    if (!input.action) {
      errors.push({ field: 'action', message: 'Action is required ("capture" or "wireframe")' })
    } else if (typeof input.action !== 'string') {
      errors.push({ field: 'action', message: 'Action must be a string' })
    } else if (input.action !== 'capture' && input.action !== 'wireframe') {
      errors.push({ field: 'action', message: 'Action must be "capture" or "wireframe"' })
    }

    if (!input.content || !input.content.trim()) {
      errors.push({ field: 'content', message: 'Content is required' })
    } else if (typeof input.content !== 'string') {
      errors.push({ field: 'content', message: 'Content must be a string' })
    }

    return errors
  }

  /**
   * Setup (optional) - ManualCaptureCell needs no initialization
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    // No-op: this cell has no external dependencies
  }

  /**
   * Teardown (optional) - ManualCaptureCell needs no cleanup
   */
  async teardown(): Promise<void> {
    // No-op
  }

  /**
   * Health check (optional) - Always healthy (no external deps)
   */
  async health_check(): Promise<HealthCheckResult> {
    return createHealthyResult()
  }

  /**
   * Generate ASCII wireframe from HTML string
   * Parses the DOM tree and creates a visual representation
   *
   * @param htmlString - HTML content to parse
   * @returns ASCII wireframe representation
   */
  private generateWireframeAscii(htmlString: string): string {
    const parser = new DOMParser()
    const doc = parser.parseFromString(htmlString, 'text/html')

    function getSignature(elemento: Element): string {
      return elemento.tagName.toLowerCase() + '|' + (elemento.className || '')
    }

    function drawBox(conteudo: string, nivel: number): string {
      const indent = '  '.repeat(nivel)
      return `${indent}+--- ${conteudo} ---+`
    }

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
   * Generate ISO timestamp string safe for filenames
   */
  private generateTimestamp(): string {
    return new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19)
  }
}
