# Flows in Detail

## Authorization code + PKCE (with OIDC)

```
1. Client creates: state (random), nonce (random), code_verifier (43-128 chars random), code_challenge = BASE64URL(SHA256(verifier))
2. Redirect browser to /authorize?response_type=code&client_id=...&redirect_uri=<exact>&scope=openid profile orders:read
      &state=...&nonce=...&code_challenge=...&code_challenge_method=S256
3. User authenticates; IdP redirects to redirect_uri?code=...&state=...  (and iss= per RFC 9207)
4. Client checks state matches (and iss), then POST /token: grant_type=authorization_code, code, redirect_uri, code_verifier
      (+ client authentication for confidential clients)
5. Response: access_token, id_token, refresh_token, expires_in
6. Validate id_token: signature (JWKS), iss, aud = client_id, exp, iat, nonce matches, azp if multiple audiences
7. Create the app session from id_token claims (sub + iss as the user key); keep tokens server-side
```
- Store state, nonce and verifier server-side (or in an encrypted, short-lived cookie) bound to the browser.
- Use `sub` + `iss` as the identity key, never email (emails change and can be unverified).

## Backend-for-frontend (BFF) for SPAs

- The BFF (same site as the SPA) runs the code flow as a confidential client, stores tokens, and sets an
  `__Host-session` cookie (HttpOnly, Secure, SameSite=Lax/Strict).
- SPA calls the BFF; the BFF attaches access tokens when proxying to APIs.
- CSRF: SameSite cookies plus a custom header (e.g. `X-CSRF: 1`) required on state-changing requests.
- Result: no tokens in JavaScript, XSS can't exfiltrate them.

## Client credentials

```
POST /token  grant_type=client_credentials&scope=orders:read
Client authentication: private_key_jwt (signed assertion) or mTLS (RFC 8705), better than shared client_secret
```
Cache the token until shortly before expiry (don't request one per call; IdPs rate limit token endpoints).

## Device authorization (RFC 8628)

```
POST /device/code -> device_code, user_code, verification_uri, interval
Show user_code + QR of verification_uri_complete; poll /token with device_code at `interval` (slow_down = back off)
```

## Token exchange (RFC 8693)

API A received a user token for audience A; to call API B on the user's behalf it exchanges it:
`grant_type=urn:ietf:params:oauth:grant-type:token-exchange&subject_token=...&audience=B&scope=...` -> narrow token for B.

## Logout

- RP-initiated: redirect to `end_session_endpoint` with `id_token_hint` and `post_logout_redirect_uri`.
- Back-channel logout: IdP POSTs a logout token to the app; the app ends matching sessions (by `sid`/`sub`).
- Revoke refresh tokens (`/revoke`, RFC 7009) on logout.
