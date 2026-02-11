/**
 * @file CalculatorCell.ts
 * @description CalculatorCell - Pure frontend BaseCell implementation (PoC)
 * 
 * This is a proof-of-concept implementation demonstrating the BaseCell interface
 * with a simple calculator that performs basic math operations entirely in JavaScript.
 * No backend dependency - perfect for testing headless execution.
 * 
 * Part of BaseCell v1.0 Framework Implementation
 * Epic: Phase 1 - Foundation
 * Task: [CALC-001] Implement CalculatorCell logic
 */

import { BaseCell, createHealthyResult } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError, EnvironmentConfig, HealthCheckResult } from '@/types/BaseCell'

/**
 * Supported calculator operations
 */
export type CalculatorOperation = 'add' | 'subtract' | 'multiply' | 'divide' | 'power' | 'modulo'

/**
 * Calculator input interface
 */
export interface CalculatorInput {
  /** First operand */
  a: number
  
  /** Second operand */
  b: number
  
  /** Operation to perform */
  operation: CalculatorOperation
  
  /** Optional precision for decimal results */
  precision?: number
}

/**
 * Calculator output interface
 */
export interface CalculatorOutput {
  /** Result of the operation */
  result: number
  
  /** Formatted result string */
  formatted: string
  
  /** Expression that was evaluated */
  expression: string
}

/**
 * CalculatorCell - Pure frontend BaseCell implementation
 * 
 * Demonstrates BaseCell interface with:
 * - Synchronous local execution (no backend)
 * - Input validation (divide by zero, invalid operations)
 * - Metadata introspection
 * - Health checking
 * - Sub-millisecond latency
 * 
 * Perfect for:
 * - Testing headless execution
 * - Demonstrating composability
 * - Benchmarking BaseCell overhead
 * 
 * @example
 * ```typescript
 * const calc = new CalculatorCell()
 * 
 * // Execute headless
 * const result = await calc.execute({
 *   a: 10,
 *   b: 5,
 *   operation: 'add'
 * })
 * // => { success: true, output: { result: 15, ... }, execution_time: 0.5 }
 * 
 * // Validate before execute
 * const errors = calc.validate({ a: 10, b: 0, operation: 'divide' })
 * // => [{ field: 'b', message: 'Cannot divide by zero' }]
 * ```
 */
export class CalculatorCell extends BaseCell {
  private _isSetup: boolean = false
  
  /**
   * Execute calculator operation
   * 
   * Pure JavaScript execution - no backend calls.
   * Completes in <1ms typically.
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
          error: 'Validation failed'
        }
      }
      
      const { a, b, operation, precision = 2 } = input as CalculatorInput
      
      // Perform operation
      let result: number
      let operatorSymbol: string
      
      switch (operation) {
        case 'add':
          result = a + b
          operatorSymbol = '+'
          break
        case 'subtract':
          result = a - b
          operatorSymbol = '-'
          break
        case 'multiply':
          result = a * b
          operatorSymbol = '×'
          break
        case 'divide':
          result = a / b
          operatorSymbol = '÷'
          break
        case 'power':
          result = Math.pow(a, b)
          operatorSymbol = '^'
          break
        case 'modulo':
          result = a % b
          operatorSymbol = '%'
          break
        default:
          throw new Error(`Unknown operation: ${operation}`)
      }
      
      // Format result
      const formatted = precision > 0
        ? result.toFixed(precision)
        : result.toString()
      
      const expression = `${a} ${operatorSymbol} ${b} = ${formatted}`
      
      const output: CalculatorOutput = {
        result,
        formatted,
        expression
      }
      
      const executionTime = performance.now() - startTime
      
      return {
        success: true,
        output,
        execution_time: executionTime,
        execution_steps: ['validate', 'calculate', 'format'],
        quality_score: 1.0,
        metadata: {
          operation,
          operands: [a, b],
          precision
        }
      }
    } catch (error: any) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message || 'Calculation failed'
      }
    }
  }
  
  /**
   * Describe calculator capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'calculator-cell',
      name: 'Calculator Cell',
      version: '1.0.0',
      description: 'Simple calculator for basic math operations. Pure frontend implementation with no backend dependencies.',
      inputs: {
        a: {
          type: 'number',
          description: 'First operand',
          required: true
        },
        b: {
          type: 'number',
          description: 'Second operand',
          required: true
        },
        operation: {
          type: 'string',
          description: 'Operation to perform',
          required: true,
          enum: ['add', 'subtract', 'multiply', 'divide', 'power', 'modulo']
        },
        precision: {
          type: 'number',
          description: 'Decimal precision for result (default: 2)',
          required: false,
          default: 2
        }
      },
      outputs: {
        result: {
          type: 'number',
          description: 'Calculated result'
        },
        formatted: {
          type: 'string',
          description: 'Formatted result string'
        },
        expression: {
          type: 'string',
          description: 'Complete expression (e.g., "10 + 5 = 15")'
        }
      },
      tags: ['math', 'calculator', 'frontend-only', 'headless-capable'],
      estimated_duration_seconds: 0.001, // <1ms
      required_resources: [] // No external dependencies
    }
  }
  
  /**
   * Validate calculator input
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    
    // Check required fields
    if (input.a === undefined || input.a === null) {
      errors.push({ field: 'a', message: 'First operand is required' })
    } else if (typeof input.a !== 'number' || isNaN(input.a)) {
      errors.push({ field: 'a', message: 'First operand must be a valid number' })
    }
    
    if (input.b === undefined || input.b === null) {
      errors.push({ field: 'b', message: 'Second operand is required' })
    } else if (typeof input.b !== 'number' || isNaN(input.b)) {
      errors.push({ field: 'b', message: 'Second operand must be a valid number' })
    }
    
    if (!input.operation) {
      errors.push({ field: 'operation', message: 'Operation is required' })
    } else {
      const validOperations: CalculatorOperation[] = ['add', 'subtract', 'multiply', 'divide', 'power', 'modulo']
      if (!validOperations.includes(input.operation as CalculatorOperation)) {
        errors.push({
          field: 'operation',
          message: `Operation must be one of: ${validOperations.join(', ')}`
        })
      }
    }
    
    // Check divide by zero
    if (input.operation === 'divide' && input.b === 0) {
      errors.push({ field: 'b', message: 'Cannot divide by zero' })
    }
    
    // Check modulo by zero
    if (input.operation === 'modulo' && input.b === 0) {
      errors.push({ field: 'b', message: 'Cannot calculate modulo by zero' })
    }
    
    // Validate precision if provided
    if (input.precision !== undefined) {
      if (typeof input.precision !== 'number' || input.precision < 0 || input.precision > 10) {
        errors.push({ field: 'precision', message: 'Precision must be a number between 0 and 10' })
      }
    }
    
    return errors
  }
  
  /**
   * Setup (optional) - Calculator needs no initialization
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    console.log('[CalculatorCell] Setup called (no-op for this cell)')
    this._isSetup = true
  }
  
  /**
   * Teardown (optional) - Calculator needs no cleanup
   */
  async teardown(): Promise<void> {
    console.log('[CalculatorCell] Teardown called (no-op for this cell)')
    this._isSetup = false
  }
  
  /**
   * Health check (optional) - Calculator is always healthy
   */
  async health_check(): Promise<HealthCheckResult> {
    return createHealthyResult()
  }
}
