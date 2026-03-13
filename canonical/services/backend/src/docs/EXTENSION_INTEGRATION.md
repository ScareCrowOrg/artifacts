---
processed: true
processed_date: 2025-12-09
themes:
  - api
  - integration
  - file-persistence
  - backend
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Backend Integration Guide for Cockpit Extension

This guide shows how to integrate the ScareCopilotPortal Backend API with the Cockpit Chrome Extension.

## 🚀 Quick Start

### 1. Start the Backend Server

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000/api`

### 2. Update Extension Configuration

In your extension's JavaScript files, configure the API base URL:

```javascript
// In your extension's config or constants file
const API_CONFIG = {
  baseUrl: 'http://localhost:8000/api',
  timeout: 30000  // 30 seconds
};
```

## 📝 Usage Examples

### Example 1: Get Directory Tree

```javascript
// Get directory tree in nested format
async function getDirectoryTree() {
  try {
    const response = await fetch(
      `${API_CONFIG.baseUrl}/tree?format=tree&max_depth=3`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('Directory tree:', data);
    return data;
  } catch (error) {
    console.error('Error fetching tree:', error);
    throw error;
  }
}

// Get flat list of files only
async function getFileList() {
  const response = await fetch(
    `${API_CONFIG.baseUrl}/tree?format=flat&file_type=file`
  );
  const data = await response.json();
  return data.data;  // Returns array of file objects
}
```

### Example 2: Save a Single File

```javascript
// Save a JavaScript file
async function saveFile(relativePath, filename, content) {
  try {
    // Encode content to base64
    const encodedContent = btoa(content);
    
    const response = await fetch(
      `${API_CONFIG.baseUrl}/persist/${relativePath}/${filename}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content: encodedContent
        })
      }
    );
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to save file');
    }
    
    const result = await response.json();
    console.log('File saved:', result);
    return result;
  } catch (error) {
    console.error('Error saving file:', error);
    throw error;
  }
}

// Usage
await saveFile('scripts', 'hello.js', "console.log('Hello World!');");
```

### Example 3: Save Multiple Files (Batch)

```javascript
// Save multiple files at once
async function saveMultipleFiles(files) {
  try {
    // Prepare files with base64-encoded content
    const encodedFiles = files.map(file => ({
      path: file.path,
      filename: file.filename,
      content: btoa(file.content)
    }));
    
    const response = await fetch(
      `${API_CONFIG.baseUrl}/persist-batch`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          files: encodedFiles
        })
      }
    );
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Batch upload failed');
    }
    
    const result = await response.json();
    console.log(`Batch upload: ${result.success_count} succeeded, ${result.error_count} failed`);
    return result;
  } catch (error) {
    console.error('Error in batch upload:', error);
    throw error;
  }
}

// Usage
await saveMultipleFiles([
  {
    path: 'scripts',
    filename: 'app.js',
    content: 'console.log("App");'
  },
  {
    path: 'styles',
    filename: 'main.css',
    content: 'body { margin: 0; }'
  }
]);
```

### Example 4: Download a File

```javascript
// Download a file from ScareFeraLab
async function downloadFile(filePath) {
  try {
    const response = await fetch(
      `${API_CONFIG.baseUrl}/ScareFeraLab/${filePath}`
    );
    
    if (!response.ok) {
      throw new Error(`File not found: ${filePath}`);
    }
    
    const content = await response.text();
    console.log('File content:', content);
    return content;
  } catch (error) {
    console.error('Error downloading file:', error);
    throw error;
  }
}

// Usage
const content = await downloadFile('scripts/hello.js');
```

### Example 5: Refresh Tree Cache

```javascript
// Refresh tree cache after file operations
async function refreshTree() {
  try {
    const response = await fetch(
      `${API_CONFIG.baseUrl}/tree-refresh`,
      {
        method: 'POST'
      }
    );
    
    const result = await response.json();
    console.log('Tree refreshed:', result.message);
    return result.tree;
  } catch (error) {
    console.error('Error refreshing tree:', error);
    throw error;
  }
}
```

## 🔧 Complete Integration Example

Here's a complete example of a utility class for the Cockpit Extension:

```javascript
// backend-client.js
class BackendClient {
  constructor(baseUrl = 'http://localhost:8000/api') {
    this.baseUrl = baseUrl;
  }
  
  // Helper to encode content
  encodeContent(content) {
    return btoa(unescape(encodeURIComponent(content)));
  }
  
  // Helper to decode content
  decodeContent(encoded) {
    return decodeURIComponent(escape(atob(encoded)));
  }
  
  // Get directory tree
  async getTree(format = 'tree', options = {}) {
    const params = new URLSearchParams({
      format,
      ...options
    });
    
    const response = await fetch(`${this.baseUrl}/tree?${params}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
  
  // Save single file
  async saveFile(path, filename, content) {
    const response = await fetch(
      `${this.baseUrl}/persist/${path}/${filename}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: this.encodeContent(content)
        })
      }
    );
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Save failed');
    }
    
    return response.json();
  }
  
  // Save multiple files
  async saveBatch(files) {
    const encodedFiles = files.map(f => ({
      path: f.path,
      filename: f.filename,
      content: this.encodeContent(f.content)
    }));
    
    const response = await fetch(
      `${this.baseUrl}/persist-batch`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files: encodedFiles })
      }
    );
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Batch save failed');
    }
    
    return response.json();
  }
  
  // Load file content
  async loadFile(filePath) {
    const response = await fetch(
      `${this.baseUrl}/ScareFeraLab/${filePath}`
    );
    
    if (!response.ok) {
      throw new Error(`File not found: ${filePath}`);
    }
    
    return response.text();
  }
  
  // Refresh tree cache
  async refreshTree() {
    const response = await fetch(
      `${this.baseUrl}/tree-refresh`,
      { method: 'POST' }
    );
    
    return response.json();
  }
  
  // Health check
  async checkHealth() {
    const response = await fetch(`${this.baseUrl}/health`);
    return response.json();
  }
}

// Usage in extension
const backend = new BackendClient();

// Check if backend is available
try {
  const health = await backend.checkHealth();
  console.log('Backend status:', health.status);
} catch (error) {
  console.error('Backend not available:', error);
}

// Save a file
await backend.saveFile('tests', 'example.js', 'console.log("Hello");');

// Load directory tree
const tree = await backend.getTree('flat', { file_type: 'file' });
console.log('Files:', tree.data);

// Save multiple files
await backend.saveBatch([
  { path: 'src', filename: 'app.js', content: '// App code' },
  { path: 'src', filename: 'utils.js', content: '// Utils' }
]);
```

## 🎨 UI Integration Example

Example of showing the directory tree in the extension UI:

```javascript
// In your sidepanel.js or popup
async function displayFileTree() {
  try {
    const backend = new BackendClient();
    const result = await backend.getTree('flat', { file_type: 'file' });
    
    const fileList = document.getElementById('file-list');
    fileList.innerHTML = '';
    
    result.data.forEach(item => {
      if (item.type === 'file') {
        const fileElement = document.createElement('div');
        fileElement.className = 'file-item';
        fileElement.innerHTML = `
          <span class="file-icon">📄</span>
          <span class="file-path">${item.path}</span>
          <span class="file-size">${item.size} bytes</span>
        `;
        
        fileElement.addEventListener('click', async () => {
          const content = await backend.loadFile(item.path);
          displayFileContent(content);
        });
        
        fileList.appendChild(fileElement);
      }
    });
  } catch (error) {
    console.error('Error displaying tree:', error);
    showError('Failed to load file tree. Is the backend running?');
  }
}
```

## ⚠️ Error Handling

Always handle errors properly:

```javascript
async function safeBackendCall(operation) {
  try {
    return await operation();
  } catch (error) {
    // Check if it's a network error
    if (error.message.includes('fetch')) {
      console.error('Backend is not accessible. Make sure it is running.');
      return null;
    }
    
    // Check if it's a validation error
    if (error.message.includes('traversal') || 
        error.message.includes('extension')) {
      console.error('Invalid input:', error.message);
      return null;
    }
    
    // Unknown error
    console.error('Backend error:', error);
    return null;
  }
}

// Usage
const result = await safeBackendCall(async () => {
  return await backend.saveFile('test', 'file.js', content);
});
```

## 🔒 Security Notes

1. **Base64 Encoding**: Always encode content before sending to the API
2. **Path Validation**: The backend validates all paths - don't try to bypass
3. **File Extensions**: Only allowed extensions can be saved (see `utils.py`)
4. **CORS**: Backend is configured to accept requests from any origin in development
5. **File Size**: Maximum 10MB per file

## 📚 API Reference

For complete API documentation, visit:
- Interactive Docs: http://localhost:8000/api/docs
- Alternative Docs: http://localhost:8000/api/redoc

## 🐛 Troubleshooting

### Backend not accessible

```bash
# Check if backend is running
curl http://localhost:8000/api/health

# If not, start it
cd backend
python -m uvicorn app.main:app --reload
```

### CORS errors

Make sure the backend is running and CORS is properly configured in `backend/app/config.py`.

### File not saving

Check the browser console for error messages. Common issues:
- Invalid file extension
- Invalid base64 encoding
- Path traversal attempt
- File too large (>10MB)

## 🎯 Next Steps

1. Integrate the `BackendClient` class into your extension
2. Update your UI to display file trees and enable file operations
3. Test all operations with the backend running
4. Consider adding authentication for production use
