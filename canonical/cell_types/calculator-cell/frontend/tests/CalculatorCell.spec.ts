/**
 * @file CalculatorCell.spec.ts
 * @description Unit tests for CalculatorCell — real import via BaseCell pattern
 *
 * CalculatorCell is a pure frontend cell (no backend dependencies).
 * No mocks needed — it only imports from @/types/BaseCell.
 *
 * Part of BaseCell v1.0 Framework Implementation
 * Ref: artifacts/docs/TESTING_ARTIFACTS.md
 */

import { describe, it, expect, beforeAll, beforeEach } from 'vitest'
import { CalculatorCell } from '../CalculatorCell'
import type { CalculatorInput } from '../CalculatorCell'

describe('CalculatorCell', () => {
  let cell: CalculatorCell

  beforeAll(() => {
    cell = new CalculatorCell()
  })

  beforeEach(() => {
    // No mocks to clear — pure frontend cell
  })

  // ── validate() ────────────────────────────────────────────────────────────

  describe('validate()', () => {
    it('returns no errors for valid add input', () => {
      const input: CalculatorInput = { a: 10, b: 5, operation: 'add' }
      const errors = cell.validate(input)
      expect(errors).toHaveLength(0)
    })

    it('returns no errors for valid divide input', () => {
      const input: CalculatorInput = { a: 22, b: 7, operation: 'divide' }
      const errors = cell.validate(input)
      expect(errors).toHaveLength(0)
    })

    it('rejects missing first operand', () => {
      const errors = cell.validate({ b: 5, operation: 'add' })
      expect(errors.some(e => e.field === 'a')).toBe(true)
    })

    it('rejects missing second operand', () => {
      const errors = cell.validate({ a: 10, operation: 'add' })
      expect(errors.some(e => e.field === 'b')).toBe(true)
    })

    it('rejects non-numeric first operand', () => {
      const errors = cell.validate({ a: 'abc', b: 5, operation: 'add' })
      expect(errors.some(e => e.field === 'a' && e.message.includes('number'))).toBe(true)
    })

    it('rejects NaN first operand', () => {
      const errors = cell.validate({ a: NaN, b: 5, operation: 'add' })
      expect(errors.some(e => e.field === 'a')).toBe(true)
    })

    it('rejects invalid operation', () => {
      const errors = cell.validate({ a: 10, b: 5, operation: 'sqrt' })
      expect(errors.some(e => e.field === 'operation')).toBe(true)
    })

    it('rejects divide by zero', () => {
      const errors = cell.validate({ a: 10, b: 0, operation: 'divide' })
      expect(errors.some(e => e.field === 'b' && e.message.includes('zero'))).toBe(true)
    })

    it('rejects modulo by zero', () => {
      const errors = cell.validate({ a: 10, b: 0, operation: 'modulo' })
      expect(errors.some(e => e.field === 'b' && e.message.includes('zero'))).toBe(true)
    })

    it('rejects precision below 0', () => {
      const errors = cell.validate({ a: 10, b: 5, operation: 'add', precision: -1 })
      expect(errors.some(e => e.field === 'precision')).toBe(true)
    })

    it('rejects precision above 10', () => {
      const errors = cell.validate({ a: 10, b: 5, operation: 'add', precision: 15 })
      expect(errors.some(e => e.field === 'precision')).toBe(true)
    })
  })

  // ── execute() ─────────────────────────────────────────────────────────────

  describe('execute()', () => {
    it('adds two numbers correctly', async () => {
      const result = await cell.execute({ a: 10, b: 5, operation: 'add', precision: 2 })
      expect(result.success).toBe(true)
      expect(result.output.result).toBe(15)
      expect(result.output.formatted).toBe('15.00')
      expect(result.output.expression).toBe('10 + 5 = 15.00')
    })

    it('subtracts two numbers correctly', async () => {
      const result = await cell.execute({ a: 20, b: 8, operation: 'subtract', precision: 1 })
      expect(result.success).toBe(true)
      expect(result.output.result).toBe(12)
      expect(result.output.formatted).toBe('12.0')
    })

    it('multiplies two numbers correctly', async () => {
      const result = await cell.execute({ a: 7, b: 6, operation: 'multiply', precision: 0 })
      expect(result.success).toBe(true)
      expect(result.output.result).toBe(42)
      expect(result.output.formatted).toBe('42')
    })

    it('divides two numbers correctly', async () => {
      const result = await cell.execute({ a: 22, b: 7, operation: 'divide', precision: 4 })
      expect(result.success).toBe(true)
      expect(result.output.result).toBeCloseTo(3.142857, 4)
      expect(result.output.formatted).toBe('3.1429')
    })

    it('calculates power correctly', async () => {
      const result = await cell.execute({ a: 2, b: 10, operation: 'power', precision: 0 })
      expect(result.success).toBe(true)
      expect(result.output.result).toBe(1024)
    })

    it('calculates modulo correctly', async () => {
      const result = await cell.execute({ a: 17, b: 5, operation: 'modulo', precision: 0 })
      expect(result.success).toBe(true)
      expect(result.output.result).toBe(2)
    })

    it('returns error for invalid input (missing fields)', async () => {
      const result = await cell.execute({ operation: 'add' })
      expect(result.success).toBe(false)
      expect(result.error).toBe('Validation failed')
    })

    it('returns error for unknown operation', async () => {
      const result = await cell.execute({ a: 10, b: 5, operation: 'unknown' })
      expect(result.success).toBe(false)
      expect(result.error).toBeDefined()
    })

    it('includes execution_steps on success', async () => {
      const result = await cell.execute({ a: 1, b: 2, operation: 'add' })
      expect(result.execution_steps).toEqual(['validate', 'calculate', 'format'])
    })

    it('includes quality_score on success', async () => {
      const result = await cell.execute({ a: 1, b: 2, operation: 'add' })
      expect(result.quality_score).toBe(1.0)
    })
  })

  // ── describe() ────────────────────────────────────────────────────────────

  describe('describe()', () => {
    it('returns correct cell metadata', async () => {
      const metadata = await cell.describe()
      expect(metadata.id).toBe('calculator-cell')
      expect(metadata.name).toBe('Calculator Cell')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.tags).toContain('math')
      expect(metadata.tags).toContain('headless-capable')
    })

    it('defines all required input fields', async () => {
      const metadata = await cell.describe()
      expect(metadata.inputs.a).toBeDefined()
      expect(metadata.inputs.a.required).toBe(true)
      expect(metadata.inputs.b).toBeDefined()
      expect(metadata.inputs.b.required).toBe(true)
      expect(metadata.inputs.operation).toBeDefined()
      expect(metadata.inputs.operation.enum).toContain('add')
    })

    it('defines all output fields', async () => {
      const metadata = await cell.describe()
      expect(metadata.outputs.result).toBeDefined()
      expect(metadata.outputs.formatted).toBeDefined()
      expect(metadata.outputs.expression).toBeDefined()
    })
  })

  // ── health_check() ────────────────────────────────────────────────────────

  describe('health_check()', () => {
    it('returns healthy status', async () => {
      const health = await cell.health_check()
      expect(health.status).toBe('healthy')
      expect(health.can_execute).toBe(true)
    })
  })

  // ── setup() / teardown() ──────────────────────────────────────────────────

  describe('setup() / teardown()', () => {
    it('completes setup without errors', async () => {
      await expect(cell.setup({
        has_gpu: false,
        gpu_vram_mb: 0,
        cpu_cores: 4,
        headless_mode: true,
        timeout_seconds: 30,
      })).resolves.not.toThrow()
    })

    it('completes teardown without errors', async () => {
      await expect(cell.teardown()).resolves.not.toThrow()
    })
  })

  // ── performance ───────────────────────────────────────────────────────────

  describe('performance', () => {
    it('executes add in under 5ms', async () => {
      const result = await cell.execute({ a: 100, b: 50, operation: 'multiply' })
      expect(result.execution_time).toBeLessThan(5)
    })

    it('handles 100 rapid executions', async () => {
      const promises = Array.from({ length: 100 }, (_, i) =>
        cell.execute({ a: i, b: 2, operation: 'add' })
      )
      const results = await Promise.all(promises)
      expect(results).toHaveLength(100)
      expect(results.every(r => r.success)).toBe(true)
    })
  })
})
