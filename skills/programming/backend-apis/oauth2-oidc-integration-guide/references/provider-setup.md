# Provider Setup

## Scopes and audiences

- Scopes as `resource:action`: `orders:read`, `orders:write`, `invoices:read`. Few, stable, coarse; fine-grained checks at
  the resource.
- One audience per API (`https://api.example.com/orders` or a logical name); resource servers require it.
- Consent screens for third-party clients list scopes in plain language.
- First-party apps: skip consent, but still request minimal scopes.

## Provider notes

| Provider | Notes |
|----------|-------|
| Auth0 | APIs as "resource servers" with an identifier used as `audience`; RBAC adds `permissions` claim; Actions for custom claims |
| Okta | Custom authorization servers for API access tokens (the org server issues tokens for Okta APIs only) |
| Microsoft Entra ID | v2 endpoint; scopes as `api://<app-id>/orders.read`; `tid` claim for tenant; multi-tenant apps must validate issuer per tenant |
| AWS Cognito | User pools; access tokens lack `aud` (check `client_id`); resource server scopes `<identifier>/<scope>` |
| Keycloak | Realms; audience mappers needed for `aud`; fine-grained authorization services available |
| Google | OIDC for sign-in; for your APIs, issue your own tokens after login |

## Hardening options

| Feature | What | When |
|---------|------|------|
| PAR (RFC 9126) | Push authorization parameters to the IdP first; redirect with a request_uri | High-security apps, FAPI, prevents parameter tampering |
| DPoP (RFC 9449) | Tokens bound to a client key; each request carries a proof | Public clients, stolen-token risk |
| mTLS-bound tokens (RFC 8705) | Tokens bound to client certificate | Service-to-service, financial APIs |
| JAR (RFC 9101) | Signed authorization requests | FAPI |
| Issuer identification (RFC 9207) | `iss` in authorization response | Mix-up attack protection with multiple IdPs |

## Multi-tenant and B2B

- Per-tenant IdP connections (SAML/OIDC enterprise SSO); route login by email domain or tenant subdomain.
- Validate issuer per tenant (Entra ID multi-tenant: `https://login.microsoftonline.com/{tid}/v2.0` pattern, check `tid`
  against allowed tenants).
- Just-in-time user provisioning plus SCIM for lifecycle (deprovisioning).

## Libraries

| Language | Client (login) | Resource server (API) |
|----------|----------------|-----------------------|
| Node | openid-client, Auth.js | jose |
| Python | Authlib | PyJWT / Authlib |
| Java | Spring Security OAuth2 Client | Spring Security Resource Server |
| .NET | Microsoft.Identity.Web / OpenIdConnect middleware | JwtBearer middleware |
| Go | coreos/go-oidc + golang.org/x/oauth2 | go-oidc / golang-jwt + keyfunc |
| Mobile | AppAuth (iOS/Android) | n/a |

Never hand-roll the protocol; configure certified libraries and test the error paths.
