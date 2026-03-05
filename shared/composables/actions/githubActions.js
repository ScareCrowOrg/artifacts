/**
 * GitHub Actions
 * 
 * Actions for GitHub PR operations: get_pr_report, get_pr_changes, 
 * get_pr_file_diff, get_pr_new_file_content
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'
import { formatFileSize } from './utils'

const log = createLogger('action:github')

/**
 * Register GitHub PR actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerGitHubActions(registerAction) {
  // Action: Get PR Report
  registerAction(
    'get_pr_report',
    async (params, ctx) => {
      const { owner, repo, pr_number } = params
      
      if (!owner || !repo || !pr_number) {
        throw new Error('Parâmetros obrigatórios: owner, repo, pr_number')
      }
      
      log.debug('get_pr_report - Fetching PR report:', { owner, repo, pr_number })
      
      try {
        const response = await apiService.fetch(
          `/api/github/pr/report?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}&pr_number=${pr_number}`
        )
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the report for display
        const formattedReport = `
📊 **Pull Request #${data.number}**

**Title:** ${data.title}

**State:** ${data.state} ${data.merged ? '(Merged ✓)' : ''}
**Author:** ${data.user}
**Base Branch:** ${data.base_branch}
**Head Branch:** ${data.head_branch}

**Statistics:**
- Commits: ${data.commits_count}
- Files Changed: ${data.changed_files}
- Additions: +${data.additions}
- Deletions: -${data.deletions}

**Timestamps:**
- Created: ${data.created_at || 'N/A'}
- Updated: ${data.updated_at || 'N/A'}
${data.merged_at ? `- Merged: ${data.merged_at}` : ''}

**URL:** ${data.url}

${data.body ? `\n**Description:**\n${data.body}` : ''}
`.trim()
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedReport })
        }
        
        log.success('get_pr_report - Report fetched successfully')
        return { success: true, data, message: 'PR report fetched successfully' }
      } catch (error) {
        log.error('get_pr_report - Error:', error)
        throw new Error(`Failed to fetch PR report: ${error.message}`)
      }
    },
    {
      description: 'Get Pull Request report with metadata and statistics',
      params: [
        { name: 'owner', type: 'string', required: true },
        { name: 'repo', type: 'string', required: true },
        { name: 'pr_number', type: 'integer', required: true }
      ],
      category: 'github',
      available: true
    }
  )
  
  // Action: Get PR Changes
  registerAction(
    'get_pr_changes',
    async (params, ctx) => {
      const { owner, repo, pr_number } = params
      
      if (!owner || !repo || !pr_number) {
        throw new Error('Parâmetros obrigatórios: owner, repo, pr_number')
      }
      
      log.debug('get_pr_changes - Fetching PR changes:', { owner, repo, pr_number })
      
      try {
        const response = await apiService.fetch(
          `/api/github/pr/changes?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}&pr_number=${pr_number}`
        )
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the changes list for display
        let formattedChanges = `📝 **Changed Files in PR #${pr_number}** (${data.total} files)\n\n`
        
        data.changes.forEach(change => {
          const statusIcon = {
            'added': '✨',
            'modified': '📝',
            'removed': '🗑️',
            'renamed': '🔄'
          }[change.status] || '📄'
          
          formattedChanges += `${statusIcon} **${change.filename}** (${change.status})\n`
          formattedChanges += `   +${change.additions} -${change.deletions} (~${change.changes} changes)\n`
          if (change.previous_filename) {
            formattedChanges += `   Renamed from: ${change.previous_filename}\n`
          }
          formattedChanges += '\n'
        })
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedChanges.length > 5000) {
            // For large outputs, attach as file
            const filename = `pr_${pr_number}_changes.txt`
            chatStore.addAttachment(filename, formattedChanges, 'text')
            log.debug('get_pr_changes - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedChanges })
          }
        }
        
        log.success('get_pr_changes - Changes fetched successfully:', { count: data.total })
        return { success: true, data, message: `Retrieved ${data.total} changed files` }
      } catch (error) {
        log.error('get_pr_changes - Error:', error)
        throw new Error(`Failed to fetch PR changes: ${error.message}`)
      }
    },
    {
      description: 'Get list of all changed files in a Pull Request',
      params: [
        { name: 'owner', type: 'string', required: true },
        { name: 'repo', type: 'string', required: true },
        { name: 'pr_number', type: 'integer', required: true }
      ],
      category: 'github',
      available: true
    }
  )
  
  // Action: Get PR File Diff
  registerAction(
    'get_pr_file_diff',
    async (params, ctx) => {
      const { owner, repo, pr_number, file_path } = params
      
      if (!owner || !repo || !pr_number || !file_path) {
        throw new Error('Parâmetros obrigatórios: owner, repo, pr_number, file_path')
      }
      
      log.debug('get_pr_file_diff - Fetching file diff:', { owner, repo, pr_number, file_path })
      
      try {
        const response = await apiService.fetch(
          `/api/github/pr/file-diff?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}&pr_number=${pr_number}&file_path=${encodeURIComponent(file_path)}`
        )
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the diff for display
        let formattedDiff = `📄 **File Diff: ${data.filename}**\n\n`
        formattedDiff += `**Status:** ${data.status}\n`
        formattedDiff += `**Changes:** +${data.additions} -${data.deletions} (~${data.changes} total)\n`
        if (data.previous_filename) {
          formattedDiff += `**Renamed from:** ${data.previous_filename}\n`
        }
        formattedDiff += '\n---\n\n'
        
        if (data.patch) {
          formattedDiff += '```diff\n'
          formattedDiff += data.patch
          formattedDiff += '\n```'
        } else {
          formattedDiff += '*(No diff available - file may be binary or too large)*'
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedDiff.length > 10000) {
            // For large diffs, attach as file
            const filename = `${file_path.replace(/\//g, '_')}_diff.txt`
            chatStore.addAttachment(filename, formattedDiff, 'text')
            log.debug('get_pr_file_diff - Diff attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedDiff })
          }
        }
        
        log.success('get_pr_file_diff - Diff fetched successfully')
        return { success: true, data, message: 'File diff retrieved successfully' }
      } catch (error) {
        log.error('get_pr_file_diff - Error:', error)
        throw new Error(`Failed to fetch file diff: ${error.message}`)
      }
    },
    {
      description: 'Get diff for a specific file in a Pull Request',
      params: [
        { name: 'owner', type: 'string', required: true },
        { name: 'repo', type: 'string', required: true },
        { name: 'pr_number', type: 'integer', required: true },
        { name: 'file_path', type: 'string', required: true }
      ],
      category: 'github',
      available: true
    }
  )
  
  // Action: Get PR New File Content
  registerAction(
    'get_pr_new_file_content',
    async (params, ctx) => {
      const { owner, repo, pr_number, file_path } = params
      
      if (!owner || !repo || !pr_number || !file_path) {
        throw new Error('Parâmetros obrigatórios: owner, repo, pr_number, file_path')
      }
      
      log.debug('get_pr_new_file_content - Fetching new file content:', { owner, repo, pr_number, file_path })
      
      try {
        const response = await apiService.fetch(
          `/api/github/pr/new-file-content?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}&pr_number=${pr_number}&file_path=${encodeURIComponent(file_path)}`
        )
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        if (data.error) {
          throw new Error(data.error)
        }
        
        // Format the file content for display
        let formattedContent = `📄 **New File: ${data.filename}**\n\n`
        formattedContent += `**Encoding:** ${data.encoding}\n`
        formattedContent += `**Size:** ${data.size ? formatFileSize(data.size) : 'Unknown'}\n`
        formattedContent += '\n---\n\n'
        
        if (data.content) {
          // Detect language from file extension for syntax highlighting
          const ext = data.filename.split('.').pop()
          const langMap = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'jsx': 'jsx',
            'tsx': 'tsx',
            'json': 'json',
            'yml': 'yaml',
            'yaml': 'yaml',
            'md': 'markdown',
            'html': 'html',
            'css': 'css',
            'sh': 'bash'
          }
          const lang = langMap[ext] || ext
          
          formattedContent += '```' + lang + '\n'
          formattedContent += data.content
          formattedContent += '\n```'
        } else {
          formattedContent += '*(No content available)*'
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedContent.length > 10000) {
            // For large files, attach as file
            const filename = data.filename.split('/').pop()
            chatStore.addAttachment(filename, data.content, 'text')
            log.debug('get_pr_new_file_content - Content attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedContent })
          }
        }
        
        log.success('get_pr_new_file_content - Content fetched successfully')
        return { success: true, data, message: 'New file content retrieved successfully' }
      } catch (error) {
        log.error('get_pr_new_file_content - Error:', error)
        throw new Error(`Failed to fetch new file content: ${error.message}`)
      }
    },
    {
      description: 'Get content of a newly added file in a Pull Request',
      params: [
        { name: 'owner', type: 'string', required: true },
        { name: 'repo', type: 'string', required: true },
        { name: 'pr_number', type: 'integer', required: true },
        { name: 'file_path', type: 'string', required: true }
      ],
      category: 'github',
      available: true
    }
  )
}
