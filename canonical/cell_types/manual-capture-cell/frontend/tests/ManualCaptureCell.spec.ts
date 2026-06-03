/**
 * @file ManualCaptureCell.spec.ts
 * @description Unit tests for ManualCaptureCell — real import via BaseCell pattern
 *
 * ManualCaptureCell is a pure frontend cell (no backend, no apiService).
 * It only imports from @/types/BaseCell — no mocks needed.
 *
 * Ref: artifacts/docs/TESTING_ARTIFACTS.md
 */

import { describe, it, expect, beforeAll } from 'vitest'
import { ManualCaptureCell } from '../ManualCaptureCell'

describe('ManualCaptureCell', () => {
  let cell: ManualCaptureCell

  beforeAll(() => {
    cell = new ManualCaptureCell()
  })

  // ── execute() — capture ──────────────────────────────────────────────────

  describe('execute() — capture', () => {
    it('captures content successfully', async () => {
      const result = await cell.execute({
        action: 'capture',
        content: '# Hello World\n\nThis is captured content.'
      })

      expect(result.success).toBe(true)
      expect(result.output.content).toBe('# Hello World\n\nThis is captured content.')
      expect(result.output.fileName).toMatch(/^captured-content-.*\.md$/)
      expect(result.output.language).toBe('markdown')
      expect(result.execution_time).toBeGreaterThanOrEqual(0)
    })

    it('trims whitespace from captured content', async () => {
      const result = await cell.execute({
        action: 'capture',
        content: '  text with whitespace  '
      })

      expect(result.success).toBe(true)
      expect(result.output.content).toBe('text with whitespace')
    })

    it('fails with empty content', async () => {
      const result = await cell.execute({ action: 'capture', content: '' })
      expect(result.success).toBe(false)
      expect(result.error).toContain('No content to capture')
    })

    it('fails with whitespace-only content', async () => {
      const result = await cell.execute({ action: 'capture', content: '   ' })
      expect(result.success).toBe(false)
      expect(result.error).toContain('No content to capture')
    })
  })

  // ── execute() — wireframe ────────────────────────────────────────────────

  describe('execute() — wireframe', () => {
    it('generates wireframe from HTML', async () => {
      const result = await cell.execute({
        action: 'wireframe',
        content: '<div><h1>Title</h1><p>Paragraph</p></div>'
      })

      expect(result.success).toBe(true)
      expect(result.output.content).toBeTruthy()
      expect(result.output.content).toContain('div')
      expect(result.output.fileName).toMatch(/^wireframe-.*\.txt$/)
      expect(result.output.language).toBe('plaintext')
    })

    it('fails with empty HTML content', async () => {
      const result = await cell.execute({ action: 'wireframe', content: '' })
      expect(result.success).toBe(false)
      expect(result.error).toContain('No HTML content')
    })

    it('fails with whitespace-only HTML', async () => {
      const result = await cell.execute({ action: 'wireframe', content: '   ' })
      expect(result.success).toBe(false)
      expect(result.error).toContain('No HTML content')
    })
  })

  // ── execute() — unknown action ───────────────────────────────────────────

  describe('execute() — unknown action', () => {
    it('returns error mentioning supported actions', async () => {
      const result = await cell.execute({ action: 'invalid', content: 'test' })

      expect(result.success).toBe(false)
      expect(result.error).toContain('Unknown action')
      expect(result.error).toContain('capture')
      expect(result.error).toContain('wireframe')
    })
  })

  // ── validate() ───────────────────────────────────────────────────────────

  describe('validate()', () => {
    it('accepts valid capture input', () => {
      const errors = cell.validate({ action: 'capture', content: 'test' })
      expect(errors).toHaveLength(0)
    })

    it('accepts valid wireframe input', () => {
      const errors = cell.validate({ action: 'wireframe', content: '<html/>' })
      expect(errors).toHaveLength(0)
    })

    it('rejects missing action', () => {
      const errors = cell.validate({ content: 'test' })
      expect(errors.some(e => e.field === 'action')).toBe(true)
    })

    it('rejects invalid action', () => {
      const errors = cell.validate({ action: 'invalid-action', content: 'test' })
      expect(errors.some(e => e.field === 'action' && e.message.includes('capture'))).toBe(true)
    })

    it('rejects missing content', () => {
      const errors = cell.validate({ action: 'capture', content: '' })
      expect(errors.some(e => e.field === 'content')).toBe(true)
    })

    it('rejects whitespace-only content', () => {
      const errors = cell.validate({ action: 'capture', content: '   ' })
      expect(errors.some(e => e.field === 'content')).toBe(true)
    })

    it('rejects non-string action', () => {
      const errors = cell.validate({ action: 123 as any, content: 'test' })
      expect(errors.some(e => e.field === 'action')).toBe(true)
    })
  })

  // ── describe() ───────────────────────────────────────────────────────────

  describe('describe()', () => {
    it('returns correct metadata', async () => {
      const metadata = await cell.describe()
      expect(metadata.id).toBe('manual-capture-cell')
      expect(metadata.name).toBe('Manual Capture')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.tags).toContain('capture')
      expect(metadata.tags).toContain('utility')
      expect(metadata.required_resources).toHaveLength(0)
    })

    it('defines action and content inputs', async () => {
      const metadata = await cell.describe()
      expect(metadata.inputs.action).toBeDefined()
      expect(metadata.inputs.action.required).toBe(true)
      expect(metadata.inputs.action.enum).toContain('capture')
      expect(metadata.inputs.action.enum).toContain('wireframe')
      expect(metadata.inputs.content).toBeDefined()
      expect(metadata.inputs.content.required).toBe(true)
    })

    it('defines all output fields', async () => {
      const metadata = await cell.describe()
      expect(metadata.outputs.content).toBeDefined()
      expect(metadata.outputs.fileName).toBeDefined()
      expect(metadata.outputs.language).toBeDefined()
    })
  })

  // ── health_check() ───────────────────────────────────────────────────────

  describe('health_check()', () => {
    it('returns healthy status', async () => {
      const health = await cell.health_check()
      expect(health.status).toBe('healthy')
      expect(health.can_execute).toBe(true)
    })
  })

  // ── setup() / teardown() ─────────────────────────────────────────────────

  describe('setup() / teardown()', () => {
    it('setup resolves without error', async () => {
      await expect(cell.setup({
        has_gpu: false,
        gpu_vram_mb: 0,
        cpu_cores: 4,
        headless_mode: true,
        timeout_seconds: 30,
      })).resolves.toBeUndefined()
    })

    it('teardown resolves without error', async () => {
      await expect(cell.teardown()).resolves.toBeUndefined()
    })
  })
})
