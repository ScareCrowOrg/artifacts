/**
 * Cell Types Service
 *
 * Service for fetching and managing cell types (NotebookItemType).
 */

import { ENDPOINTS } from '../config/endpoints.js'
import apiService from './apiService.js'

class CellTypesService {
  constructor() {
    this.cellTypes = null
    this.cellTypesMap = new Map()
    this.loading = false
  }

  /**
   * Transform NotebookItemType by flattening default_initial_data properties
   * to the top level for easier access in the UI.
   * 
   * Properties like views_components, icon, category are stored in
   * default_initial_data in the backend but expected at the top level
   * by frontend components.
   * 
   * @param {Object|null} type - Raw NotebookItemType from backend with structure:
   *   {id: string, name: string, default_initial_data: {views_components: Array, icon: string, category: string, ...}}
   * @returns {Object|null} Transformed type with flattened properties at top level,
   *   or null if input is null. Properties from default_initial_data are promoted
   *   to top level without overriding existing top-level values.
   */
  _transformCellType(type) {
    if (!type) return null

    // Create a shallow copy to avoid mutating the original
    const transformed = { ...type }

    // Flatten commonly accessed properties from default_initial_data
    if (type.default_initial_data) {
      const { views_components, icon, category, properties, versao } =
        type.default_initial_data

      // Only set if they don't already exist at top level
      if (views_components !== undefined && !transformed.views_components) {
        transformed.views_components = views_components
      }
      if (icon !== undefined && !transformed.icon) {
        transformed.icon = icon
      }
      if (category !== undefined && !transformed.category) {
        transformed.category = category
      }
      if (properties !== undefined && !transformed.properties) {
        transformed.properties = properties
      }
      if (versao !== undefined && !transformed.versao) {
        transformed.versao = versao
      }
    }

    return transformed
  }

  /**
   * Fetch all cell types from backend
   * @returns {Promise<Array>} Array of NotebookItemType objects
   */
  async fetchCellTypes() {
    if (this.loading) {
      // Wait for ongoing fetch to complete
      while (this.loading) {
        await new Promise((resolve) => setTimeout(resolve, 100))
      }
      return this.cellTypes
    }

    this.loading = true

    try {
      const response = await apiService.fetch(ENDPOINTS.listCellTypes)

      if (!response.ok) {
        throw new Error('Falha ao carregar tipos de célula')
      }

      const rawTypes = await response.json()

      // Transform types to flatten default_initial_data properties
      this.cellTypes = rawTypes.map((type) => this._transformCellType(type))

      // Build map for quick lookup
      this.cellTypesMap.clear()
      this.cellTypes.forEach((type) => {
        this.cellTypesMap.set(type.id, type)
      })

      return this.cellTypes
    } catch (error) {
      console.error('Erro ao buscar tipos de célula:', error)
      throw error
    } finally {
      this.loading = false
    }
  }

  /**
   * Get a specific cell type by ID
   * @param {string} cellTypeId - ID of the cell type
   * @returns {Promise<Object>} NotebookItemType object
   */
  async getCellType(cellTypeId) {
    if (!this.cellTypes) {
      await this.fetchCellTypes()
    }

    return this.cellTypesMap.get(cellTypeId) || null
  }

  /**
   * Get cell type icon
   * @param {string} cellTypeId - ID of the cell type
   * @returns {Promise<string>} Icon name or default icon
   */
  async getCellTypeIcon(cellTypeId) {
    const cellType = await this.getCellType(cellTypeId)
    return cellType?.icon || 'mdi-file'
  }

  /**
   * Get cell type name
   * @param {string} cellTypeId - ID of the cell type
   * @returns {Promise<string>} Cell type name or default
   */
  async getCellTypeName(cellTypeId) {
    const cellType = await this.getCellType(cellTypeId)
    return cellType?.name || 'Célula'
  }

  /**
   * Get cell type category
   * @param {string} cellTypeId - ID of the cell type
   * @returns {Promise<string>} Category ('persistida' or 'efemera')
   */
  async getCellTypeCategory(cellTypeId) {
    const cellType = await this.getCellType(cellTypeId)
    return cellType?.category || 'persistida'
  }

  /**
   * Get view components for a cell type
   * @param {string} cellTypeId - ID of the cell type
   * @returns {Promise<Array>} Array of component names
   */
  async getCellTypeViewComponents(cellTypeId) {
    const cellType = await this.getCellType(cellTypeId)
    return cellType?.views_components || []
  }

  /**
   * Check if cell type is ephemeral
   * @param {string} cellTypeId - ID of the cell type
   * @returns {Promise<boolean>} True if ephemeral
   */
  async isEphemeral(cellTypeId) {
    const category = await this.getCellTypeCategory(cellTypeId)
    return category === 'efemera'
  }

  /**
   * Clear cached cell types
   */
  clearCache() {
    this.cellTypes = null
    this.cellTypesMap.clear()
  }
}

// Export singleton instance
export default new CellTypesService()
