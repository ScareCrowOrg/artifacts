/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-02-08",
 *   "console_calls_found": 0,
 *   "console_calls_migrated": 0,
 *   "migration_rate": 100,
 *   "logger_namespace": "vault",
 *   "validation_status": "excellent"
 * }
 */
/**
 * useVault - STUB IMPLEMENTATION (Extension Removed)
 * 
 * ⚠️ DEPRECATED: Browser extension vault has been removed.
 * 
 * This composable now returns a stub implementation that indicates the vault
 * is unavailable. All methods throw errors directing users to alternative
 * credential management approaches.
 * 
 * Historical Context:
 * - Previously provided browser extension-based credential storage
 * - Removed as part of dead code cleanup (extension never production-ready)
 * - Extension was "Development / Template" status
 * 
 * Migration Path:
 * - Use backend credential management APIs instead
 * - Or implement direct environment variable configuration
 * 
 * @deprecated Browser extension vault removed. Use backend credential APIs.
 * @version 2.0.0 - Stub implementation
 */

import { ref, computed } from 'vue';
import { createLogger } from '@/utils/logger';

const log = createLogger('vault');

// Vault state (always unavailable now)
const isUnlocked = ref(false);
const isLoading = ref(false);
const error = ref('Vault is unavailable - browser extension removed');

export function useVault() {
  /**
   * Check if vault is available (always false now)
   */
  const isVaultAvailable = computed(() => false);

  /**
   * Lock the vault (no-op)
   */
  const lockVault = () => {
    log.warn('lockVault called but vault is unavailable (extension removed)');
  };

  /**
   * Unlock the vault with master key (always fails)
   */
  const unlockVault = async (masterKey) => {
    throw new Error('Vault unavailable - browser extension was removed. Use backend credential APIs instead.');
  };

  /**
   * Store a credential (always fails)
   */
  const storeCredential = async (vaultRef, provider, credentialValue, credentialType = 'api_key', expiresAt = null) => {
    throw new Error('Vault unavailable - browser extension was removed. Use backend credential APIs instead.');
  };

  /**
   * Retrieve a credential (always fails)
   */
  const retrieveCredential = async (vaultRef) => {
    throw new Error('Vault unavailable - browser extension was removed. Use backend credential APIs instead.');
  };

  /**
   * Delete a credential (always fails)
   */
  const deleteCredential = async (vaultRef) => {
    throw new Error('Vault unavailable - browser extension was removed. Use backend credential APIs instead.');
  };

  /**
   * List all credentials (always returns empty)
   */
  const listCredentials = async () => {
    log.warn('listCredentials called but vault is unavailable (extension removed)');
    return [];
  };

  return {
    // State
    isVaultAvailable,
    isUnlocked,
    isLoading,
    error,

    // Methods
    lockVault,
    unlockVault,
    storeCredential,
    retrieveCredential,
    deleteCredential,
    listCredentials
  };
}
