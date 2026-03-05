/**
 * composables/useCellViewProvider.ts
 *
 * Cell type discovery, instantiation, and view resolution for DynamicWorkspace v2.
 *
 * Responsibilities:
 * 1. getCellTypes()          — Load available cell types from HybridDatabase (canonical JSONs)
 * 2. instantiateCellByType() — Dynamic import the BaseCell class and instantiate it
 * 3. resolveViewSpec()       — Call cellInstance.show() and return {component, props}
 *
 * Phase 2 — BaseCell-first architecture:
 * - cellInstance.show() is THE source of truth for what to render
 * - NO fallbacks or cascading conditionals in parent
 * - Always uses cellTypeName (semantic name), never UUID
 *
 * Import strategy:
 * - Static imports use @/ aliases (resolved by Vite to artifacts/shared/)
 * - Dynamic cell loading uses browser URL: await import('/canonical/cell_types/...')
 */

import { defineAsyncComponent, markRaw, shallowRef, ref } from 'vue'
import type { Component } from 'vue'
import type { CellTypeDefinition, ViewSpec } from '../types'
import { createLogger } from '@/utils/logger'
import GeneratedFormView from '../components/GeneratedFormView.vue'

const log = createLogger('workspace:cell-view-provider')

// ── Constants ─────────────────────────────────────────────────────────────────

const SCARERUNNER_URL =
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_SCARERUNNER_URL) ||
  'http://localhost:5050'

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Fetch a JSON file from the ScareRunner backend (/local/ mount of artifacts).
 */
async function fetchJson(path: string): Promise<any> {
  const url = `${SCARERUNNER_URL}${path}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${url}`)
  const text = await res.text()
  if (text.trim().startsWith('<')) throw new Error(`Received HTML for ${url}`)
  return JSON.parse(text)
}

// ── Composable ────────────────────────────────────────────────────────────────

export function useCellViewProvider() {

  // ── getCellTypes ───────────────────────────────────────────────────────────

  /**
   * Load available cell types from HybridDatabase.
   *
   * Strategy:
   * 1. Try GET /api/cells/types/list (backend API — returns full list)
   * 2. Fall back to loading individual type.json files for known cell types
   *
   * Returns only types with can_render_dynamically === true.
   */
  async function getCellTypes(): Promise<CellTypeDefinition[]> {
    log.debug('[useCellViewProvider] getCellTypes: loading from HybridDatabase')

    // 1. Try backend API
    try {
      const res = await fetch(`${SCARERUNNER_URL}/api/cells/types/list`)
      if (res.ok) {
        const data = await res.json()
        const types: CellTypeDefinition[] = Array.isArray(data) ? data : (data.types ?? [])
        const renderableTypes = types.filter(t => t.can_render_dynamically !== false)
        log.info('[useCellViewProvider] getCellTypes: loaded from API', { count: renderableTypes.length })
        return renderableTypes
      }
    } catch (err) {
      log.warn('[useCellViewProvider] getCellTypes: API unavailable, using fallback', err)
    }

    // 2. Fallback: load type.json for known canonical cell types
    const knownCellTypes = [
      'calculator-cell',
      '3d-mesh-prototyping-cell',
      'content-manager-cell',
      'file-manager-cell',
      'fragment-editor-cell',
      'issues-dashboard-cell',
      'chat-ia',
      'log-toggle-cell',
      'manual-capture-cell',
      'roles-management-cell',
    ]

    const results: CellTypeDefinition[] = []
    await Promise.allSettled(
      knownCellTypes.map(async name => {
        try {
          const typeJson = await fetchJson(`/local/canonical/cell_types/${name}/type.json`)
          if (typeJson && typeJson.can_render_dynamically !== false) {
            results.push(typeJson as CellTypeDefinition)
          }
        } catch (err) {
          log.debug(`[useCellViewProvider] getCellTypes: could not load ${name}`, err)
        }
      }),
    )

    log.info('[useCellViewProvider] getCellTypes: loaded from canonical JSONs', { count: results.length })
    return results
  }

  // ── instantiateCellByType ─────────────────────────────────────────────────

  /**
   * Dynamically import the BaseCell class for the given cell type and instantiate it.
   *
   * Requires the cell type's type.json to have default_refs.basecell[0] set.
   * Import uses browser URL: /canonical/cell_types/{name}/{basecellPath}
   *
   * @param cellTypeName  Semantic type name (e.g. "calculator-cell") — never UUID
   * @param cellType      Type definition (from getCellTypes or provided externally)
   * @returns             Instantiated BaseCell subclass
   */
  async function instantiateCellByType(
    cellTypeName: string,
    cellType: CellTypeDefinition,
  ): Promise<any> {
    const basecellPath = cellType.default_refs?.basecell?.[0]
    if (!basecellPath) {
      throw new Error(`[useCellViewProvider] Cell type "${cellTypeName}" has no basecell ref in type.json`)
    }

    // Dynamic import via browser URL (Vite resolves to canonical directory)
    const importUrl = `/canonical/cell_types/${cellTypeName}/${basecellPath}`
    log.debug('[useCellViewProvider] instantiateCellByType: dynamic import', { importUrl })

    const module = await import(/* @vite-ignore */ importUrl)
    const CellClass = module.default
    if (!CellClass) {
      throw new Error(`[useCellViewProvider] No default export in ${importUrl}`)
    }

    const instance = new CellClass()

    // Set semantic name so BaseCell.show() uses the correct folder for type.json loading
    ;(instance as any).__cellTypeName = cellTypeName

    log.info('[useCellViewProvider] instantiateCellByType: cell instantiated', {
      cellTypeName,
      className: CellClass.name,
    })
    return instance
  }

  // ── resolveViewSpec ───────────────────────────────────────────────────────

  /**
   * Determine what to render for a cell by calling cellInstance.show().
   *
   * show() is THE source of truth (Requirement 2 — ONE orchestration path).
   * Parent is agnostic — it receives only {component, props}.
   *
   * show() may return:
   * - { cellTypeName, componentPath, cellInstance } → custom View.vue exists
   * - undefined/void → no custom view; use GeneratedFormView
   *
   * @param cellInstance  Instantiated BaseCell
   * @param cellTypeName  Semantic type name
   * @param cellType      Full type definition (for schema fallback)
   * @returns             ViewSpec — always { component, props } — never undefined
   */
  async function resolveViewSpec(
    cellInstance: any,
    cellTypeName: string,
    cellType: CellTypeDefinition,
  ): Promise<ViewSpec> {
    log.debug('[useCellViewProvider] resolveViewSpec: calling show()', { cellTypeName })

    let showResult: any

    try {
      showResult = await cellInstance.show({}, { mode: 'dynamicworkspace' })
    } catch (err) {
      // show() failed (e.g. backend unreachable). Fall back to type.json direct check.
      log.warn('[useCellViewProvider] resolveViewSpec: show() threw, using type.json fallback', err)
      showResult = undefined
    }

    // Case 1: show() returned a custom view path
    if (showResult && showResult.componentPath) {
      const viewPath = showResult.componentPath
      const importUrl = `/canonical/cell_types/${cellTypeName}/${viewPath}`
      log.debug('[useCellViewProvider] resolveViewSpec: loading custom View.vue', { importUrl })

      const ViewComponent = defineAsyncComponent(() =>
        import(/* @vite-ignore */ importUrl),
      )

      return {
        component: markRaw(ViewComponent),
        props: {
          cellInstance,
          cell: { cellTypeName, cellType },
        },
      }
    }

    // Case 2: show() returned undefined (no custom view) or failed
    // Check type.json directly as a reliable fallback within the viewer context
    const viewRef = cellType.default_refs?.view?.[0]
    if (viewRef) {
      const importUrl = `/canonical/cell_types/${cellTypeName}/${viewRef}`
      log.debug('[useCellViewProvider] resolveViewSpec: loading View.vue from type.json ref', {
        importUrl,
      })

      const ViewComponent = defineAsyncComponent(() =>
        import(/* @vite-ignore */ importUrl),
      )

      return {
        component: markRaw(ViewComponent),
        props: {
          cellInstance,
          cell: { cellTypeName, cellType },
        },
      }
    }

    // Case 3: Truly no custom view — use GeneratedFormView
    log.info('[useCellViewProvider] resolveViewSpec: using GeneratedFormView', { cellTypeName })
    const schema = cellType.properties_schema || {}

    return {
      component: markRaw(GeneratedFormView),
      props: {
        cellInstance,
        schema,
        cellTypeName,
      },
    }
  }

  // ── Return ────────────────────────────────────────────────────────────────

  return {
    getCellTypes,
    instantiateCellByType,
    resolveViewSpec,
  }
}
