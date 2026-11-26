---
name: jwt-auth-flow-implementer
description: "Implement JWT-based authentication correctly and at scale: when JWTs fit (stateless verification across many services) and when opaque tokens or sessions are better, short-lived access tokens with rotating refresh tokens and reuse detection, signing with RS256/ES256/EdDSA and published JWKS with kid-based key rotation, strict verification (algorithm allow-list, iss, aud, exp, nbf, typ, clock leeway), claims design and size budgets, token storage per client type (backend-for-frontend with HttpOnly cookies for browsers, secure storage on mobile), revocation (short TTLs, deny lists, token versions), logout, and the attacks to prevent. Ships jwt_inspect.py, which decodes a token, prints claims with UTC times, verifies HS256/384/512 signatures with the standard library and flags alg none, expiry problems, missing aud/iss/kid, sensitive claims and oversized tokens. Use when building or reviewing JWT authentication or debugging token problems."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# JWT Auth Flow Implementer

JWTs let every service verify a request locally, with no call to an auth server. At a million requests per second, that
property is why they're used. The same property makes mistakes expensive: a token can't be "logged out" before it
expires, a verifier that trusts the token's own `alg` header can be tricked, and a 3 KB token costs 24 Gbit/s of headers
at that rate. This skill designs the flow (short access tokens, rotating refresh tokens, asymmetric keys with JWKS),
implements strict verification, and audits real tokens with `scripts/jwt_inspect.py`.

## Trigger Conditions

Activate this skill when the user:
- Implements login, access and refresh tokens, or service-to-service tokens with JWTs
- Verifies JWTs from an identity provider (Auth0, Okta, Cognito, Entra ID, Keycloak)
- Debugs "invalid token" errors, clock skew or key rotation problems
- Reviews JWT security or decides between JWTs, opaque tokens and sessions

OAuth2/OIDC flows: `oauth2-oidc-integration-guide`. Browser sessions and cookies: `session-cookie-security-configurator`.
Permissions: `rbac-permission-model-designer`.

## Workflow

```
1. DECIDE    -> JWT vs opaque token vs session for each client (references/token-flows.md)
2. ISSUE     -> access token 5-15 min, refresh token rotated on use; claims minimal (sub, iss, aud, exp, iat, jti, scope)
3. SIGN      -> ES256/EdDSA or RS256 with kid; private key in KMS/HSM; JWKS endpoint; rotation schedule
4. VERIFY    -> library with explicit algorithm allow-list, iss, aud, exp/nbf with small leeway (references/verification.md)
5. STORE     -> browser: BFF + HttpOnly cookie (no tokens in localStorage); mobile: Keychain/Keystore
6. REVOKE    -> refresh-token revocation and reuse detection; deny list by jti for emergencies
7. INSPECT   -> python scripts/jwt_inspect.py token.txt --audience api --issuer https://auth... [--secret]
```

## Rules

| Rule | Why |
|------|-----|
| Verifier decides the algorithm, never the token header | Prevents `alg: none` and RS/HS confusion |
| Always check iss and aud (and typ for access tokens) | Tokens for another API or tenant are rejected |
| Short access-token lifetime; rotate refresh tokens | Limits damage from leaks without per-request lookups |
| Asymmetric signing across services; private keys never leave the issuer | Verifiers can't mint tokens |
| Cache JWKS with TTL; refetch on unknown kid with rate limit | Local verification at scale and smooth rotation |
| Minimal claims; no personal or secret data | Payloads are readable; size is paid on every request |
| Leeway of a few seconds to a minute | Clock skew without accepting long-expired tokens |

## Inspection Codes (jwt_inspect.py)

| Code | Severity | Problem |
|------|----------|---------|
| JW001 | error | alg none or missing |
| JW002 | error | No exp |
| JW003 | error | Expired |
| JW004 | error | HMAC signature invalid (with --secret) |
| JW005 | warn | Lifetime too long |
| JW006 | warn | aud missing or wrong |
| JW007 | warn | iss missing or wrong |
| JW008 | warn | Asymmetric alg without kid |
| JW009 | warn | Sensitive claims in payload |
| JW010 | warn | iat/nbf in the future |
| JW011 | warn | Token too large |
| JW012 | info | HMAC alg (shared secret) |
| JW013 | info | typ not at+jwt |

## Scripts

```bash
python scripts/jwt_inspect.py TOKEN_OR_FILE [--secret S] [--audience A] [--issuer I] [--now TS] [--leeway 60] [--max-lifetime 3600] [--json]
```
Never paste production tokens into shared tools; this runs locally. Asymmetric signatures aren't verified (needs the
issuer's public key and a JOSE library). Exit codes: 0 clean, 1 errors or warnings, 2 not a JWT.

## Output

Token flow design, claims schema, signing and rotation plan, verification code for the user's stack, storage per client,
revocation approach, and inspection findings.

## Additional Resources

| File | Content |
|------|---------|
| [token-flows.md](references/token-flows.md) | JWT vs opaque vs session, access/refresh with rotation and reuse detection, storage, revocation, logout, service tokens |
| [verification.md](references/verification.md) | Verification code per language, JWKS caching and rotation, attacks and defences, performance at scale |
