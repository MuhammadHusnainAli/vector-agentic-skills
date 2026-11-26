# Token Flows

## JWT vs opaque token vs session

| Option | Verification | Revocation | Fits |
|--------|--------------|------------|------|
| JWT access token | Local signature check (no network) | Only by expiry (or deny list) | Many services, high RPS, gateways |
| Opaque token | Introspection call or cache lookup | Immediate | Few services, strong revocation needs, third-party tokens you don't want readable |
| Server session (cookie) | Session store lookup | Immediate | Browser apps with one backend or a BFF |
| Phantom token | Gateway exchanges opaque external token for an internal JWT | Immediate at the edge, local inside | Public APIs that need revocation + internal scale |

## Access and refresh tokens

```
login -> access token (JWT, 5-15 min) + refresh token (opaque, random, stored hashed server-side, 7-30 days)
API calls -> Authorization: Bearer <access token>
access expired -> POST /token (grant_type=refresh_token) -> new access token + NEW refresh token; old one invalidated
```
- **Rotation with reuse detection**: if an already-used refresh token is presented, someone copied it: revoke the whole
  token family (all descendants) and force re-login.
- Bind refresh tokens to the client (client ID, device ID); for public clients consider DPoP (RFC 9449) sender
  constraining.
- Absolute session lifetime (e.g. 30-90 days) regardless of rotation.

## Claims

| Claim | Use |
|-------|-----|
| `iss` | Issuer URL; verifier pins it |
| `sub` | Stable user/service ID (not email) |
| `aud` | Target API(s); verifier requires its own |
| `exp`, `iat`, `nbf` | Times (seconds since epoch) |
| `jti` | Unique ID for deny lists and replay detection |
| `scope` / `scp` | Granted scopes |
| `tenant` / `org` | Tenant for multi-tenant authorisation |
| `azp` / `client_id` | Client that requested it |

Keep permissions coarse in the token (scopes, roles); fine-grained authorisation happens at the resource (see
rbac-permission-model-designer). Large group lists belong in a lookup, not the token.

## Storage

| Client | Store | Avoid |
|--------|-------|-------|
| Browser SPA | Backend-for-frontend holds tokens; browser gets an HttpOnly, Secure, SameSite cookie session | localStorage/sessionStorage (any XSS steals tokens) |
| Server-rendered web | Server session | Tokens in the browser |
| Mobile | Keychain (iOS) / Keystore-backed EncryptedSharedPreferences (Android) | Plain preferences, logs |
| Service-to-service | Client credentials, short-lived tokens cached in memory until near expiry; or mTLS + workload identity (SPIFFE) | Long-lived static tokens |

## Revocation and logout

- Logout: revoke the refresh token (and session); access tokens expire soon (that's the trade-off).
- Emergency revocation: deny list of `jti` (or `sub` + `iat` cut-off "tokens issued before T are invalid") in a fast
  store (Redis, in-memory replicated); check only at gateways to keep cost low.
- Token version: store `token_version` per user; include it in tokens; bump on password change; verifiers with a cache of
  versions reject older tokens.
