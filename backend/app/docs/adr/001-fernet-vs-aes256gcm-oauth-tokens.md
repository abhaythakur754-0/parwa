# ADR-001: Fernet vs AES-256-GCM for OAuth Token Encryption

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2025-01-15 |
| **Context** | Token encryption for stored OAuth credentials |

## Context

PARWA stores encrypted OAuth access/refresh tokens for third-party AI provider
integrations (Google AI, Cerebras, Groq). These tokens must be encrypted at rest
so a database breach does not compromise user OAuth sessions.

Two symmetric encryption approaches were considered:

1. **Fernet** (cryptography library) — AES-128-CBC with PKCS7 padding, HMAC-SHA256
   authentication, timestamped tokens.
2. **AES-256-GCM** (cryptography library) — 256-bit key, built-in authenticated
   encryption with associated data (AEAD).

## Decision

We chose **Fernet** for encrypting OAuth tokens at rest.

### Rationale

- **Simplicity & safety**: Fernet is an opinionated, URL-safe format that bundles
  encryption, authentication, and a version byte. It eliminates the class of
  mistakes common with raw AES-GCM (nonce reuse, IV management, tag truncation).
- **Built-in timestamp**: Fernet tokens include an embedded creation timestamp,
  enabling expiration checks without separate metadata columns.
- **Proven library**: `cryptography.fernet.Fernet` is maintained by the Python
  Cryptographic Authority and is widely audited.
- **Adequate security**: AES-128-CBC + HMAC-SHA256 provides 128-bit
  confidentiality and 256-bit integrity. NIST guidance confirms AES-128 remains
  secure through at least 2030. The HMAC construction is encrypt-then-MAC,
  avoiding padding-oracle attacks that can affect plain AES-CBC.
- **Operational consistency**: The existing `DATA_ENCRYPTION_KEY` field (32 chars)
  maps cleanly to a Fernet key (base64url-encoded 32 bytes → 256-bit key material:
  128-bit signing key + 128-bit encryption key).

## Consequences

### Positive

- Fewer lines of code and a smaller attack surface versus manual AES-GCM.
- Token tampering is detected by HMAC before any decryption attempt.
- Versioned format allows future algorithm upgrades without schema changes.

### Negative

- AES-128 is weaker than AES-256 against future quantum adversaries (Grover's
  algorithm halves effective key length). This is acceptable given our 2030+
  re-evaluation horizon and the fact that OAuth tokens are short-lived and
  rotatable.
- Fernet tokens are ~84 bytes larger than raw AES-GCM ciphertext (overhead from
  version byte, timestamp, IV, HMAC). Negligible for our token sizes.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **AES-256-GCM** | Requires manual nonce/IV management. Nonce reuse is catastrophic (key compromise). Higher implementation risk for marginal security gain over Fernet. |
| **AES-256-CBC + separate HMAC** | Essentially what Fernet does internally, but would require us to implement the composition correctly (encrypt-then-MAC, constant-time comparison, proper IV handling). |
| **ChaCha20-Poly1305** | Strong AEAD cipher, but not available as a high-level opinionated envelope format in the `cryptography` library. Would require the same manual nonce management as AES-256-GCM. |
| **Envelope encryption via KMS** | Overkill for current scale. Would add latency and cloud-provider lock-in. Can be adopted later if compliance requires it. |
