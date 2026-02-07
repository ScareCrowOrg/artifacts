/**
 * @file example-usage.ts
 * @description Example demonstrating how to use ContentManagerCell as a BaseCell utility
 * 
 * This file shows how other cells (png-generator, svg-generator, etc.) can
 * import and use ContentManagerCell to manage their content persistence.
 */

import { ContentManagerCell } from './ContentManagerCell'
import type { BaseCell, CellResult, CellMetadata, ValidationError } from '@/types/BaseCell'

/**
 * Example: PNG Generator Cell that uses ContentManagerCell
 * 
 * This demonstrates the composition pattern where one cell uses another
 * cell as a utility to handle specific functionality (content persistence).
 */
export class ExamplePngGeneratorCell implements BaseCell {
  // Compose ContentManagerCell as a utility
  private contentManager = new ContentManagerCell()
  
  /**
   * Execute PNG generation and persist the result
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()
    
    try {
      // 1. Validate input
      const errors = this.validate(input)
      if (errors.length > 0) {
        return {
          success: false,
          output: { errors },
          execution_time: performance.now() - startTime,
          error: 'Validation failed'
        }
      }
      
      // 2. Generate PNG (simulated)
      const prompt = input.prompt as string
      const pngData = await this.generatePNG(prompt)
      
      // 3. Persist using ContentManagerCell
      const persistResult = await this.contentManager.execute({
        action: 'persist',
        content_type_id: 'image-png',
        filename: `${this.sanitizeFilename(prompt)}.png`,
        binary: pngData,  // Base64 or ArrayBuffer
        fragments: {
          prompt: prompt,
          generated_at: new Date().toISOString(),
          generator: 'example-png-generator'
        },
        tags: ['generated', 'png', 'example'],
        origin_cell_id: this.cell_instance?.id
      })
      
      if (!persistResult.success) {
        return {
          success: false,
          output: {},
          execution_time: performance.now() - startTime,
          error: `Failed to persist PNG: ${persistResult.error}`
        }
      }
      
      // 4. Return success with content metadata
      return {
        success: true,
        output: {
          content_id: persistResult.output.id,
          data_ref: persistResult.output.data_ref,
          filename: persistResult.output.filename,
          size_bytes: persistResult.output.size_bytes,
          download_url: `/api/content/${persistResult.output.id}/download`
        },
        execution_time: performance.now() - startTime,
        artifacts: [persistResult.output.data_ref],
        execution_steps: ['validate', 'generate_png', 'persist_content']
      }
    } catch (error: any) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message || 'PNG generation failed'
      }
    }
  }
  
  /**
   * Describe cell capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'example-png-generator-cell',
      name: 'Example PNG Generator',
      version: '1.0.0',
      description: 'Generates PNG images from prompts and persists them using ContentManagerCell',
      inputs: {
        prompt: {
          type: 'string',
          description: 'Text prompt for image generation',
          required: true
        }
      },
      outputs: {
        content_id: {
          type: 'string',
          description: 'ID of the persisted content'
        },
        data_ref: {
          type: 'string',
          description: 'R2 storage reference'
        },
        download_url: {
          type: 'string',
          description: 'URL to download the generated PNG'
        }
      },
      tags: ['image', 'generator', 'png', 'example'],
      estimated_duration_seconds: 5.0,
      required_resources: ['backend', 'content-manager-cell']
    }
  }
  
  /**
   * Validate input
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    
    if (!input.prompt) {
      errors.push({ field: 'prompt', message: 'Prompt is required' })
    } else if (typeof input.prompt !== 'string') {
      errors.push({ field: 'prompt', message: 'Prompt must be a string' })
    } else if (input.prompt.length < 3) {
      errors.push({ field: 'prompt', message: 'Prompt must be at least 3 characters' })
    } else if (input.prompt.length > 500) {
      errors.push({ field: 'prompt', message: 'Prompt must be less than 500 characters' })
    }
    
    return errors
  }
  
  /**
   * Setup - Initialize content manager
   */
  async setup(config: any): Promise<void> {
    // Pass setup config to content manager
    await this.contentManager.setup(config)
  }
  
  /**
   * Teardown - Cleanup content manager
   */
  async teardown(): Promise<void> {
    await this.contentManager.teardown()
  }
  
  /**
   * Health check - Verify both generator and content manager are healthy
   */
  async health_check() {
    // Check content manager health
    const cmHealth = await this.contentManager.health_check()
    
    if (!cmHealth.can_execute) {
      return {
        status: 'degraded' as const,
        can_execute: false,
        reason: `Content Manager unhealthy: ${cmHealth.reason}`,
        estimated_recovery_seconds: cmHealth.estimated_recovery_seconds
      }
    }
    
    return {
      status: 'healthy' as const,
      can_execute: true
    }
  }
  
  // Private helper methods
  
  /**
   * Generate PNG (simulated for example)
   */
  private async generatePNG(prompt: string): Promise<string> {
    // In a real implementation, this would call a backend service
    // or use a library to generate an actual PNG
    
    // For this example, return a placeholder Base64 string
    return 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
  }
  
  /**
   * Sanitize filename for storage
   */
  private sanitizeFilename(text: string): string {
    return text
      .substring(0, 50)  // Limit length
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')  // Replace non-alphanumeric with dashes
      .replace(/^-+|-+$/g, '')  // Remove leading/trailing dashes
      || 'generated'  // Fallback if empty
  }
}

/**
 * Example: List existing content
 * 
 * This shows how a cell can query existing content to avoid
 * regenerating assets that already exist.
 */
export async function exampleListContent() {
  const contentManager = new ContentManagerCell()
  
  // List all PNG images
  const result = await contentManager.execute({
    action: 'list',
    filters: {
      content_type_id: 'image-png',
      is_latest: true
    },
    limit: 10,
    offset: 0
  })
  
  if (result.success) {
    const contents = result.output.contents
    console.log(`Found ${contents.length} PNG images:`)
    contents.forEach((content: any) => {
      console.log(`  - ${content.filename} (${content.size_bytes} bytes)`)
    })
  } else {
    console.error('Failed to list contents:', result.error)
  }
}

/**
 * Example: Load existing content
 * 
 * This shows how a cell can retrieve previously generated content
 * using its content ID.
 */
export async function exampleLoadContent(contentId: string) {
  const contentManager = new ContentManagerCell()
  
  // Get presigned URL for the content
  const result = await contentManager.execute({
    action: 'load',
    content_id: contentId,
    direct_download: false  // Use presigned URL (faster)
  })
  
  if (result.success) {
    const url = result.output.presigned_url
    console.log(`Content available at: ${url}`)
    console.log(`URL expires in: ${result.output.presigned_expires_in} seconds`)
    return url
  } else {
    console.error('Failed to load content:', result.error)
    return null
  }
}
