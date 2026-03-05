/**
 * Composable for filename suggestion logic
 * Extracted from NotebookCell.vue for modularity
 */

export function useFilenameSuggestion() {
  /**
   * Suggest filename based on content
   * @param {string} content - The content to analyze
   * @returns {string} Suggested filename
   */
  function suggestFilename(content) {
    // Extract title or first meaningful line
    const lines = content.trim().split('\n')

    for (let line of lines) {
      line = line.trim()

      // Detect Markdown title
      if (line.startsWith('# ')) {
        const title = line.substring(2).trim()
        return sanitizeFilename(title) + '.md'
      }

      // Detect Python comment (single # followed by space)
      if (line.startsWith('# ') && !line.match(/^#+\s/)) {
        const title = line.substring(2).trim()
        return sanitizeFilename(title) + '.py'
      }

      // Detect JavaScript comment
      if (line.startsWith('// ')) {
        const title = line.substring(3).trim()
        return sanitizeFilename(title) + '.js'
      }

      // First non-empty line as fallback
      if (line.length > 0 && line.length < 50) {
        return sanitizeFilename(line.substring(0, 30)) + '.txt'
      }
    }

    // Fallback: timestamp
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-')
    return `captura_${timestamp}.txt`
  }

  /**
   * Sanitize text to be a valid filename
   * @param {string} text - Text to sanitize
   * @returns {string} Sanitized filename
   */
  function sanitizeFilename(text) {
    return text
      .toLowerCase()
      .replace(/[^a-z0-9\s\-_]/g, '') // Remove special characters
      .replace(/\s+/g, '_') // Replace spaces with underscore
      .substring(0, 50) // Limit size
  }

  return {
    suggestFilename,
    sanitizeFilename,
  }
}
