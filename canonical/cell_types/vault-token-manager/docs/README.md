---
processed: true
processed_date: 2025-12-23
updated_docs:
  - docs/official/frontend/security/vault-token-manager.md
themes:
  - security
  - encryption
  - technical
modules:
  - frontend
  - security
code_verified: true
dead_docs_found: false
---
# Vault Token Manager Cell

## Overview

The **Vault Token Manager** is an ephemeral cell type designed to provide a secure, user-friendly interface for managing encrypted tokens stored in the Wasm Sidecar Vault. It replaces the insecure `window.prompt()` mechanism with a dedicated UI for vault operations.

## Features

### Security
- **Secure Password Modal**: Custom modal for master password input (replacing `window.prompt()`)
- **AES-256-GCM Encryption**: All tokens encrypted before storage
- **PBKDF2 Key Derivation**: Strong key derivation from master password
- **Auto-Lock**: Automatic vault locking after 5 minutes of inactivity
- **No Plaintext Display**: Token values never shown in list view

### User Interface
- **Token List**: Display all stored tokens with metadata
- **Add Token**: Interactive form for adding new encrypted tokens
- **View Token**: Secure retrieval and display of decrypted token values
- **Delete Token**: Remove tokens with confirmation dialog
- **Filter & Sort**: Filter expired tokens, sort by date/provider/name

### Integration
- **Dynamic Layout Compatible**: Works seamlessly with the dynamic workspace system
- **Plug-and-Play**: Self-contained cell type following ScareVerse architecture
- **i18n Support**: Full internationalization (English and Portuguese)
- **Theme Compliant**: Dark mode support and Tailwind theme consistency

## Architecture

### Components

```
vault-token-manager/
├── frontend/
│   ├── View.vue              # Main cell view component
│   ├── VaultUnlockModal.vue  # Secure password input modal
│   ├── VaultTokenList.vue    # Token listing component
│   └── VaultTokenForm.vue    # Add/edit token form
├── docs/
│   └── README.md             # This file
└── type.json                 # Symlink to canonical definition
```

### Data Flow

```
User → VaultUnlockModal → useVault composable → Wasm Sidecar Vault
                                ↓
                        IndexedDB (encrypted)
```

1. **Unlock**: User enters master password in secure modal
2. **List**: Load encrypted token metadata (no values)
3. **Add**: Encrypt token value with master key, store in vault
4. **View**: Decrypt token value on-demand
5. **Delete**: Remove encrypted token from vault

## Usage

### Adding to Workspace

1. Click the "+" button in the footer window manager
2. Search for "Vault Token Manager" in AddCellModal
3. Select and add the cell to your workspace

### Unlocking the Vault

1. Click the "Unlock" button (🔓) in the cell header
2. Enter your master password in the secure modal
3. Vault will auto-lock after 5 minutes of inactivity

### Managing Tokens

#### Add a New Token
1. Click "Add Token" button
2. Fill in the form:
   - **Token Name**: Unique identifier (e.g., `openai-api-key-prod`)
   - **Provider**: Select from dropdown or specify custom
   - **Credential Type**: API Key, OAuth Token, JWT, etc.
   - **Token Value**: Paste your actual token/secret
   - **Expiration Date**: Optional expiration tracking
3. Click "Save Token"

#### View a Token
1. Click the eye icon (👁️) on any token card
2. Token value will be decrypted and displayed
3. **Warning**: Handle decrypted values securely

#### Delete a Token
1. Click the trash icon (🗑️) on any token card
2. Confirm deletion in dialog
3. Token is permanently removed

### Filtering & Sorting

- **Show Expired**: Toggle to show/hide expired tokens
- **Sort By**: Sort by creation date, provider, or token name
- **Sort Order**: Toggle ascending/descending order

## Integration with Vault Composable

The cell uses the `useVault` composable from `@/composables/useVault.js`:

```javascript
import { useVault } from '@/composables/useVault.js'

const vault = useVault()

// Unlock vault
await vault.unlockVault(masterKey)

// List tokens (metadata only)
const tokens = await vault.listCredentials()

// Store encrypted token
await vault.storeCredential(vaultRef, provider, credentialValue, credentialType, expiresAt)

// Retrieve decrypted token
const entry = await vault.retrieveCredential(vaultRef)

// Delete token
await vault.deleteCredential(vaultRef)

// Lock vault
vault.lockVault()
```

## Security Considerations

### ✅ Secure
- Master password never stored in memory longer than needed
- All tokens encrypted with AES-256-GCM before IndexedDB storage
- Password input modal prevents logging and masking issues
- Auto-lock timer prevents unauthorized access

### ⚠️ Limitations
- Master password must be memorized (no recovery mechanism)
- Decrypted token values shown in alert() (TODO: dedicated secure modal)
- No two-factor authentication for vault access
- Browser-based storage (not suitable for highly sensitive environments)

## Cell Type Configuration

### Properties Schema

```json
{
  "autoLockEnabled": {
    "type": "boolean",
    "default": true,
    "description": "Enable automatic vault locking after timeout"
  },
  "showExpired": {
    "type": "boolean",
    "default": false,
    "description": "Show expired tokens in the list"
  },
  "sortBy": {
    "type": "string",
    "default": "createdAt",
    "enum": ["createdAt", "provider", "vaultRef"]
  },
  "sortOrder": {
    "type": "string",
    "default": "desc",
    "enum": ["asc", "desc"]
  }
}
```

## Testing

### Manual Testing Checklist

- [ ] Cell appears in AddCellModal
- [ ] Unlock modal opens and accepts password
- [ ] Invalid password shows error
- [ ] Token list loads after unlock
- [ ] Add token form validates input
- [ ] New token appears in list after save
- [ ] View token shows decrypted value
- [ ] Delete token removes from list
- [ ] Vault auto-locks after 5 minutes
- [ ] Lock button immediately locks vault
- [ ] Filter and sort controls work correctly
- [ ] Dark mode renders correctly
- [ ] i18n translations work (en-US and pt-BR)

### Unit Tests

TODO: Add unit tests in `frontend/tests/`

- VaultUnlockModal component tests
- VaultTokenList component tests
- VaultTokenForm component tests
- View.vue integration tests

## Future Enhancements

1. **Secure Token View Modal**: Replace alert() with dedicated modal for viewing decrypted tokens
2. **Token Export**: Encrypted export/import functionality
3. **Token History**: Track token usage and access history
4. **Bulk Operations**: Add/delete multiple tokens at once
5. **Search**: Search tokens by name or provider
6. **Token Rotation**: Automated token rotation reminders
7. **Two-Factor Auth**: Optional 2FA for vault unlock

## Related Documentation

- [Wasm Sidecar Phase 2 - Vault Implementation](../../../docs/issues/wasm-sidecar-phase-2-vault/README.md)
- [Cell Type Architecture](../../../docs/official/backend/architecture/cell-type-symlink-architecture.md)
- [Dynamic Layout Architecture](../../../docs/official/frontend/dynamic-layout-architecture.md)
- [Adding New Cell Types](../../../docs/official/ADDING_NEW_CELL_TYPE.md)

## Changelog

### Version 1.0.0 (2025-12-22)
- Initial implementation
- Secure unlock modal
- Token list with metadata display
- Add token form with validation
- View and delete token functionality
- Filter and sort controls
- i18n support (en-US, pt-BR)
- Dark mode support
- Dynamic layout integration
