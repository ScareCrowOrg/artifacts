/**
 * Books Actions
 * 
 * Actions for books management: list_books, get_book, create_book,
 * update_book, delete_book, add_cell_to_book
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:books')

/**
 * Register books management actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerBooksActions(registerAction) {
  // Action: List Books
  registerAction(
    'list_books',
    async (params, ctx) => {
      const { assignee_id } = params
      
      log.debug('list_books - Fetching books list:', { assignee_id })
      
      try {
        const queryParams = assignee_id ? `?assignee_id=${encodeURIComponent(assignee_id)}` : ''
        const response = await apiService.fetch(`/api/books/list${queryParams}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the books list for display
        let formattedOutput = `📚 **Books List** (${data.length} book${data.length !== 1 ? 's' : ''})\n\n`
        
        if (data.length === 0) {
          formattedOutput += '*No books found*'
        } else {
          // Group by type
          const byType = {}
          data.forEach(book => {
            const type = book.type || 'unknown'
            if (!byType[type]) byType[type] = []
            byType[type].push(book)
          })
          
          // Display by type groups
          Object.entries(byType).forEach(([type, books]) => {
            const typeIcon = {
              'canonical': '📖',
              'volatile': '📝',
              'persistent': '💾'
            }[type.toLowerCase()] || '📕'
            
            formattedOutput += `**${typeIcon} ${type.toUpperCase()}** (${books.length})\n`
            books.forEach(book => {
              formattedOutput += `  • **${book.name}**\n`
              formattedOutput += `    ID: ${book.id}\n`
              if (book.description) {
                formattedOutput += `    Description: ${book.description}\n`
              }
              if (book.purpose) {
                formattedOutput += `    Purpose: ${book.purpose}\n`
              }
              formattedOutput += `    Cells: ${book.cells?.length || 0}\n`
              formattedOutput += `    Assignee: ${book.assignee_id}\n`
            })
            formattedOutput += '\n'
          })
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            const filename = `books_list_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('list_books - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('list_books - Books list fetched successfully:', { count: data.length })
        return { success: true, data, message: `Retrieved ${data.length} books` }
      } catch (error) {
        log.error('list_books - Error:', error)
        throw new Error(`Failed to fetch books list: ${error.message}`)
      }
    },
    {
      description: 'List books with RBAC filtering',
      params: [
        { name: 'assignee_id', type: 'string', required: false }
      ],
      category: 'books',
      available: true
    }
  )
  
  // Action: Get Book
  registerAction(
    'get_book',
    async (params, ctx) => {
      const { book_id } = params
      
      if (!book_id) {
        throw new Error('Missing required parameter: book_id')
      }
      
      log.debug('get_book - Fetching book:', { book_id })
      
      try {
        const response = await apiService.fetch(`/api/books/${encodeURIComponent(book_id)}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const book = await response.json()
        
        // Format book details
        const typeIcon = {
          'canonical': '📖',
          'volatile': '📝',
          'persistent': '💾'
        }[book.type?.toLowerCase()] || '📕'
        
        let formattedOutput = `${typeIcon} **Book Details**\n\n`
        formattedOutput += `**Name:** ${book.name}\n`
        formattedOutput += `**ID:** ${book.id}\n`
        formattedOutput += `**Type:** ${book.type}\n`
        if (book.description) {
          formattedOutput += `**Description:** ${book.description}\n`
        }
        if (book.purpose) {
          formattedOutput += `**Purpose:** ${book.purpose}\n`
        }
        formattedOutput += `**Assignee:** ${book.assignee_id}\n`
        if (book.notebook_item_type_id) {
          formattedOutput += `**Item Type:** ${book.notebook_item_type_id}\n`
        }
        formattedOutput += `**Cells:** ${book.cells?.length || 0}\n`
        
        if (book.cells && book.cells.length > 0) {
          formattedOutput += `\n**Cell IDs:**\n`
          book.cells.forEach(cellId => {
            formattedOutput += `  • ${cellId}\n`
          })
        }
        
        if (book.refs && Object.keys(book.refs).length > 0) {
          formattedOutput += `\n**References:**\n`
          Object.entries(book.refs).forEach(([key, value]) => {
            formattedOutput += `  • ${key}: ${value}\n`
          })
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('get_book - Book fetched successfully:', { book_id })
        return { success: true, data: book, message: 'Book retrieved successfully' }
      } catch (error) {
        log.error('get_book - Error:', error)
        throw new Error(`Failed to fetch book: ${error.message}`)
      }
    },
    {
      description: 'Get a specific book by ID',
      params: [
        { name: 'book_id', type: 'string', required: true }
      ],
      category: 'books',
      available: true
    }
  )
  
  // Action: Create Book
  registerAction(
    'create_book',
    async (params, ctx) => {
      const { name, description, purpose, assignee_id, notebook_item_type_id, refs } = params
      
      if (!name) {
        throw new Error('Missing required parameter: name')
      }
      
      log.debug('create_book - Creating book:', { name, description, purpose })
      
      try {
        const requestBody = {
          name,
          description: description || null,
          purpose: purpose || null,
          assignee_id: assignee_id || null,
          notebook_item_type_id: notebook_item_type_id || null,
          refs: refs || null
        }
        
        const response = await apiService.fetch('/api/books/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestBody)
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const book = await response.json()
        
        const formattedOutput = `📚 **Book Created Successfully**\n\n` +
          `**Name:** ${book.name}\n` +
          `**ID:** ${book.id}\n` +
          `**Type:** ${book.type}\n` +
          `${book.description ? `**Description:** ${book.description}\n` : ''}` +
          `${book.purpose ? `**Purpose:** ${book.purpose}\n` : ''}` +
          `**Assignee:** ${book.assignee_id}\n` +
          `\n✅ Book created successfully`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('create_book - Book created successfully:', { book_id: book.id })
        return { success: true, data: book, message: 'Book created successfully' }
      } catch (error) {
        log.error('create_book - Error:', error)
        throw new Error(`Failed to create book: ${error.message}`)
      }
    },
    {
      description: 'Create a new book',
      params: [
        { name: 'name', type: 'string', required: true },
        { name: 'description', type: 'string', required: false },
        { name: 'purpose', type: 'string', required: false },
        { name: 'assignee_id', type: 'string', required: false },
        { name: 'notebook_item_type_id', type: 'string', required: false },
        { name: 'refs', type: 'object', required: false }
      ],
      category: 'books',
      available: true
    }
  )
  
  // Action: Update Book
  registerAction(
    'update_book',
    async (params, ctx) => {
      const { book_id, name, description, purpose } = params
      
      if (!book_id) {
        throw new Error('Missing required parameter: book_id')
      }
      
      if (!name && !description && !purpose) {
        throw new Error('At least one field (name, description, purpose) must be provided')
      }
      
      log.debug('update_book - Updating book:', { book_id, name, description, purpose })
      
      try {
        const queryParams = new URLSearchParams()
        if (name) queryParams.append('name', name)
        if (description) queryParams.append('description', description)
        if (purpose) queryParams.append('purpose', purpose)
        
        const response = await apiService.fetch(`/api/books/${encodeURIComponent(book_id)}?${queryParams}`, {
          method: 'PUT'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const book = await response.json()
        
        const formattedOutput = `📚 **Book Updated Successfully**\n\n` +
          `**Name:** ${book.name}\n` +
          `**ID:** ${book.id}\n` +
          `${book.description ? `**Description:** ${book.description}\n` : ''}` +
          `${book.purpose ? `**Purpose:** ${book.purpose}\n` : ''}` +
          `\n✅ Book updated successfully`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('update_book - Book updated successfully:', { book_id })
        return { success: true, data: book, message: 'Book updated successfully' }
      } catch (error) {
        log.error('update_book - Error:', error)
        throw new Error(`Failed to update book: ${error.message}`)
      }
    },
    {
      description: 'Update an existing book',
      params: [
        { name: 'book_id', type: 'string', required: true },
        { name: 'name', type: 'string', required: false },
        { name: 'description', type: 'string', required: false },
        { name: 'purpose', type: 'string', required: false }
      ],
      category: 'books',
      available: true
    }
  )
  
  // Action: Delete Book
  registerAction(
    'delete_book',
    async (params, ctx) => {
      const { book_id } = params
      
      if (!book_id) {
        throw new Error('Missing required parameter: book_id')
      }
      
      log.debug('delete_book - Deleting book:', { book_id })
      
      try {
        const response = await apiService.fetch(`/api/books/${encodeURIComponent(book_id)}`, {
          method: 'DELETE'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const formattedOutput = `🗑️ **Book Deleted Successfully**\n\n` +
          `**Book ID:** ${book_id}\n` +
          `\n✅ Book deleted successfully`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('delete_book - Book deleted successfully:', { book_id })
        return { success: true, message: 'Book deleted successfully' }
      } catch (error) {
        log.error('delete_book - Error:', error)
        throw new Error(`Failed to delete book: ${error.message}`)
      }
    },
    {
      description: 'Delete a book',
      params: [
        { name: 'book_id', type: 'string', required: true }
      ],
      category: 'books',
      available: true
    }
  )
  
  // Action: Add Cell to Book
  registerAction(
    'add_cell_to_book',
    async (params, ctx) => {
      const { book_id, cell_id } = params
      
      if (!book_id) {
        throw new Error('Missing required parameter: book_id')
      }
      if (!cell_id) {
        throw new Error('Missing required parameter: cell_id')
      }
      
      log.debug('add_cell_to_book - Adding cell to book:', { book_id, cell_id })
      
      try {
        const response = await apiService.fetch(`/api/books/${encodeURIComponent(book_id)}/add_cell`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cell_id })
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const book = await response.json()
        
        const formattedOutput = `📚 **Cell Added to Book**\n\n` +
          `**Book:** ${book.name}\n` +
          `**Book ID:** ${book.id}\n` +
          `**Cell ID:** ${cell_id}\n` +
          `**Total Cells:** ${book.cells?.length || 0}\n` +
          `\n✅ Cell added successfully`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('add_cell_to_book - Cell added to book successfully:', { book_id, cell_id })
        return { success: true, data: book, message: 'Cell added to book successfully' }
      } catch (error) {
        log.error('add_cell_to_book - Error:', error)
        throw new Error(`Failed to add cell to book: ${error.message}`)
      }
    },
    {
      description: 'Add a cell to a book',
      params: [
        { name: 'book_id', type: 'string', required: true },
        { name: 'cell_id', type: 'string', required: true }
      ],
      category: 'books',
      available: true
    }
  )
}
