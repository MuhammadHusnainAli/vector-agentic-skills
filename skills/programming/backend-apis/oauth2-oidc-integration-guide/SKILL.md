---
name: oauth2-oidc-integration-guide
description: "Integrate OAuth 2.x and OpenID Connect correctly, following the OAuth 2.0 Security Best Current Practice (RFC 9700) and OAuth 2.1: choosing the flow per client (authorization code with PKCE for web, mobile and SPAs via a backend-for-frontend, client credentials for services, device authorization for TVs and CLIs, token exchange for delegation), why implicit and password grants are out, state, nonce and exact redirect URI matching, ID token vs access token, discovery and JWKS, scopes and consent design, refresh token rotation, logout (RP-initiated, back-channel), Pushed Authorization Requests, DPoP and mTLS sender-constrained tokens, multi-tenant and B2B setups, and provider specifics (Auth0, Okta, Entra ID, Cognito, Keycloak, Google). Reviews integrations for missing PKCE or state, leaked tokens, wildcard redirects and unvalidated audiences. Use when adding login, SSO, API authorization or machine-to-machine auth with an identity provider."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# OAuth2 / OIDC Integration Guide

OAuth 2.0 is a framework with many options, and most integration bugs come from picking the wrong ones. That means the
implicit flow in a SPA, an ID token sent to an API, a redirect URI matched by prefix, or a missing `state`. The current
security BCP (RFC 9700) and OAuth 2.1 narrow the choices to a few safe patterns. This skill picks the flow per client,
wires it to the identity provider, and reviews existing integrations against the BCP.

## Trigger Conditions

Activate this skill when the user:
- Adds "Sign in with ..." / SSO, or connects an app to Auth0, Okta, Entra ID, Cognito, Keycloak or Google
- Secures an API with OAuth access tokens, or sets up machine-to-machine auth
- Builds auth for a SPA, mobile app, TV app or CLI
- Reviews an OAuth/OIDC integration for security

Token verification and lifetimes: `jwt-auth-flow-implementer`. Cookies for the BFF session:
`session-cookie-security-configurator`. API keys for developers: `api-key-management-designer`.

## Flow per Client

| Client | Flow | Notes |
|--------|------|-------|
| Server-rendered web app | Authorization code + PKCE (confidential client) | Tokens stay on the server; session cookie to the browser |
| SPA | Authorization code + PKCE via a backend-for-frontend (BFF) | BFF is the OAuth client; browser gets an HttpOnly cookie |
| SPA without backend (only if unavoidable) | Authorization code + PKCE in the browser, refresh token rotation, short lifetimes | Tokens in memory, never localStorage |
| Mobile / desktop | Authorization code + PKCE with the system browser (AppAuth) | Claimed HTTPS redirect (universal/app links) |
| Service to service | Client credentials (private_key_jwt or mTLS client auth) | Or workload identity federation |
| TV, console, CLI | Device authorization grant (RFC 8628) | User approves on another device |
| API calling another API on behalf of a user | Token exchange (RFC 8693) | Narrow audience and scopes |
| Never | Implicit, resource owner password credentials | Removed in OAuth 2.1 |

## Workflow

```
1. CLIENTS   -> list clients and pick flows (table above)
2. PROVIDER  -> register clients: exact redirect URIs, allowed grants, token lifetimes (references/provider-setup.md)
3. SCOPES    -> design API scopes (resource:action) and audiences per API
4. LOGIN     -> authorization code + PKCE with state and nonce; validate ID token (references/flows-in-detail.md)
5. API       -> resource servers validate access tokens (iss, aud, exp, scope); never accept ID tokens
6. SESSION   -> BFF/server session; refresh rotation; logout (RP-initiated + back-channel)
7. HARDEN    -> PAR, DPoP or mTLS where risk warrants; review checklist below
```

## Review Codes

| Code | Severity | Check |
|------|----------|-------|
| OA001 | high | Implicit or password grant in use |
| OA002 | high | Authorization code flow without PKCE, or without state (CSRF) |
| OA003 | high | Redirect URIs with wildcards or prefix matching |
| OA004 | high | Access or refresh tokens in URLs, logs or browser localStorage |
| OA005 | high | API accepts ID tokens, or doesn't check aud/iss |
| OA006 | medium | ID token not validated (signature, iss, aud, exp, nonce) |
| OA007 | medium | Over-broad scopes (`*`, `admin`) requested by default |
| OA008 | medium | No logout propagation (sessions remain after IdP logout) |
| OA009 | medium | Client secrets in mobile apps or SPAs |
| OA010 | low | No refresh token rotation or absolute session lifetime |

## Output

Flow choice per client with sequence diagrams, provider configuration, scope design, code for the stack (library choice
and setup), token handling and logout, and review findings.

## Additional Resources

| File | Content |
|------|---------|
| [flows-in-detail.md](references/flows-in-detail.md) | Authorization code + PKCE step by step, ID token validation, BFF pattern, client credentials, device flow, token exchange, logout |
| [provider-setup.md](references/provider-setup.md) | Scopes and audiences, provider specifics, PAR, DPoP, mTLS, multi-tenant B2B, libraries per language |
