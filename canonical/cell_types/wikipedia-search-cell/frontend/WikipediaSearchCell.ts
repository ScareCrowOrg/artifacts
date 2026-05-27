import { BaseCell } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError } from '@/types/BaseCell'

interface WikipediaPage {
  pageid: number
  title: string
  snippet: string
}

interface WikipediaSearchResult {
  title: string
  pageId: number
  snippet: string
  url: string
}

export class WikipediaSearchCell extends BaseCell {
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()

    try {
      const query = String(input.query ?? '').trim()
      const language = String(input.language ?? 'en').trim() || 'en'
      const limit = Math.min(Math.max(Number(input.limit) || 10, 1), 50)

      const apiUrl =
        `https://${language}.wikipedia.org/w/api.php` +
        `?action=query` +
        `&list=search` +
        `&srsearch=${encodeURIComponent(query)}` +
        `&srlimit=${limit}` +
        `&format=json` +
        `&origin=*`

      const response = await fetch(apiUrl)
      if (!response.ok) {
        throw new Error(`Wikipedia API returned HTTP ${response.status}`)
      }
      const data = await response.json()

      const pages: WikipediaPage[] = data?.query?.search ?? []
      const results: WikipediaSearchResult[] = pages.map((item) => ({
        title: item.title,
        pageId: item.pageid,
        snippet: item.snippet
          .replace(/<span class="searchmatch">/g, '**')
          .replace(/<\/span>/g, '**'),
        url: `https://${language}.wikipedia.org/wiki/${encodeURIComponent(item.title.replace(/ /g, '_'))}`
      }))

      return {
        success: true,
        output: {
          results,
          totalResults: data?.query?.searchinfo?.totalHits ?? 0,
          searchTime: data?.query?.searchinfo?.totalhits ?? null
        },
        execution_time: performance.now() - startTime
      }
    } catch (error) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error instanceof Error ? error.message : 'Unknown error during Wikipedia search'
      }
    }
  }

  async describe(): Promise<CellMetadata> {
    return {
      id: 'wikipedia-search-cell',
      name: 'Wikipedia Search',
      version: '1.0.0',
      description: 'Search Wikipedia articles and browse results with direct links',
      inputs: {
        query: { type: 'string', description: 'Search query', required: true },
        language: {
          type: 'string',
          description: 'Wikipedia language code (e.g. en, pt, es, fr, de)',
          required: false
        },
        limit: { type: 'number', description: 'Max results (1-50)', required: false }
      },
      outputs: {
        results: { type: 'array', description: 'Search results with titles, snippets and URLs' },
        totalResults: { type: 'number', description: 'Total matching articles' }
      },
      tags: ['search', 'wikipedia', 'reference', 'utility']
    }
  }

  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    if (!input.query || typeof input.query !== 'string' || input.query.trim() === '') {
      errors.push({ field: 'query', message: 'Search query is required' })
    }

    if (input.limit !== undefined && input.limit !== null) {
      const limit = Number(input.limit)
      if (isNaN(limit) || limit < 1 || limit > 50) {
        errors.push({ field: 'limit', message: 'Limit must be between 1 and 50' })
      }
    }

    if (input.language !== undefined && input.language !== null) {
      if (typeof input.language !== 'string' || !/^[a-z]{2,3}$/.test(input.language.trim())) {
        errors.push({ field: 'language', message: 'Language must be a 2-3 letter code (e.g. en, pt)' })
      }
    }

    return errors
  }
}
