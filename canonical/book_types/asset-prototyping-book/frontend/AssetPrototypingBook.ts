/**
 * @file AssetPrototypingBook.ts
 * @description AssetPrototypingBook - DAG-based orchestrator for 3D asset creation
 * 
 * This book demonstrates the BaseBook pattern by orchestrating PNG generation
 * and 3D mesh prototyping cells to create complete 3D assets from text prompts.
 * 
 * It replaces the orchestration logic previously embedded in AssetPrototypingCell,
 * properly separating orchestration concerns from atomic cell execution.
 * 
 * DAG Workflow:
 * 1. generate_texture (PngGeneratorCell) - Generate texture from prompt
 * 2. generate_mesh (MeshPrototypingCell) - Create 3D mesh from texture
 * 3. Output aggregation - Combine results into final asset
 * 
 * Part of BaseBook v1.0 Framework - Refactoring of PR 2309
 */

import { AbstractBaseBook, registerCellType } from '@/types/BaseBookImpl'
import type { DAGDefinition } from '@/types/BaseBook'
import type { CellMetadata, ExecutionContext } from '@/types/BaseCell'
import { PngGeneratorCell } from '../../../cell_types/png-generator-cell/frontend/PngGeneratorCell'
import { MeshPrototypingCell } from '../../../cell_types/3d-mesh-prototyping-cell/frontend/MeshPrototypingCell'
import { createLogger } from '@/utils/logger'

const log = createLogger('books:AssetPrototyping')

/**
 * Asset prototyping book input interface
 */
export interface AssetPrototypingBookInput {
  /** Text prompt describing the asset to generate */
  prompt: string
  
  /** Optional negative prompt to exclude unwanted features */
  negativePrompt?: string
  
  /** Enable 3D asset mode for PNG generation */
  asset3dMode?: boolean
  
  /** Mesh reconstruction parameters */
  reconstructionParams?: {
    targetFaces?: number
    enableDracoCompression?: boolean
    compressionLevel?: number
  }
  
  /** Generation mode for mesh creation */
  generationMode?: 'cloud-api' | 'local-gpu' | 'manual-upload'
}

/**
 * Asset prototyping book output interface
 */
export interface AssetPrototypingBookOutput {
  /** Base64-encoded generated texture PNG */
  texturePng: string
  
  /** URL to download the generated GLB file */
  meshGlbUrl?: string
  
  /** Job ID for async processing (local-gpu mode) */
  jobId?: string
  
  /** Success message */
  message: string
  
  /** Execution metadata */
  metadata: {
    textureGenTime: number
    meshGenTime: number
    totalTime: number
    prompt: string
  }
}

/**
 * Register required cell types
 * This should be called once during application initialization
 */
export function registerAssetPrototypingCells(): void {
  registerCellType('png-generator-cell', () => new PngGeneratorCell())
  registerCellType('3d-mesh-prototyping-cell', () => new MeshPrototypingCell())
  
  log.debug('Registered cell types for AssetPrototypingBook')
}

/**
 * AssetPrototypingBook - Complete 3D asset prototyping workflow
 * 
 * This book orchestrates PNG generation and 3D mesh creation to produce
 * complete textured 3D assets from text prompts.
 * 
 * Key Improvements Over AssetPrototypingCell:
 * - Declarative DAG definition (no manual orchestration)
 * - Automatic state transfer between cells
 * - Parallel-safe cell execution
 * - Reusable cells (PngGeneratorCell, MeshPrototypingCell)
 * - Testable orchestration logic
 * 
 * @example
 * ```typescript
 * // Register cells first (once per application)
 * registerAssetPrototypingCells()
 * 
 * // Create and use book
 * const book = new AssetPrototypingBook()
 * await book.setup({ headless_mode: true })
 * 
 * const result = await book.execute({
 *   prompt: 'a fantasy sword with ornate handle',
 *   asset3dMode: true,
 *   generationMode: 'cloud-api'
 * })
 * 
 * console.log(result.output.texturePng) // Base64 PNG
 * console.log(result.output.meshGlbUrl) // URL to GLB file
 * 
 * await book.teardown()
 * ```
 */
export class AssetPrototypingBook extends AbstractBaseBook {
  /**
   * Define the DAG workflow for asset prototyping
   * 
   * Nodes:
   * - generate_texture: Creates texture PNG from prompt
   * - generate_mesh: Creates 3D mesh from texture
   * 
   * Dependencies:
   * - generate_mesh depends on generate_texture (needs the PNG)
   */
  getDAG(): DAGDefinition {
    return {
      nodes: [
        {
          id: 'generate_texture',
          cellType: 'png-generator-cell',
          label: 'Generate Texture PNG',
          // Input is a function that reads from book input
          input: (context: ExecutionContext) => ({
            action: 'generate',
            prompt: context.bookInput.prompt,
            negativePrompt: context.bookInput.negativePrompt,
            asset3dMode: context.bookInput.asset3dMode ?? true
          })
        },
        {
          id: 'generate_mesh',
          cellType: '3d-mesh-prototyping-cell',
          label: 'Generate 3D Mesh',
          // Input uses output from generate_texture node
          input: (context: ExecutionContext) => ({
            inputImage: context.outputs.generate_texture?.generatedPng,
            reconstructionParams: context.bookInput.reconstructionParams,
            generationMode: context.bookInput.generationMode ?? 'cloud-api'
          })
        }
      ],
      edges: [
        {
          from: 'generate_texture',
          to: 'generate_mesh'
        }
      ]
    }
  }
  
  /**
   * Describe the book's capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'asset-prototyping-book',
      name: 'Asset Prototyping Book',
      version: '1.0.0',
      description: 'Complete 3D asset prototyping workflow. Orchestrates PNG generation and mesh prototyping to create textured 3D assets from text prompts.',
      inputs: {
        prompt: {
          type: 'string',
          description: 'Text description of the asset to generate',
          required: true,
          example: 'a fantasy sword with ornate handle'
        },
        negativePrompt: {
          type: 'string',
          description: 'Features to exclude from generation',
          required: false,
          example: 'blurry, low quality'
        },
        asset3dMode: {
          type: 'boolean',
          description: 'Enable 3D asset optimization mode',
          required: false,
          default: true
        },
        reconstructionParams: {
          type: 'object',
          description: 'Mesh reconstruction parameters',
          required: false,
          properties: {
            targetFaces: { type: 'number', description: 'Target face count for mesh' },
            enableDracoCompression: { type: 'boolean', description: 'Enable Draco compression' },
            compressionLevel: { type: 'number', description: 'Compression level (0-10)' }
          }
        },
        generationMode: {
          type: 'string',
          description: 'Mesh generation mode',
          required: false,
          default: 'cloud-api',
          enum: ['cloud-api', 'local-gpu', 'manual-upload']
        }
      },
      outputs: {
        texturePng: {
          type: 'string',
          description: 'Base64-encoded texture PNG'
        },
        meshGlbUrl: {
          type: 'string',
          description: 'URL to download generated GLB file'
        },
        jobId: {
          type: 'string',
          description: 'Job ID for async processing (local-gpu mode)'
        },
        message: {
          type: 'string',
          description: 'Success or status message'
        },
        metadata: {
          type: 'object',
          description: 'Execution timing and metadata'
        }
      },
      tags: ['3d', 'asset', 'book', 'composition', 'pipeline', 'ai-generation', 'headless-capable'],
      estimated_duration_seconds: 30,
      required_resources: ['backend', 'stable-diffusion', '3d-generation-api'],
      llm_config: {
        bookType: 'dag-orchestrator',
        composedCells: ['png-generator-cell', '3d-mesh-prototyping-cell'],
        pipelineType: 'sequential',
        canFailPartially: false
      }
    }
  }
  
  /**
   * Aggregate output from node results
   * Transforms DAG outputs into the expected book output format
   */
  protected aggregateOutput(context: ExecutionContext, dag: DAGDefinition): Record<string, any> {
    const textureOutput = context.outputs.generate_texture
    const meshOutput = context.outputs.generate_mesh
    
    const output: AssetPrototypingBookOutput = {
      texturePng: textureOutput?.generatedPng || '',
      meshGlbUrl: meshOutput?.glb_url,
      jobId: meshOutput?.job_id,
      message: 'Asset prototyping completed successfully',
      metadata: {
        textureGenTime: textureOutput?.execution_time || 0,
        meshGenTime: meshOutput?.execution_time || 0,
        totalTime: performance.now() - context.metadata.startTime,
        prompt: context.bookInput.prompt
      }
    }
    
    return output
  }
}
