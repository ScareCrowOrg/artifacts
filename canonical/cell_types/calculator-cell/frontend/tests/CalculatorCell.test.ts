/**
 * @file CalculatorCell.test.ts
 * @description Unit tests for CalculatorCell
 * 
 * Tests the CalculatorCell BaseCell implementation
 * Part of BaseCell v1.0 Framework Implementation
 */

import { describe, it, expect, beforeAll } from 'vitest'
import { CalculatorCell } from '../CalculatorCell'
import type { CalculatorInput } from '../CalculatorCell'

describe('CalculatorCell', () => {
  let calculator: CalculatorCell

  beforeAll(() => {
    calculator = new CalculatorCell()
  })

  describe('execute', () => {
    it('should add two numbers correctly', async () => {
      const input: CalculatorInput = {
        a: 10,
        b: 5,
        operation: 'add',
        precision: 2
      }

      const result = await calculator.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.result).toBe(15)
      expect(result.output.formatted).toBe('15.00')
      expect(result.output.expression).toBe('10 + 5 = 15.00')
      expect(result.execution_time).toBeGreaterThan(0)
      expect(result.execution_time).toBeLessThan(5) // Should be <5ms
    })

    it('should subtract two numbers correctly', async () => {
      const input: CalculatorInput = {
        a: 20,
        b: 8,
        operation: 'subtract',
        precision: 1
      }

      const result = await calculator.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.result).toBe(12)
      expect(result.output.formatted).toBe('12.0')
    })

    it('should multiply two numbers correctly', async () => {
      const input: CalculatorInput = {
        a: 7,
        b: 6,
        operation: 'multiply',
        precision: 0
      }

      const result = await calculator.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.result).toBe(42)
      expect(result.output.formatted).toBe('42')
    })

    it('should divide two numbers correctly', async () => {
      const input: CalculatorInput = {
        a: 22,
        b: 7,
        operation: 'divide',
        precision: 4
      }

      const result = await calculator.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.result).toBeCloseTo(3.142857, 4)
      expect(result.output.formatted).toBe('3.1429')
    })

    it('should calculate power correctly', async () => {
      const input: CalculatorInput = {
        a: 2,
        b: 10,
        operation: 'power',
        precision: 0
      }

      const result = await calculator.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.result).toBe(1024)
    })

    it('should calculate modulo correctly', async () => {
      const input: CalculatorInput = {
        a: 17,
        b: 5,
        operation: 'modulo',
        precision: 0
      }

      const result = await calculator.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.result).toBe(2)
    })

    it('should return error for invalid input', async () => {
      const input = {
        a: 10,
        // b is missing
        operation: 'add'
      }

      const result = await calculator.execute(input)

      expect(result.success).toBe(false)
      expect(result.error).toBe('Validation failed')
      expect(result.output.errors).toBeDefined()
    })
  })

  describe('validate', () => {
    it('should validate correct input', () => {
      const input: CalculatorInput = {
        a: 10,
        b: 5,
        operation: 'add'
      }

      const errors = calculator.validate(input)

      expect(errors).toHaveLength(0)
    })

    it('should reject missing operands', () => {
      const input = {
        operation: 'add'
      }

      const errors = calculator.validate(input)

      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.field === 'a')).toBe(true)
      expect(errors.some(e => e.field === 'b')).toBe(true)
    })

    it('should reject invalid operation', () => {
      const input = {
        a: 10,
        b: 5,
        operation: 'invalid'
      }

      const errors = calculator.validate(input)

      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.field === 'operation')).toBe(true)
    })

    it('should reject divide by zero', () => {
      const input: CalculatorInput = {
        a: 10,
        b: 0,
        operation: 'divide'
      }

      const errors = calculator.validate(input)

      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.field === 'b' && e.message.includes('zero'))).toBe(true)
    })

    it('should reject modulo by zero', () => {
      const input: CalculatorInput = {
        a: 10,
        b: 0,
        operation: 'modulo'
      }

      const errors = calculator.validate(input)

      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.field === 'b' && e.message.includes('zero'))).toBe(true)
    })

    it('should reject invalid precision', () => {
      const input = {
        a: 10,
        b: 5,
        operation: 'add',
        precision: 15 // Too high
      }

      const errors = calculator.validate(input)

      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.field === 'precision')).toBe(true)
    })
  })

  describe('describe', () => {
    it('should return correct metadata', async () => {
      const metadata = await calculator.describe()

      expect(metadata.id).toBe('calculator-cell')
      expect(metadata.name).toBe('Calculator Cell')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.tags).toContain('math')
      expect(metadata.tags).toContain('headless-capable')
      expect(metadata.required_resources).toHaveLength(0)
      expect(metadata.estimated_duration_seconds).toBeLessThan(0.01)
    })

    it('should define all input fields', async () => {
      const metadata = await calculator.describe()

      expect(metadata.inputs.a).toBeDefined()
      expect(metadata.inputs.b).toBeDefined()
      expect(metadata.inputs.operation).toBeDefined()
      expect(metadata.inputs.precision).toBeDefined()
    })

    it('should define all output fields', async () => {
      const metadata = await calculator.describe()

      expect(metadata.outputs.result).toBeDefined()
      expect(metadata.outputs.formatted).toBeDefined()
      expect(metadata.outputs.expression).toBeDefined()
    })
  })

  describe('lifecycle methods', () => {
    it('should setup without errors', async () => {
      await expect(calculator.setup({
        has_gpu: false,
        gpu_vram_mb: 0,
        cpu_cores: 4,
        headless_mode: true,
        timeout_seconds: 30
      })).resolves.not.toThrow()
    })

    it('should teardown without errors', async () => {
      await expect(calculator.teardown()).resolves.not.toThrow()
    })

    it('should return healthy status', async () => {
      const health = await calculator.health_check()

      expect(health.status).toBe('healthy')
      expect(health.can_execute).toBe(true)
    })
  })

  describe('performance', () => {
    it('should execute in under 5ms', async () => {
      const input: CalculatorInput = {
        a: 100,
        b: 50,
        operation: 'multiply'
      }

      const result = await calculator.execute(input)

      expect(result.execution_time).toBeLessThan(5)
    })

    it('should handle multiple rapid executions', async () => {
      const promises = Array.from({ length: 100 }, (_, i) => 
        calculator.execute({
          a: i,
          b: 2,
          operation: 'add'
        })
      )

      const results = await Promise.all(promises)

      expect(results).toHaveLength(100)
      expect(results.every(r => r.success)).toBe(true)
    })
  })
})
