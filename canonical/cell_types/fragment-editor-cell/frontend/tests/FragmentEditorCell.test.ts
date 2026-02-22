/**
 * @file FragmentEditorCell.test.ts
 * @description Unit tests for FragmentEditorCell
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { FragmentEditorCell } from '../FragmentEditorCell'
import type { FragmentEditorInput } from '../FragmentEditorCell'

// Mock apiFetch
vi.mock('@/services/apiService', () => ({
  apiFetch: vi.fn()
}))

import { apiFetch } from '@/services/apiService'
const mockApiFetch = apiFetch as any

describe('FragmentEditorCell', () => {
  let cell: FragmentEditorCell
  
  beforeEach(() => {
    cell = new FragmentEditorCell()
    vi.clearAllMocks()
  })
  
  describe('describe()', () => {
    it('should return cell metadata', async () => {
      const metadata = await cell.describe()
      
      expect(metadata.id).toBe('fragment-editor-cell')
      expect(metadata.name).toBe('Fragment Editor')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.description).toContain('fragments')
      expect(metadata.tags).toContain('editor')
      expect(metadata.inputs).toHaveProperty('action')
      expect(metadata.inputs).toHaveProperty('cellId')
      expect(metadata.inputs).toHaveProperty('fragmentId')
      expect(metadata.inputs).toHaveProperty('content')
      expect(metadata.outputs).toHaveProperty('fragmentId')
      expect(metadata.outputs).toHaveProperty('content')
    })
  })
  
  describe('validate()', () => {
    it('should validate create action', () => {
      const validInput: FragmentEditorInput = {
        action: 'create',
        cellId: 'cell-123',
        content: 'Test content'
      }
      
      const errors = cell.validate(validInput)
      expect(errors).toHaveLength(0)
    })
    
    it('should require action', () => {
      const errors = cell.validate({})
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('action')
      expect(errors[0].message).toContain('required')
    })
    
    it('should validate action values', () => {
      const errors = cell.validate({ action: 'invalid' })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toBe('action')
      expect(errors[0].message).toContain('create, edit, load')
    })
    
    it('should require cellId for create action', () => {
      const errors = cell.validate({
        action: 'create',
        content: 'Test'
      })
      
      expect(errors.some(e => e.field === 'cellId')).toBe(true)
    })
    
    it('should require content for create action', () => {
      const errors = cell.validate({
        action: 'create',
        cellId: 'cell-123'
      })
      
      expect(errors.some(e => e.field === 'content')).toBe(true)
    })
    
    it('should require cellId, fragmentId, and content for edit action', () => {
      const errors = cell.validate({
        action: 'edit'
      })
      
      expect(errors.some(e => e.field === 'cellId')).toBe(true)
      expect(errors.some(e => e.field === 'fragmentId')).toBe(true)
      expect(errors.some(e => e.field === 'content')).toBe(true)
    })
    
    it('should require fragmentId for load action', () => {
      const errors = cell.validate({
        action: 'load'
      })
      
      expect(errors.some(e => e.field === 'fragmentId')).toBe(true)
    })
  })
  
  describe('execute() - create action', () => {
    it('should create a new fragment', async () => {
      const mockCellData = {
        id: 'cell-123',
        fragments: []
      }
      
      mockApiFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockCellData
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })
      
      const result = await cell.execute({
        action: 'create',
        cellId: 'cell-123',
        content: 'Test fragment content'
      })
      
      expect(result.success).toBe(true)
      expect(result.output?.cellId).toBe('cell-123')
      expect(result.output?.content).toBe('Test fragment content')
      expect(result.output?.message).toContain('created')
      expect(mockApiFetch).toHaveBeenCalledTimes(2)
    })
    
    it('should handle create errors', async () => {
      mockApiFetch.mockResolvedValueOnce({
        ok: false
      })
      
      const result = await cell.execute({
        action: 'create',
        cellId: 'cell-123',
        content: 'Test'
      })
      
      expect(result.success).toBe(false)
      expect(result.error).toBeTruthy()
    })
  })
  
  describe('execute() - edit action', () => {
    it('should edit an existing fragment', async () => {
      const mockCellData = {
        id: 'cell-123',
        fragments: [
          { tipo: 'memoria', conteudo: 'Old content' }
        ]
      }
      
      mockApiFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockCellData
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })
      
      const result = await cell.execute({
        action: 'edit',
        cellId: 'cell-123',
        fragmentId: '0',
        content: 'Updated content'
      })
      
      expect(result.success).toBe(true)
      expect(result.output?.content).toBe('Updated content')
      expect(result.output?.message).toContain('updated')
    })
    
    it('should handle invalid fragment ID', async () => {
      const mockCellData = {
        id: 'cell-123',
        fragments: [{ tipo: 'memoria', conteudo: 'Content' }]
      }
      
      mockApiFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockCellData
      })
      
      const result = await cell.execute({
        action: 'edit',
        cellId: 'cell-123',
        fragmentId: '999',
        content: 'Updated'
      })
      
      expect(result.success).toBe(false)
      expect(result.error).toContain('Invalid fragment ID')
    })
  })
  
  describe('execute() - load action', () => {
    it('should load a fragment by ID', async () => {
      const mockCellData = {
        id: 'cell-123',
        fragments: [
          { tipo: 'memoria', conteudo: 'Fragment content' }
        ]
      }
      
      mockApiFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockCellData
      })
      
      const result = await cell.execute({
        action: 'load',
        fragmentId: 'cell-123:0'
      })
      
      expect(result.success).toBe(true)
      expect(result.output?.content).toBe('Fragment content')
      expect(result.output?.cellId).toBe('cell-123')
    })
    
    it('should handle invalid fragment ID format', async () => {
      const result = await cell.execute({
        action: 'load',
        fragmentId: 'invalid-format'
      })
      
      expect(result.success).toBe(false)
      expect(result.error).toContain('Invalid fragment ID format')
    })
    
    it('should handle fragment not found', async () => {
      const mockCellData = {
        id: 'cell-123',
        fragments: []
      }
      
      mockApiFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockCellData
      })
      
      const result = await cell.execute({
        action: 'load',
        fragmentId: 'cell-123:0'
      })
      
      expect(result.success).toBe(false)
      expect(result.error).toContain('Fragment not found')
    })
  })
  
  describe('execute() - validation', () => {
    it('should fail on validation errors', async () => {
      const result = await cell.execute({
        action: 'create'
        // Missing cellId and content
      })
      
      expect(result.success).toBe(false)
      expect(result.error).toContain('Validation failed')
      expect(result.output?.errors).toBeDefined()
    })
  })
  
  describe('execute() - unknown action', () => {
    it('should handle unknown action via validation', async () => {
      const result = await cell.execute({
        action: 'unknown'
      })
      
      expect(result.success).toBe(false)
      expect(result.error).toContain('Validation failed')
      expect(result.error).toContain('create, edit, load')
    })
  })
})
