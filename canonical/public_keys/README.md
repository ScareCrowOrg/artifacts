# PAT Public Keys

This directory holds Ed25519 public keys used to validate Personal Access Tokens (PATs).

## File Naming Convention

Each file is named `{kid}.pub` where `kid` is the Key ID embedded in the JWT header
(format: `YYYY-MM`, e.g. `2026-03.pub`).

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
    kid = key_file.stem  # "2026-03"
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
with open("artifacts/canonical/public_keys/2026-03.pub", "w") as f:
    f.write(public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode())

# Set the private key as an environment variable (NEVER commit)
private_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
print(f"Set CENTRALHUB_PRIVATE_KEY='{private_pem}'")
```
