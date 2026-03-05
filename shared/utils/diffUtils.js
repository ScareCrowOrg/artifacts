/**
 * Simple diff utility for comparing file contents
 * Generates line-by-line diff for visualization
 */

/**
 * Compute diff between two text contents
 * @param {string} original - Original content
 * @param {string} updated - Updated content
 * @returns {Array} Array of diff lines with metadata
 */
export function computeDiff(original, updated) {
  const originalLines = original.split('\n')
  const updatedLines = updated.split('\n')
  
  // Handle empty strings: split('\n') on '' gives [''] instead of []
  const originalFiltered = original === '' ? [] : originalLines
  const updatedFiltered = updated === '' ? [] : updatedLines
  
  const diff = []
  
  // Simple line-by-line comparison
  // For more advanced diff, we could use a library like diff-match-patch
  let i = 0
  let j = 0
  
  while (i < originalFiltered.length || j < updatedFiltered.length) {
    const originalLine = i < originalFiltered.length ? originalFiltered[i] : null
    const updatedLine = j < updatedFiltered.length ? updatedFiltered[j] : null
    
    if (originalLine === null) {
      // Addition at end
      diff.push({
        type: 'added',
        lineNumber: j + 1,
        content: updatedLine
      })
      j++
    } else if (updatedLine === null) {
      // Deletion at end
      diff.push({
        type: 'deleted',
        lineNumber: i + 1,
        content: originalLine
      })
      i++
    } else if (originalLine === updatedLine) {
      // Unchanged line
      diff.push({
        type: 'unchanged',
        lineNumber: i + 1,
        content: originalLine
      })
      i++
      j++
    } else {
      // Changed line (simple approach: mark as deletion + addition)
      diff.push({
        type: 'deleted',
        lineNumber: i + 1,
        content: originalLine
      })
      diff.push({
        type: 'added',
        lineNumber: j + 1,
        content: updatedLine
      })
      i++
      j++
    }
  }
  
  return diff
}

/**
 * Compute diff statistics
 * @param {Array} diff - Diff array from computeDiff
 * @returns {Object} Statistics about the diff
 */
export function getDiffStats(diff) {
  const stats = {
    additions: 0,
    deletions: 0,
    unchanged: 0,
    total: diff.length
  }
  
  diff.forEach(line => {
    if (line.type === 'added') stats.additions++
    else if (line.type === 'deleted') stats.deletions++
    else if (line.type === 'unchanged') stats.unchanged++
  })
  
  return stats
}

/**
 * Format diff for display
 * @param {Array} diff - Diff array from computeDiff
 * @returns {string} Formatted diff text
 */
export function formatDiff(diff) {
  return diff.map(line => {
    const prefix = line.type === 'added' ? '+' : line.type === 'deleted' ? '-' : ' '
    return `${prefix} ${line.content}`
  }).join('\n')
}
