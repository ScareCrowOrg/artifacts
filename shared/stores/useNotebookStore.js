/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-28",
 *   "console_calls_found": 12,
 *   "console_calls_migrated": 12,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:notebook",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Notebook Store - Manages hierarchical organization of Books and Cells
 *
 * This store centralizes state and logic for the NotebookItem abstraction,
 * providing a hierarchical view of "Books of Intentions" (Livros) and "Mission Cells" (Células).
 *
 * @module stores/useNotebookStore
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiService from '../services/apiService.js'
import { ENDPOINTS } from '../config/endpoints.js'
import authService from '../services/authService.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('store:notebook')

const FREE_FLOATING_BOOK_ID = '__free_floating__'

export const useNotebookStore = defineStore('notebook', () => {
  // =====================
  // State
  // =====================

  const books = ref([]) // Array of Book objects
  const cells = ref({}) // Map of cell ID to Cell object
  const selectedBookId = ref(null)
  const selectedCellId = ref(null)
  const isLoading = ref(false)
  const error = ref(null)
  const expandedBooks = ref([FREE_FLOATING_BOOK_ID]) // Start with free floating expanded

  // =====================
  // Getters
  // =====================

  /**
   * Get cells belonging to a specific book, sorted by date (most recent first)
   */
  const getCellsForBook = computed(() => (bookId) => {
    let filteredCells

    if (bookId === FREE_FLOATING_BOOK_ID) {
      // Return cells without source_book_id
      filteredCells = Object.values(cells.value).filter(
        (cell) => !cell.source_book_id,
      )
    } else {
      // Return cells with matching source_book_id
      filteredCells = Object.values(cells.value).filter(
        (cell) => cell.source_book_id === bookId,
      )
    }

    // Sort by created_at, most recent first
    return filteredCells.sort((a, b) => {
      const dateA = new Date(a.created_at || 0)
      const dateB = new Date(b.created_at || 0)
      return dateB - dateA // Descending order (most recent first)
    })
  })

  /**
   * Get virtual "Free Floating Cells" book
   */
  const getFreeFloatingCellsBook = computed(() => {
    const freeFloatingCells = Object.values(cells.value).filter(
      (cell) => !cell.source_book_id,
    )

    return {
      id: FREE_FLOATING_BOOK_ID,
      name: '📝 Células Soltas',
      description: 'Células não organizadas em livros',
      isVirtual: true,
      cells: freeFloatingCells.map((c) => c.id),
      cellCount: freeFloatingCells.length,
    }
  })

  /**
   * Get books for display (including virtual free floating book)
   */
  const getBooksForDisplay = computed(() => {
    const freeFloatingBook = getFreeFloatingCellsBook.value
    const userBooks = books.value.filter(
      (book) => !book.is_canonical_system_book,
    )

    // Return free floating book first, then user books
    return [freeFloatingBook, ...userBooks]
  })

  /**
   * Get the unclassified master template book
   */
  const getUnclassifiedMasterBook = computed(() => {
    return books.value.find((book) => book.is_unclassified_master_template)
  })

  /**
   * Check if a book is expanded
   */
  const isBookExpanded = computed(() => (bookId) => {
    return expandedBooks.value.includes(bookId)
  })

  /**
   * Get selected cell object
   */
  const selectedCell = computed(() => {
    return selectedCellId.value ? cells.value[selectedCellId.value] : null
  })

  /**
   * Get selected book object
   */
  const selectedBook = computed(() => {
    if (selectedBookId.value === FREE_FLOATING_BOOK_ID) {
      return getFreeFloatingCellsBook.value
    }
    return books.value.find((book) => book.id === selectedBookId.value)
  })

  // =====================
  // Actions
  // =====================

  /**
   * Get current user ID
   */
  function getUserId() {
    const user = authService.getUser()
    if (user && user.id) {
      return user.id
    }

    // Fallback
    let userId = localStorage.getItem('scareverse_user_id')
    if (!userId) {
      userId = 'seed-user-001'
      localStorage.setItem('scareverse_user_id', userId)
    }
    return userId
  }

  /**
   * Fetch all notebook items (books and cells) for the current user
   */
  async function fetchNotebookItems() {
    isLoading.value = true
    error.value = null

    try {
      const userId = getUserId()

      // Fetch books
      const booksResponse = await apiService.fetch(
        `${ENDPOINTS.books}/list?assignee_id=${userId}`,
      )
      let totalCells = 0
      if (booksResponse.ok) {
        books.value = await booksResponse.json()
      }

      // Fetch cells
      // Convert cells array to map
      cells.value = {}
      const cellsResponse = await apiService.fetch(
        `${ENDPOINTS.cells}/list?assignee_id=${userId}`,
      )
      if (cellsResponse.ok) {
        const cellsArray = await cellsResponse.json()
        totalCells = cellsArray.length
        cellsArray.forEach((cell) => {
          cells.value[cell.id] = cell
        })
      }
      log.info(`Loaded ${books.value.length} books and ${totalCells} cells`)
    } catch (err) {
      log.error('Error fetching notebook items', err)
      error.value =
        'Não foi possível carregar os itens do notebook. Tente novamente.'
      books.value = []
      cells.value = {}
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Create a new book
   */
  async function createBook(name, description = '', purpose = '') {
    isLoading.value = true
    error.value = null

    try {
      const response = await apiService.fetch(`${ENDPOINTS.books}/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          description: description || `Livro de intenções: ${name}`,
          purpose: purpose || name,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to create book')
      }

      const newBook = await response.json()
      books.value.push(newBook)

      // Auto-select and expand the new book
      selectedBookId.value = newBook.id
      if (!expandedBooks.value.includes(newBook.id)) {
        expandedBooks.value.push(newBook.id)
      }

      log.info(`Book created: ${newBook.id}`)
      return newBook
    } catch (err) {
      log.error('Error creating book', err)
      error.value = 'Não foi possível criar o livro. Tente novamente.'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Create a new cell
   * @param {string|null} bookId - Book ID to associate with, or null for free floating
   * @param {Object} cellData - Partial cell data
   */
  async function createCell(bookId = null, cellData = {}) {
    isLoading.value = true
    error.value = null

    try {
      const userId = getUserId()

      // Find unclassified cell type
      const cellTypesResponse = await apiService.fetch(
        `${ENDPOINTS.listCellTypes}`,
      )
      if (!cellTypesResponse.ok) {
        throw new Error('Failed to fetch cell types')
      }
      const cellTypes = await cellTypesResponse.json()
      log.debug('Cell types response', cellTypes)
      const unclassifiedType = cellTypes.find(
        (type) => type.id === 'unclassified',
      )

      if (!unclassifiedType) {
        throw new Error('Unclassified cell type not found')
      }

      // Prepare cell creation request
      const requestBody = {
        assignee_id: userId,
        notebook_item_type_id: unclassifiedType.id,
        source_book_id:
          bookId && bookId !== FREE_FLOATING_BOOK_ID ? bookId : null,
        initial_data: cellData.data || {},
      }

      const response = await apiService.fetch(`${ENDPOINTS.cells}/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      })

      if (!response.ok) {
        throw new Error('Failed to create cell')
      }

      const newCell = await response.json()
      cells.value[newCell.id] = newCell

      // Auto-select the new cell
      selectedCellId.value = newCell.id

      // If cell belongs to a book, expand that book
      const sourceBookId = newCell.source_book_id
      if (sourceBookId && !expandedBooks.value.includes(sourceBookId)) {
        expandedBooks.value.push(sourceBookId)
      } else if (
        !sourceBookId &&
        !expandedBooks.value.includes(FREE_FLOATING_BOOK_ID)
      ) {
        expandedBooks.value.push(FREE_FLOATING_BOOK_ID)
      }

      log.info(`Cell created: ${newCell.id}`)
      return newCell
    } catch (err) {
      log.error('Error creating cell', err)
      error.value = 'Não foi possível criar a célula. Tente novamente.'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Delete a cell
   */
  async function deleteCell(cellId) {
    isLoading.value = true
    error.value = null

    try {
      const response = await apiService.fetch(
        `${ENDPOINTS.cells}/${cellId}`,
        {
          method: 'DELETE',
        },
      )

      if (!response.ok) {
        throw new Error('Failed to delete cell')
      }

      // Remove from local state
      delete cells.value[cellId]

      // Clear selection if deleted cell was selected
      if (selectedCellId.value === cellId) {
        selectedCellId.value = null
      }

      log.info(`Cell deleted: ${cellId}`)
    } catch (err) {
      log.error('Error deleting cell', err)
      error.value = 'Não foi possível excluir a célula. Tente novamente.'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Select a book
   */
  function selectBook(bookId) {
    selectedBookId.value = bookId
    log.debug(`Book selected: ${bookId}`)
  }

  /**
   * Select a cell
   */
  function selectCell(cellId) {
    selectedCellId.value = cellId
    log.debug(`Cell selected: ${cellId}`)
  }

  /**
   * Toggle book expansion
   */
  function toggleBookExpansion(bookId) {
    const index = expandedBooks.value.indexOf(bookId)
    if (index > -1) {
      expandedBooks.value.splice(index, 1)
    } else {
      expandedBooks.value.push(bookId)
    }
    log.debug(`Book expansion toggled: ${bookId}`)
  }

  /**
   * Refresh notebook items
   */
  async function refresh() {
    await fetchNotebookItems()
  }

  return {
    // State
    books,
    cells,
    selectedBookId,
    selectedCellId,
    isLoading,
    error,
    expandedBooks,

    // Getters
    getCellsForBook,
    getFreeFloatingCellsBook,
    getBooksForDisplay,
    getUnclassifiedMasterBook,
    isBookExpanded,
    selectedCell,
    selectedBook,

    // Actions
    fetchNotebookItems,
    createBook,
    createCell,
    deleteCell,
    selectBook,
    selectCell,
    toggleBookExpansion,
    refresh,
    getUserId,
  }
})
