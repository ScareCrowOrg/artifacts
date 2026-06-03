import { describe, it, expect, vi, beforeEach } from 'vitest'
import { WikipediaSearchCell } from '../WikipediaSearchCell'

describe('WikipediaSearchCell', () => {
  let cell: WikipediaSearchCell

  beforeEach(() => {
    cell = new WikipediaSearchCell()
    global.fetch = vi.fn()
  })

  describe('validate', () => {
    it('returns no errors for valid input', () => {
      const errors = cell.validate({ query: 'Artificial Intelligence', language: 'en', limit: 10 })
      expect(errors).toHaveLength(0)
    })

    it('returns error when query is empty', () => {
      const errors = cell.validate({ query: '' })
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('query')
    })

    it('returns error when query is missing', () => {
      const errors = cell.validate({})
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('query')
    })

    it('returns error for limit below minimum', () => {
      const errors = cell.validate({ query: 'test', limit: 0 })
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('limit')
    })

    it('returns error for limit above maximum', () => {
      const errors = cell.validate({ query: 'test', limit: 51 })
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('limit')
    })

    it('returns error for invalid language code', () => {
      const errors = cell.validate({ query: 'test', language: 'english' })
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('language')
    })

    it('accepts valid language codes', () => {
      const errors = cell.validate({ query: 'test', language: 'pt' })
      expect(errors).toHaveLength(0)
    })
  })

  describe('describe', () => {
    it('returns valid metadata', async () => {
      const metadata = await cell.describe()
      expect(metadata.id).toBe('wikipedia-search-cell')
      expect(metadata.name).toBe('Wikipedia Search')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.inputs).toHaveProperty('query')
      expect(metadata.inputs).toHaveProperty('language')
      expect(metadata.inputs).toHaveProperty('limit')
      expect(metadata.outputs).toHaveProperty('results')
      expect(metadata.outputs).toHaveProperty('totalResults')
    })
  })

  describe('execute', () => {
    it('returns successful search results', async () => {
      const mockResponse = {
        query: {
          searchinfo: { totalHits: 100 },
          search: [
            { pageid: 1, title: 'AI', snippet: '<span class="searchmatch">AI</span> is...' },
            { pageid: 2, title: 'Machine Learning', snippet: '<span class="searchmatch">ML</span> is...' }
          ]
        }
      }
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const result = await cell.execute({ query: 'artificial intelligence', language: 'en', limit: 10 })

      expect(result.success).toBe(true)
      expect(result.output.results).toHaveLength(2)
      expect(result.output.results[0].title).toBe('AI')
      expect(result.output.results[0].pageId).toBe(1)
      expect(result.output.results[0].url).toContain('wikipedia.org/wiki/')
      expect(result.output.totalResults).toBe(100)
      expect(result.execution_time).toBeGreaterThanOrEqual(0)
    })

    it('handles empty search results', async () => {
      const mockResponse = { query: { searchinfo: { totalhits: 0 }, search: [] } }
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const result = await cell.execute({ query: 'nonexistentxyz123', language: 'en' })

      expect(result.success).toBe(true)
      expect(result.output.results).toHaveLength(0)
      expect(result.output.totalResults).toBe(0)
    })

    it('handles HTTP errors', async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 429
      })

      const result = await cell.execute({ query: 'test', language: 'en' })

      expect(result.success).toBe(false)
      expect(result.error).toContain('429')
    })

    it('handles network errors', async () => {
      ;(global.fetch as any).mockRejectedValueOnce(new Error('Network failure'))

      const result = await cell.execute({ query: 'test', language: 'en' })

      expect(result.success).toBe(false)
      expect(result.error).toBe('Network failure')
    })
  })
})
