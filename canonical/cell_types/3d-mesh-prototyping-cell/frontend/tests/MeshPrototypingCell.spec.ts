/**
 * @file MeshPrototypingCell.spec.ts
 * @description Unit tests for MeshPrototypingCell — validate(), describe(), execute(), health_check(), getState(), setState()
 *
 * Covers the modified validate() logic (inputImage optional, input_content_id added,
 * "either/or" requirement) and all other public methods to meet Regra 3.1 (90%+ coverage).
 */

import { describe, it, expect, beforeAll, beforeEach, vi } from 'vitest'

// ── Module-level mocks (vitest-hoisted) ──────────────────────────────────────

vi.mock('@/services/apiService.js', () => ({
  default: { fetch: vi.fn() }
}))

vi.mock('@/config/endpoints.js', () => ({
  ENDPOINTS: {
    executeEphemeralCell: 'http://localhost:5050/api/cells/execute-ephemeral',
    systemStatus: 'http://localhost:5050/api/status'
  }
}))

vi.mock('@/utils/logger', () => ({
  createLogger: () => ({
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn()
  })
}))

// ── Real imports (resolved via vitest aliases in vitest.config.js) ────────────

import apiService from '@/services/apiService.js'
import { MeshPrototypingCell } from '../MeshPrototypingCell'
import type { MeshPrototypingInput, GenerationMode } from '../MeshPrototypingCell'

// ── Helpers ──────────────────────────────────────────────────────────────────

const VALID_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='

const VALID_BASE64_DATA_URI = `data:image/png;base64,${VALID_BASE64}`

const VALID_CONTENT_ID = 'b3f7a1e2-8c4d-4f6a-9b0c-1d2e3f4a5b6c'

// ── Suite ────────────────────────────────────────────────────────────────────

describe('MeshPrototypingCell', () => {
  let cell: MeshPrototypingCell

  beforeAll(() => {
    cell = new MeshPrototypingCell()
  })

  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── describe() ─────────────────────────────────────────────────────────────

  describe('describe()', () => {
    it('should return correct cell metadata (id, name, version, tags)', async () => {
      const meta = await cell.describe()

      expect(meta.id).toBe('3d-mesh-prototyping-cell')
      expect(meta.name).toBe('Mesh Prototyping Cell')
      expect(meta.version).toBe('1.0.0')
      expect(meta.tags).toContain('3d-generation')
      expect(meta.tags).toContain('mesh-generation')
      expect(meta.tags).toContain('2d-to-3d')
      expect(meta.tags).toContain('glb')
      expect(meta.required_resources).toContain('backend')
      expect(meta.required_resources).toContain('gpu')
    })

    it('should describe generationMode enum', async () => {
      const meta = await cell.describe()
      expect(meta.inputs.generationMode.enum).toEqual([
        'cloud-api',
        'local-gpu',
        'manual-upload'
      ])
    })

    it('should describe reconstructionParams with all sub-fields', async () => {
      const meta = await cell.describe()
      const props = meta.inputs.reconstructionParams.properties

      expect(props).toBeDefined()
      expect(props.targetFaces).toBeDefined()
      expect(props.enableDracoCompression).toBeDefined()
      expect(props.compressionLevel).toBeDefined()
      expect(props.targetFileSizeMB).toBeDefined()
    })

    it('should describe inputImage as optional', async () => {
      const meta = await cell.describe()
      expect(meta.inputs.inputImage.required).toBe(false)
    })

    it('should describe input_content_id as optional field', async () => {
      const meta = await cell.describe()
      expect(meta.inputs.input_content_id).toBeDefined()
      expect(meta.inputs.input_content_id.type).toBe('string')
      expect(meta.inputs.input_content_id.required).toBe(false)
    })

    it('should list outputs', async () => {
      const meta = await cell.describe()
      expect(meta.outputs.success).toBeDefined()
      expect(meta.outputs.job_id).toBeDefined()
      expect(meta.outputs.glb_url).toBeDefined()
      expect(meta.outputs.message).toBeDefined()
      expect(meta.outputs.error).toBeDefined()
      expect(meta.outputs.metadata).toBeDefined()
    })
  })

  // ── validate() ─────────────────────────────────────────────────────────────

  describe('validate()', () => {
    // ── Required field (either/or) ───────────────────────────────────────────
    it('should reject empty payload (neither inputImage nor input_content_id)', () => {
      const errors = cell.validate({})
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('input')
      expect(errors[0].message).toContain('Either inputImage or input_content_id')
    })

    it('should reject when both fields are empty strings', () => {
      const errors = cell.validate({ inputImage: '', input_content_id: '' })
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('input')
    })

    it('should reject when inputImage is empty string and input_content_id absent', () => {
      const errors = cell.validate({ inputImage: '' })
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('input')
    })

    // ── inputImage valid ─────────────────────────────────────────────────────
    it('should accept valid base64 string (no data URI prefix)', () => {
      const errors = cell.validate({ inputImage: VALID_BASE64 })
      expect(errors).toHaveLength(0)
    })

    it('should accept valid base64 with data URI prefix', () => {
      const errors = cell.validate({ inputImage: VALID_BASE64_DATA_URI })
      expect(errors).toHaveLength(0)
    })

    // ── inputImage invalid ───────────────────────────────────────────────────
    it('should reject non-string inputImage', () => {
      const errors = cell.validate({ inputImage: 12345 as any })
      // 12345 is truthy → enters the block, typeof !== 'string' → pushes error
      expect(errors.length).toBeGreaterThanOrEqual(1)
      expect(errors[0].field).toBe('inputImage')
    })

    it('should reject whitespace-only inputImage string', () => {
      const errors = cell.validate({ inputImage: '   ' })
      // '   ' is truthy → enters the block, trim().length === 0 → pushes error
      expect(errors.length).toBeGreaterThanOrEqual(1)
      expect(errors[0].field).toBe('inputImage')
    })

    it('should reject invalid base64 format (non-base64 characters)', () => {
      const errors = cell.validate({ inputImage: 'not-valid-base64!!!' })
      expect(errors.length).toBeGreaterThanOrEqual(1)
      expect(errors[0].field).toBe('inputImage')
      expect(errors[0].message).toContain('valid base64')
    })

    // ── input_content_id valid ───────────────────────────────────────────────
    it('should accept only valid input_content_id (no inputImage)', () => {
      const errors = cell.validate({ input_content_id: VALID_CONTENT_ID })
      expect(errors).toHaveLength(0)
    })

    // ── input_content_id invalid ─────────────────────────────────────────────
    it('should reject non-string input_content_id', () => {
      const errors = cell.validate({ input_content_id: 456 as any })
      // 456 is truthy → enters block, typeof !== 'string' → pushes error
      expect(errors.length).toBeGreaterThanOrEqual(1)
      expect(errors.some(e => e.field === 'input_content_id')).toBe(true)
    })

    it('should reject whitespace-only input_content_id', () => {
      const errors = cell.validate({ input_content_id: '   ' })
      // '   ' is truthy → enters block, trim().length === 0 → pushes error
      expect(errors.length).toBeGreaterThanOrEqual(1)
      expect(errors.some(e => e.field === 'input_content_id')).toBe(true)
    })

    // ── Combined ─────────────────────────────────────────────────────────────
    it('should flag invalid inputImage even when valid input_content_id present', () => {
      const errors = cell.validate({
        inputImage: 'not-valid!!!',
        input_content_id: VALID_CONTENT_ID
      })
      // inputImage fails base64 validation, input_content_id is valid
      expect(errors.length).toBeGreaterThanOrEqual(1)
      expect(errors[0].field).toBe('inputImage')
      // Should NOT have an "input" field error (either/or satisfied by content_id)
      expect(errors.some(e => e.field === 'input')).toBe(false)
    })

    it('should pass when both fields provided and valid', () => {
      const errors = cell.validate({
        inputImage: VALID_BASE64,
        input_content_id: VALID_CONTENT_ID
      })
      expect(errors).toHaveLength(0)
    })

    // ── generationMode ───────────────────────────────────────────────────────
    it('should reject invalid generation mode', () => {
      const errors = cell.validate({
        inputImage: VALID_BASE64,
        generationMode: 'invalid-mode'
      })
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('generationMode')
      expect(errors[0].message).toContain('must be one of')
    })

    it('should accept valid generation modes', () => {
      const modes: GenerationMode[] = ['cloud-api', 'local-gpu', 'manual-upload']
      modes.forEach(mode => {
        const errors = cell.validate({ inputImage: VALID_BASE64, generationMode: mode })
        expect(errors).toHaveLength(0)
      })
    })

    // ── reconstructionParams — targetFaces ───────────────────────────────────
    it('should reject targetFaces below minimum (100)', () => {
      const errors = cell.validate({
        inputImage: VALID_BASE64,
        reconstructionParams: { targetFaces: 50 }
      })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toContain('targetFaces')
    })

    it('should reject targetFaces above maximum (100000)', () => {
      const errors = cell.validate({
        inputImage: VALID_BASE64,
        reconstructionParams: { targetFaces: 200000 }
      })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toContain('targetFaces')
    })

    it('should reject non-number targetFaces', () => {
      const errors = cell.validate({
        inputImage: VALID_BASE64,
        reconstructionParams: { targetFaces: 'many' as any }
      })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toContain('targetFaces')
    })

    // ── reconstructionParams — enableDracoCompression ────────────────────────
    it('should reject non-boolean enableDracoCompression', () => {
      const errors = cell.validate({
        inputImage: VALID_BASE64,
        reconstructionParams: { enableDracoCompression: 'yes' as any }
      })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toContain('enableDracoCompression')
    })

    // ── reconstructionParams — compressionLevel ──────────────────────────────
    it('should reject compressionLevel above maximum (10)', () => {
      const errors = cell.validate({
        inputImage: VALID_BASE64,
        reconstructionParams: { compressionLevel: 15 }
      })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toContain('compressionLevel')
    })

    it('should reject compressionLevel below minimum (0)', () => {
      const errors = cell.validate({
        inputImage: VALID_BASE64,
        reconstructionParams: { compressionLevel: -1 }
      })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toContain('compressionLevel')
    })

    it('should reject non-number compressionLevel', () => {
      const errors = cell.validate({
        inputImage: VALID_BASE64,
        reconstructionParams: { compressionLevel: 'high' as any }
      })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toContain('compressionLevel')
    })

    // ── reconstructionParams — targetFileSizeMB ──────────────────────────────
    it('should reject non-positive targetFileSizeMB', () => {
      const errors = cell.validate({
        inputImage: VALID_BASE64,
        reconstructionParams: { targetFileSizeMB: 0 }
      })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toContain('targetFileSizeMB')
    })

    it('should reject negative targetFileSizeMB', () => {
      const errors = cell.validate({
        inputImage: VALID_BASE64,
        reconstructionParams: { targetFileSizeMB: -5 }
      })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toContain('targetFileSizeMB')
    })

    it('should reject non-number targetFileSizeMB', () => {
      const errors = cell.validate({
        inputImage: VALID_BASE64,
        reconstructionParams: { targetFileSizeMB: 'large' as any }
      })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toContain('targetFileSizeMB')
    })

    // ── reconstructionParams — valid ─────────────────────────────────────────
    it('should accept valid reconstruction parameters', () => {
      const errors = cell.validate({
        inputImage: VALID_BASE64,
        reconstructionParams: {
          targetFaces: 10000,
          enableDracoCompression: true,
          compressionLevel: 7,
          targetFileSizeMB: 5
        }
      })
      expect(errors).toHaveLength(0)
    })

    // ── Mixed: multiple errors ───────────────────────────────────────────────
    it('should return multiple errors for multiple invalid fields', () => {
      const errors = cell.validate({
        inputImage: '',                    // falsy → no base64 check, but contributes to "either/or"
        input_content_id: '',              // falsy → no string check
        generationMode: 'bad-mode',
        reconstructionParams: {
          targetFaces: 500000,
          enableDracoCompression: 'nope' as any
        }
      })
      // Expected: 1 error for "either/or" + 1 for generationMode + 1 for targetFaces + 1 for draco
      expect(errors.length).toBe(4)
    })
  })

  // ── execute() ──────────────────────────────────────────────────────────────

  describe('execute()', () => {
    it('should return validation error for invalid input', async () => {
      const result = await cell.execute({})
      expect(result.success).toBe(false)
      expect(result.error).toBe('Validation failed')
      expect(result.output.errors).toBeDefined()
      expect(result.output.errors.length).toBeGreaterThan(0)
    })

    it('should call backend API with correct payload on valid input', async () => {
      const mockResponse = {
        ok: true,
        json: vi.fn().mockResolvedValue({
          success: true,
          glb_url: 'http://example.com/model.glb',
          message: 'Mesh generated successfully'
        })
      }
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const result = await cell.execute({
        inputImage: VALID_BASE64,
        generationMode: 'cloud-api',
        reconstructionParams: { targetFaces: 10000, enableDracoCompression: true }
      })

      expect(apiService.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
          body: expect.stringContaining('3d-mesh-prototyping-cell')
        })
      )
      expect(result.success).toBe(true)
      expect(result.output.glb_url).toBe('http://example.com/model.glb')
      expect(result.artifacts).toHaveLength(1)
      expect(result.artifacts![0]).toBe('http://example.com/model.glb')
    })

    it('should handle local-gpu mode returning job_id', async () => {
      const mockResponse = {
        ok: true,
        json: vi.fn().mockResolvedValue({
          success: true,
          job_id: 'job-12345',
          message: 'Job queued for processing'
        })
      }
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const result = await cell.execute({
        inputImage: VALID_BASE64,
        generationMode: 'local-gpu'
      })

      expect(result.success).toBe(true)
      expect(result.output.job_id).toBe('job-12345')
      expect(result.artifacts).toHaveLength(0) // No GLB yet — async
    })

    it('should handle backend errors (non-ok response)', async () => {
      const mockResponse = {
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        text: vi.fn().mockResolvedValue('Server error details')
      }
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const result = await cell.execute({ inputImage: VALID_BASE64 })
      expect(result.success).toBe(false)
      expect(result.error).toContain('Backend execution failed')
    })

    it('should handle network exceptions gracefully', async () => {
      vi.mocked(apiService.fetch).mockRejectedValue(new Error('Connection timeout'))

      const result = await cell.execute({ inputImage: VALID_BASE64 })
      expect(result.success).toBe(false)
      expect(result.error).toContain('Connection timeout')
    })

    it('should work with input_content_id instead of inputImage', async () => {
      const mockResponse = {
        ok: true,
        json: vi.fn().mockResolvedValue({
          success: true,
          glb_url: 'http://example.com/model.glb',
          message: 'Mesh generated from content_id'
        })
      }
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const result = await cell.execute({
        input_content_id: VALID_CONTENT_ID,
        generationMode: 'cloud-api'
      })

      expect(result.success).toBe(true)
      expect(result.output.message).toContain('content_id')
    })

    it('should include mesh_data as artifact when no glb_url', async () => {
      const mockResponse = {
        ok: true,
        json: vi.fn().mockResolvedValue({
          success: true,
          mesh_data: 'base64meshdata==',
          message: 'Mesh generated'
        })
      }
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const result = await cell.execute({ inputImage: VALID_BASE64 })
      expect(result.success).toBe(true)
      expect(result.artifacts).toHaveLength(1)
      expect(result.artifacts![0]).toBe('base64meshdata==')
    })
  })

  // ── health_check() ─────────────────────────────────────────────────────────

  describe('health_check()', () => {
    it('should return healthy when backend is reachable', async () => {
      vi.mocked(apiService.fetch).mockResolvedValue({ ok: true } as Response)

      const health = await cell.health_check()
      expect(health.status).toBe('healthy')
      expect(health.can_execute).toBe(true)
    })

    it('should return degraded when backend returns error status', async () => {
      vi.mocked(apiService.fetch).mockResolvedValue({ ok: false, status: 503 } as Response)

      const health = await cell.health_check()
      expect(health.status).toBe('degraded')
      expect(health.can_execute).toBe(false)
      expect(health.reason).toContain('unreachable')
    })

    it('should return unavailable on network exception', async () => {
      vi.mocked(apiService.fetch).mockRejectedValue(new Error('Network unreachable'))

      const health = await cell.health_check()
      expect(health.status).toBe('unavailable')
      expect(health.can_execute).toBe(false)
      expect(health.reason).toContain('Network unreachable')
    })
  })

  // ── getState() / setState() ────────────────────────────────────────────────

  describe('getState() and setState()', () => {
    it('getState should return default values before any state is set', () => {
      const state = cell.getState()
      expect(state).toHaveProperty('status', 'idle')
      expect(state).toHaveProperty('input_content_id', '')
      expect(state).toHaveProperty('input_data_ref', '')
      expect(state).toHaveProperty('mesh_content_id', '')
      expect(state).toHaveProperty('jobId', '')
      expect(state).toHaveProperty('isGenerating', false)
      expect(state).toHaveProperty('error', '')
    })

    it('setState should restore all fields from persisted data', () => {
      cell.setState({
        input_content_id: VALID_CONTENT_ID,
        input_data_ref: '/runtime/user/abc123/image.png',
        mesh_content_id: 'mesh-uuid-456',
        jobId: 'job-789',
        isGenerating: true,
        error: ''
      })

      const state = cell.getState()
      expect(state.input_content_id).toBe(VALID_CONTENT_ID)
      expect(state.input_data_ref).toBe('/runtime/user/abc123/image.png')
      expect(state.mesh_content_id).toBe('mesh-uuid-456')
      expect(state.jobId).toBe('job-789')
      expect(state.isGenerating).toBe(true)
      expect(state.error).toBe('')
    })

    it('setState should handle partial data with defaults for missing fields', () => {
      cell.setState({ input_content_id: VALID_CONTENT_ID })

      const state = cell.getState()
      expect(state.input_content_id).toBe(VALID_CONTENT_ID)
      expect(state.input_data_ref).toBe('')   // default
      expect(state.mesh_content_id).toBe('')   // default
      expect(state.jobId).toBe('')             // default
      expect(state.isGenerating).toBe(false)   // default
    })

    it('setState should handle legacy content_id field name', () => {
      cell.setState({ content_id: 'legacy-uuid' })

      const state = cell.getState()
      expect(state.input_content_id).toBe('legacy-uuid')
    })
  })

  // ── setup() / teardown() ──────────────────────────────────────────────────

  describe('setup() and teardown()', () => {
    it('setup should resolve without error', async () => {
      await expect(
        cell.setup({
          has_gpu: true,
          gpu_vram_mb: 12000,
          cpu_cores: 16,
          headless_mode: false,
          timeout_seconds: 600
        })
      ).resolves.toBeUndefined()
    })

    it('teardown should resolve without error', async () => {
      await expect(cell.teardown()).resolves.toBeUndefined()
    })
  })
})
