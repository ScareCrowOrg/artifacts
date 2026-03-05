/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-24",
 *   "console_calls_found": 17,
 *   "console_calls_migrated": 17,
 *   "migration_rate": 100,
 *   "logger_namespace": "utils:indexeddb",
 *   "validation_status": "excellent"
 * }
 */
/**
 * IndexedDB Wrapper for ScareVerse Vault
 * 
 * Provides a simple interface for storing and retrieving encrypted vault entries
 * in the browser's IndexedDB. This wrapper handles database initialization,
 * version management, and CRUD operations.
 */

import { createLogger } from '@/utils/logger'

const log = createLogger('utils:indexeddb')

const DB_NAME = 'ScareVerseVault';
const DB_VERSION = 1;
const STORE_NAME = 'credentials';

export class IndexedDBWrapper {
  constructor() {
    this.db = null;
  }

  /**
   * Initialize the IndexedDB database
   * Creates the object store if it doesn't exist
   */
  async init() {
    if (this.db) {
      return this.db;
    }

    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = () => {
        const error = request.error || new Error('Failed to open IndexedDB');
        log.error('Open error', error);
        reject(error);
      };

      request.onsuccess = () => {
        this.db = request.result;
        log.info('Database opened successfully');
        resolve(this.db);
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Create object store if it doesn't exist
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const objectStore = db.createObjectStore(STORE_NAME, { keyPath: 'vaultRef' });
          
          // Create indexes for efficient querying
          objectStore.createIndex('provider', 'provider', { unique: false });
          objectStore.createIndex('createdAt', 'createdAt', { unique: false });
          objectStore.createIndex('expiresAt', 'expiresAt', { unique: false });
          
          log.info('Object store created with indexes');
        }
      };
    });
  }

  /**
   * Store an encrypted vault entry
   * @param {string} vaultRef - Unique vault reference ID
   * @param {Object} encryptedData - Encrypted vault entry data
   */
  async store(vaultRef, encryptedData) {
    const db = await this.init();
    
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const objectStore = transaction.objectStore(STORE_NAME);
      
      const data = {
        vaultRef,
        provider: encryptedData.provider,
        credentialType: encryptedData.credentialType,
        encryptedValue: encryptedData.encryptedValue,
        iv: encryptedData.iv,
        authTag: encryptedData.authTag,
        salt: encryptedData.salt,
        createdAt: encryptedData.createdAt,
        expiresAt: encryptedData.expiresAt,
        updatedAt: new Date().toISOString()
      };
      
      const request = objectStore.put(data);
      
      request.onsuccess = () => {
        log.debug('Stored entry', { vaultRef });
        resolve(vaultRef);
      };
      
      request.onerror = () => {
        const error = request.error || new Error('Failed to store entry');
        log.error('Store error', error);
        reject(error);
      };
    });
  }

  /**
   * Retrieve an encrypted vault entry
   * @param {string} vaultRef - Unique vault reference ID
   * @returns {Object|null} Encrypted vault entry or null if not found
   */
  async retrieve(vaultRef) {
    const db = await this.init();
    
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([STORE_NAME], 'readonly');
      const objectStore = transaction.objectStore(STORE_NAME);
      const request = objectStore.get(vaultRef);
      
      request.onsuccess = () => {
        const result = request.result;
        if (result) {
          log.debug('Retrieved entry', { vaultRef });
          resolve(result);
        } else {
          log.warn('Entry not found', { vaultRef });
          resolve(null);
        }
      };
      
      request.onerror = () => {
        const error = request.error || new Error('Failed to retrieve entry');
        log.error('Retrieve error', error);
        reject(error);
      };
    });
  }

  /**
   * Delete a vault entry
   * @param {string} vaultRef - Unique vault reference ID
   * @returns {boolean} True if deleted, false if not found
   */
  async delete(vaultRef) {
    const db = await this.init();
    
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const objectStore = transaction.objectStore(STORE_NAME);
      
      // Check if entry exists first
      const getRequest = objectStore.get(vaultRef);
      
      getRequest.onsuccess = () => {
        if (!getRequest.result) {
          log.warn('Entry not found for deletion', { vaultRef });
          resolve(false);
          return;
        }
        
        const deleteRequest = objectStore.delete(vaultRef);
        
        deleteRequest.onsuccess = () => {
          log.debug('Deleted entry', { vaultRef });
          resolve(true);
        };
        
        deleteRequest.onerror = () => {
          const error = deleteRequest.error || new Error('Failed to delete entry');
          log.error('Delete error', error);
          reject(error);
        };
      };
      
      getRequest.onerror = () => {
        const error = getRequest.error || new Error('Failed to check entry');
        log.error('Get error during delete', error);
        reject(error);
      };
    });
  }

  /**
   * List all vault entries (metadata only)
   * @returns {Array} Array of vault metadata
   */
  async list() {
    const db = await this.init();
    
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([STORE_NAME], 'readonly');
      const objectStore = transaction.objectStore(STORE_NAME);
      const request = objectStore.getAll();
      
      request.onsuccess = () => {
        const entries = request.result || [];
        log.debug('Listed entries', { count: entries.length });
        
        // Return only metadata, not the encrypted values
        const metadata = entries.map(entry => ({
          vaultRef: entry.vaultRef,
          provider: entry.provider,
          credentialType: entry.credentialType,
          createdAt: entry.createdAt,
          expiresAt: entry.expiresAt,
          updatedAt: entry.updatedAt
        }));
        
        resolve(metadata);
      };
      
      request.onerror = () => {
        const error = request.error || new Error('Failed to list entries');
        log.error('List error', error);
        reject(error);
      };
    });
  }

  /**
   * Clear all vault entries (for testing or reset)
   */
  async clear() {
    const db = await this.init();
    
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const objectStore = transaction.objectStore(STORE_NAME);
      const request = objectStore.clear();
      
      request.onsuccess = () => {
        log.info('Cleared all entries');
        resolve();
      };
      
      request.onerror = () => {
        const error = request.error || new Error('Failed to clear entries');
        log.error('Clear error', error);
        reject(error);
      };
    });
  }

  /**
   * Close the database connection
   */
  close() {
    if (this.db) {
      this.db.close();
      this.db = null;
      log.info('Database closed');
    }
  }
}

// Create and export a singleton instance
let wrapperInstance = null;

export function getIndexedDBWrapper() {
  if (!wrapperInstance) {
    wrapperInstance = new IndexedDBWrapper();
  }
  return wrapperInstance;
}

// Initialize on window load for global access
if (typeof window !== 'undefined') {
  window.indexedDBWrapper = getIndexedDBWrapper();
}
