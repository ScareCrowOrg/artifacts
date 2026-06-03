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
 * Import strategy (Edge-Centric):
 * - Static imports use @/ aliases (resolved by Vite to artifacts/shared/)
 * - Dynamic cell loading uses buildArtifactUrl():
 *   - With VITE_TUNNEL_FQDN: https://{FQDN}/artifacts/canonical/cell_types/{name}/{file}
 *   - Without (localhost):    /artifacts/canonical/cell_types/{name}/{file}
 * - Traefik routes /artifacts/canonical/cell_types/ → vite:5052 (priority 100)
 * - Vite's artifactsRewritePlugin strips /artifacts → /canonical/cell_types/{name}/{file}
 * - Backend is API-only; Vite is the sovereign artifact host
 */

import { defineAsyncComponent, markRaw, shallowRef, ref } from 'vue'
import type { Component } from 'vue'
import type { CellTypeDefinition, ViewSpec } from '../types'
import { createLogger } from '@/utils/logger'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { apiFetch } from '@/services/apiService'
import GeneratedFormView from '../components/GeneratedFormView.vue'

const log = createLogger('workspace:cell-view-provider')

// ── Constants ─────────────────────────────────────────────────────────────────

const TUNNEL_FQDN =
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_TUNNEL_FQDN) || ''

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Build an absolute (or origin-relative) URL for a cell artifact.
 *
 * Uses the stage from the cell type definition (canonical, sandbox, runtime)
 * to construct the correct artifact path. Falls back to "canonical" if no
 * stage is provided (backward compatibility).
 *
 * When VITE_TUNNEL_FQDN is set, returns an absolute HTTPS URL so that
 * dynamic imports work correctly in Cloudflare Tunnel environments where
 * same-origin is not guaranteed.
 *
 * URL structure: /artifacts/{stage}/cell_types/{cellTypeName}/{filePath}
 * - Traefik routes PathPrefix(`/artifacts/`) → vite:5052
 * - Vite's artifactsRewritePlugin strips `/artifacts` → `/{stage}/cell_types/...`
 * - Vite resolves to /app/artifacts/{stage}/cell_types/{cellTypeName}/{filePath}
 *
 * @param cellTypeName  Semantic cell-type name (e.g. "calculator-cell")
 * @param filePath      Relative file path within the cell-type directory
 * @param stage         Artifact stage (canonical, sandbox) — defaults to "canonical"
 * @returns             Absolute or root-relative URL string
 */
function buildArtifactUrl(cellTypeName: string, filePath: string, stage: string = 'canonical'): string {
  if (!cellTypeName || !filePath) {
    throw new Error(`[useCellViewProvider] Missing artifact path: cellTypeName="${cellTypeName ?? 'undefined'}", filePath="${filePath ?? 'undefined'}"`)
  }
  if (cellTypeName.includes('..') || filePath.includes('..')) {
    throw new Error(`[useCellViewProvider] Invalid artifact path: cellTypeName="${cellTypeName}", filePath="${filePath}"`)
  }
  const artifactPath = `/artifacts/${stage}/cell_types/${cellTypeName}/${filePath}`
  log.debug('[useCellViewProvider] buildArtifactUrl', { cellTypeName, filePath, stage, artifactPath, hasTunnelFqdn: !!TUNNEL_FQDN })
  return TUNNEL_FQDN ? `https://${TUNNEL_FQDN}${artifactPath}` : artifactPath
}

// ── Composable ────────────────────────────────────────────────────────────────

export function useCellViewProvider() {

  // ── getCellTypes ───────────────────────────────────────────────────────────

  /**
   * Load available cell types from backend API.
   *
   * Endpoint: GET /api/cells/types/list
   * Returns: List of all notebook item types (cell type definitions)
   * Returns only types with can_render_dynamically === true.
   */
  async function getCellTypes(): Promise<CellTypeDefinition[]> {
    const store = useWorkspaceStore()
    log.debug('[useCellViewProvider] getCellTypes: loading from backend API', {
      hasToken: !!store.sessionToken,
      tokenLength: store.sessionToken?.length,
      storeStatus: store.status,
    })

    try {
      const response = await apiFetch('/api/cells/types/list', {
        method: 'GET',
      })

      const data = await response.json()

      log.info('[useCellViewProvider] getCellTypes: raw response from API', {
        isArray: Array.isArray(data),
        hasTypesProperty: !!data?.types,
        rawDataKeys: Object.keys(data || {}),
        rawDataPreview: JSON.stringify(data).substring(0, 200) + '...',
      })

      const types: CellTypeDefinition[] = Array.isArray(data) ? data : (data.types ?? [])

      log.info('[useCellViewProvider] getCellTypes: types extracted', {
        totalCount: types.length,
        typesPreview: types.slice(0, 3).map((t: any) => ({
          name: t.name,
          can_render_dynamically: t.can_render_dynamically,
        })),
      })

      const renderableTypes = types.filter(t => t.can_render_dynamically !== false)

      log.info('[useCellViewProvider] getCellTypes: after filtering', {
        beforeFilter: types.length,
        afterFilter: renderableTypes.length,
        filteredOut: types.length - renderableTypes.length,
        filterDetails: types.map((t: any) => ({
          name: t.name,
          can_render_dynamically: t.can_render_dynamically,
          isIncluded: t.can_render_dynamically !== false,
        })),
      })

      log.info('[useCellViewProvider] getCellTypes: final result', { count: renderableTypes.length })
      return renderableTypes
    } catch (err) {
      log.error('[useCellViewProvider] getCellTypes: failed to load from API', err)
      throw err
    }
  }

  // ── instantiateCellByType ─────────────────────────────────────────────────

  /**
   * Dynamically import the BaseCell class for the given cell type and instantiate it.
   *
   * Requires the cell type's type.json to have default_refs.basecell[0] set.
   * Import uses buildArtifactUrl(): /artifacts/{stage}/cell_types/{name}/{basecellPath}
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

    log.info('[useCellViewProvider] instantiateCellByType: starting', {
      cellTypeName,
      hasBasecellPath: !!basecellPath,
      basecellPath,
      defaultRefs: cellType.default_refs,
    })

    if (!basecellPath) {
      throw new Error(`[useCellViewProvider] Cell type "${cellTypeName}" has no basecell ref in type.json`)
    }

    // Dynamic import via Edge-centric URL (Traefik → vite:5052 → /artifacts/canonical/cell_types/)
    // TODO: Remove typeof diagnostics below after this fix is validated in production
    log.debug('[useCellViewProvider] instantiateCellByType: pre-buildArtifactUrl', {
      cellTypeName,
      basecellPath,
      cellTypeNameType: typeof cellTypeName,
      basecellPathType: typeof basecellPath,
    })
    const importUrl = buildArtifactUrl(cellTypeName, basecellPath, cellType.stage || 'canonical')
    log.info('[useCellViewProvider] instantiateCellByType: dynamic import', { importUrl })

    try {
      const module = await import(/* @vite-ignore */ importUrl)

      // Try to get the cell class: prefer default export, fall back to named export (usually class name)
      let CellClass = module.default

      if (!CellClass) {
        // No default export, look for a named export that's a class/function
        const keys = Object.keys(module)
        const classExport = keys.find((k) => typeof (module as any)[k] === 'function')

        if (classExport) {
          CellClass = (module as any)[classExport]
          log.info('[useCellViewProvider] instantiateCellByType: using named export', {
            importUrl,
            namedExport: classExport,
          })
        }
      }

      if (!CellClass) {
        const keys = Object.keys(module)
        log.error('[useCellViewProvider] instantiateCellByType: no cell class found', {
          importUrl,
          moduleKeys: keys,
          exportTypes: keys.map((k) => `${k}: ${typeof (module as any)[k]}`),
        })
        throw new Error(`[useCellViewProvider] No default or named class export in ${importUrl}`)
      }

      const instance = new CellClass()

      // Set semantic name so BaseCell.show() uses the correct folder for type.json loading
      ;(instance as any).__cellTypeName = cellTypeName
      // Set stage so BaseCell.loadCellTypeFromDiscovery loads from correct path (sandbox vs canonical)
      ;(instance as any).__cellStage = cellType.stage || 'canonical'

      log.info('[useCellViewProvider] instantiateCellByType: cell instantiated', {
        cellTypeName,
        className: CellClass.name,
      })
      return instance
    } catch (err) {
      log.error('[useCellViewProvider] instantiateCellByType: import failed', {
        importUrl,
        error: err instanceof Error ? err.message : String(err),
      })
      throw err
    }
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
    initialData?: Record<string, any>,
    cellId?: string,
  ): Promise<ViewSpec> {
    log.debug('[useCellViewProvider] resolveViewSpec: calling show()', { cellTypeName })

    const data = initialData ?? {}

    let showResult: any

    try {
      showResult = await cellInstance.show(data, { mode: 'dynamicworkspace' })
      log.info('[useCellViewProvider] resolveViewSpec: show() returned', {
        hasResult: !!showResult,
        resultKeys: showResult ? Object.keys(showResult) : [],
        componentPath: showResult?.componentPath,
      })
    } catch (err) {
      // show() failed (e.g. backend unreachable). Fall back to type.json direct check.
      log.warn('[useCellViewProvider] resolveViewSpec: show() threw, using type.json fallback', {
        error: err instanceof Error ? err.message : String(err),
      })
      showResult = undefined
    }

    // Case 1: show() returned a custom view path
    if (showResult && showResult.componentPath) {
      const viewPath = showResult.componentPath
      const importUrl = buildArtifactUrl(cellTypeName, viewPath, cellType.stage || 'canonical')
      log.info('[useCellViewProvider] resolveViewSpec: loading custom View.vue from show()', {
        importUrl,
      })

      try {
        const ViewComponent = defineAsyncComponent(() => {
          log.debug('[useCellViewProvider] Dynamic import START', { importUrl })
          return import(/* @vite-ignore */ importUrl)
            .then(module => {
              log.debug('[useCellViewProvider] Dynamic import SUCCESS', { importUrl, moduleKeys: Object.keys(module) })
              return module
            })
            .catch(err => {
              log.error('[useCellViewProvider] Dynamic import FAILED', {
                importUrl,
                error: err instanceof Error ? err.message : String(err),
                stack: err instanceof Error ? err.stack : undefined
              })
              throw err
            })
        })

        log.info('[useCellViewProvider] resolveViewSpec: custom View component created', {
          importUrl,
        })

        return {
          component: markRaw(ViewComponent),
          props: {
            cellInstance,
            cell: { cellTypeName, cellType, cellId, initial_data: data },
          },
        }
      } catch (err) {
        log.error('[useCellViewProvider] resolveViewSpec: failed to import custom View', {
          importUrl,
          error: err instanceof Error ? err.message : String(err),
        })
        throw err
      }
    }

    // Case 2: show() returned undefined (no custom view) or failed
    // Check type.json directly as a reliable fallback within the viewer context
    const viewRef = cellType.default_refs?.view?.[0]

    log.info('[useCellViewProvider] resolveViewSpec: checking type.json for view ref', {
      hasViewRef: !!viewRef,
      viewRef,
      defaultRefs: cellType.default_refs,
    })

    if (viewRef) {
      const importUrl = buildArtifactUrl(cellTypeName, viewRef, cellType.stage || 'canonical')
      log.info('[useCellViewProvider] resolveViewSpec: loading View.vue from type.json ref', {
        importUrl,
        viewRef,
      })

      try {
        const ViewComponent = defineAsyncComponent(() => {
          log.debug('[useCellViewProvider] resolveViewSpec: async import starting', { importUrl })
          return import(/* @vite-ignore */ importUrl)
            .then((module) => {
              log.info('[useCellViewProvider] resolveViewSpec: async import completed', {
                importUrl,
                moduleKeys: Object.keys(module),
              })
              return module
            })
            .catch((err) => {
              log.error('[useCellViewProvider] resolveViewSpec: async import failed', {
                importUrl,
                error: err instanceof Error ? err.message : String(err),
                errorStack: err instanceof Error ? err.stack : undefined,
              })
              throw err
            })
        })

        log.info('[useCellViewProvider] resolveViewSpec: View component created', { importUrl })

        return {
          component: markRaw(ViewComponent),
          props: {
            cellInstance,
            cell: { cellTypeName, cellType, cellId, initial_data: data },
          },
        }
      } catch (err) {
        log.error('[useCellViewProvider] resolveViewSpec: failed to create View component', {
          importUrl,
          error: err instanceof Error ? err.message : String(err),
        })
        throw err
      }
    }

    // Case 3: Truly no custom view — use GeneratedFormView
    log.info('[useCellViewProvider] resolveViewSpec: no view ref found, using GeneratedFormView', {
      cellTypeName,
    })
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
