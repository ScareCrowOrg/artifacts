---
processed: true
processed_date: 2026-07-04
themes:
  - security
  - authentication
  - keys
  - tenant
modules:
  - backend
  - centralhub
  - infrastructure
code_verified: true
dead_docs_found: false
---
# PAT Public Keys

This directory holds Ed25519 public keys used to validate Personal Access Tokens (PATs) and JWTs.

## File Naming Convention

Each file is named `{tenant}-{YYYY-MM}.pub` where:

- `{tenant}` is the environment name (`staging`, `production`)
- `{YYYY-MM}` is the key rotation period (year-month)

**Examples:**
```
staging-2026-03.pub       ← staging environment (March 2026)
production-2026-07.pub    ← production environment (July 2026)
```

The stem of the filename (without `.pub` extension) becomes the `kid` in the JWT header:
- `staging-2026-03.pub` → `kid = "staging-2026-03"`
- `production-2026-07.pub` → `kid = "production-2026-07"`

## Environment Variable: `TENANT_NAME`

The `TENANT_NAME` environment variable determines which public keys are used
when **signing** JWTs:

| Environment | `TENANT_NAME` | Default |
|-------------|---------------|---------|
| Dev / Staging | `staging` | ✅ (default) |
| Production | `production` | Set via `.env.production` |

When `TENANT_NAME` is set, `get_latest_key_id()` filters the `*.pub` files to
only those matching `{TENANT_NAME}-*`. This prevents staging CentralHub from
accidentally signing with a production key ID, and vice versa.

**Verification** (`verify_jwt()`) loads **all** `*.pub` files regardless of
tenant prefix, so tokens from any environment can be verified (useful during
migration and shared-worker scenarios).

## How Keys Are Used

1. **CentralHub** generates an Ed25519 keypair and signs PAT JWTs with the private key.
2. The **private key** is stored as the `CENTRALHUB_PRIVATE_KEY` environment variable — never committed.
3. The **public key** for each key version is placed here for distribution.
4. **Runners / Launchers / Workers** load all `*.pub` files at startup and validate tokens offline.

## Validation Flow

```python
from pathlib import Path
import jwt

public_keys = {}
for key_file in Path("artifacts/canonical/public_keys").glob("*.pub"):
    kid = key_file.stem  # e.g. "staging-2026-03" or "production-2026-07"
    with open(key_file) as f:
        public_keys[kid] = f.read()

# When validating a token:
kid = jwt.get_unverified_header(token)["kid"]
public_key = public_keys[kid]
payload = jwt.decode(token, public_key, algorithms=["EdDSA"])
```

## Key Rotation Policy

- A new keypair is generated each calendar month (YYYY-MM).
- Old public keys are **kept** in this directory for the duration of their tokens' validity.
- New PATs are always signed with the current month's private key.
- Retired private keys are destroyed; their public keys remain here for validation.

## Generating a New Keypair

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)

private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()

# Save public key to this directory (commit to repo)
tenant = "staging"  # or "production"
with open(f"artifacts/canonical/public_keys/{tenant}-2026-03.pub", "w") as f:
    f.write(public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode())

# Set the private key as an environment variable (NEVER commit)
private_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
print(f"Set CENTRALHUB_PRIVATE_KEY='{private_pem}'")
```

## Backward Compatibility

The file `2026-03.pub` (without tenant prefix) is kept as a copy of
`staging-2026-03.pub` for backward compatibility with tokens that were issued
before the tenant-aware naming convention was adopted. It can be removed after
all tokens with `kid=2026-03` have expired (typically 30 days).
