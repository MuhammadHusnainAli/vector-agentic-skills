# Verification

## Code

**Node (jose)**
```ts
import { createRemoteJWKSet, jwtVerify } from "jose";
const JWKS = createRemoteJWKSet(new URL("https://auth.example.com/.well-known/jwks.json"), { cooldownDuration: 30_000 });
export async function verify(token: string) {
  const { payload } = await jwtVerify(token, JWKS, {
    algorithms: ["ES256"], issuer: "https://auth.example.com", audience: "orders-api",
    typ: "at+jwt", clockTolerance: 30, maxTokenAge: "15m",
  });
  return payload;
}
```

**Python (PyJWT)**
```python
jwks = jwt.PyJWKClient("https://auth.example.com/.well-known/jwks.json", cache_keys=True, lifespan=300)
def verify(token: str) -> dict:
    key = jwks.get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=["ES256"], audience="orders-api", issuer="https://auth.example.com",
                      leeway=30, options={"require": ["exp", "iat", "iss", "aud", "sub"]})
```

**Go (golang-jwt + keyfunc)**
```go
k, _ := keyfunc.NewDefaultCtx(ctx, []string{"https://auth.example.com/.well-known/jwks.json"})
tok, err := jwt.Parse(raw, k.Keyfunc, jwt.WithValidMethods([]string{"ES256"}),
    jwt.WithIssuer("https://auth.example.com"), jwt.WithAudience("orders-api"), jwt.WithLeeway(30*time.Second),
    jwt.WithExpirationRequired())
```

**Java (Spring Security resource server)**: `spring.security.oauth2.resourceserver.jwt.issuer-uri` plus a custom
`OAuth2TokenValidator` for audience; JWKS caching is built in.

## JWKS and key rotation

1. Publish the new key in JWKS (with a new `kid`) before using it.
2. Wait at least the verifiers' JWKS cache TTL.
3. Start signing with the new key.
4. Keep the old key in JWKS until all tokens it signed have expired (max token lifetime).
5. Remove the old key.

Verifiers: cache JWKS (minutes), refetch on unknown `kid` with a cooldown so attackers can't force fetch storms.

## Attacks and defences

| Attack | Defence |
|--------|---------|
| `alg: none` | Explicit algorithm allow-list |
| Algorithm confusion (RS256 public key used as HS256 secret) | Allow-list per key type; libraries that bind alg to key |
| `kid` injection (path traversal, SQL) | Treat kid as a lookup key in a fixed JWKS set only |
| `jku` / `x5u` header pointing to attacker keys | Ignore token-supplied key URLs; pin JWKS URL |
| Cross-audience replay | Require `aud` |
| Token from another tenant | Check tenant claim against the resource |
| Stolen bearer token | Short TTL, sender-constrained tokens (DPoP, mTLS), anomaly detection |
| Replay of one-time tokens (password reset, email links) | Single-use `jti` stored until expiry |

## Performance at scale

- ES256/EdDSA verification takes tens of microseconds per token; at 1M rps that's tens of CPU cores fleet-wide: cache
  verified tokens (hash -> claims) for their remaining lifetime at the gateway if CPU matters.
- Verify once at the edge/gateway, forward identity to internal services (signed internal token or mTLS-authenticated
  headers); don't re-verify an external token at every hop.
- Token size: every byte is paid on every request; keep tokens under about 1 KB.
