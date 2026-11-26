#!/usr/bin/env python3
"""Decode and audit a JWT (JWS compact form) without trusting it.

Prints the header and claims (times in UTC) and checks them. With --secret, HS256/HS384/HS512 signatures are verified
using the standard library; RS*/ES*/PS*/EdDSA signatures need the issuer's public key and a JOSE library, so they are
reported as not verified here.

Checks:
  JW001 error  alg is 'none' or missing
  JW002 error  no exp claim
  JW003 error  token expired (relative to --now, default current time, with --leeway seconds)
  JW004 error  signature invalid (HMAC, with --secret)
  JW005 warn   lifetime (exp - iat) longer than --max-lifetime seconds (default 3600 for access tokens)
  JW006 warn   no aud claim, or aud doesn't include --audience
  JW007 warn   no iss claim, or iss differs from --issuer
  JW008 warn   asymmetric alg without kid (key rotation needs kid)
  JW009 warn   sensitive-looking claims (password, secret, ssn, card numbers) in the payload: JWTs are readable by anyone
  JW010 warn   iat or nbf in the future beyond leeway (clock skew or forged)
  JW011 warn   token larger than --max-bytes (default 2048): sent on every request
  JW012 info   HMAC alg: every verifier holds the signing secret
  JW013 info   typ is not "at+jwt" (RFC 9068 access token profile)

Usage:
    python jwt_inspect.py TOKEN_OR_FILE [--secret S] [--audience A] [--issuer I] [--now 1767225600] [--json]
    echo "$TOKEN" | python jwt_inspect.py -

Exit codes: 0 no errors or warnings, 1 errors or warnings, 2 not a JWT.
"""

import argparse
import base64
import datetime
import hashlib
import hmac
import json
import os
import re
import sys
import time

SENSITIVE = re.compile(r"pass(word)?|secret|ssn|social_?security|credit_?card|card_?number|cvv|private_?key", re.I)
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def b64d(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def utc(ts):
    try:
        return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (TypeError, ValueError, OverflowError, OSError):
        return "invalid"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("token", help="the JWT, a file containing it, or - for stdin")
    ap.add_argument("--secret", help="HMAC secret to verify HS* signatures")
    ap.add_argument("--audience")
    ap.add_argument("--issuer")
    ap.add_argument("--now", type=int, help="current time as a Unix timestamp (default: now)")
    ap.add_argument("--leeway", type=int, default=60, help="clock skew allowance in seconds (default 60)")
    ap.add_argument("--max-lifetime", type=int, default=3600, help="warn above this lifetime in seconds (default 3600)")
    ap.add_argument("--max-bytes", type=int, default=2048, help="warn above this token size (default 2048)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    raw = sys.stdin.read() if a.token == "-" else (open(a.token).read() if os.path.isfile(a.token) else a.token)
    token = raw.strip().removeprefix("Bearer ").strip()
    parts = token.split(".")
    try:
        if len(parts) != 3:
            raise ValueError("expected 3 dot-separated parts (JWS compact); JWE (5 parts) is encrypted and can't be inspected")
        header, claims = json.loads(b64d(parts[0])), json.loads(b64d(parts[1]))
        if not isinstance(header, dict) or not isinstance(claims, dict):
            raise ValueError("header and payload must be JSON objects")
    except (ValueError, json.JSONDecodeError, base64.binascii.Error) as e:
        print(f"error: not a JWT: {e}", file=sys.stderr)
        return 2

    now = a.now if a.now is not None else int(time.time())
    found = []
    add = lambda code, sev, msg: found.append({"code": code, "severity": sev, "message": msg})
    alg = str(header.get("alg", ""))
    if alg.lower() in ("", "none"):
        add("JW001", "error", f"alg is '{alg or 'missing'}': unsigned tokens must always be rejected")
    exp, iat, nbf = claims.get("exp"), claims.get("iat"), claims.get("nbf")
    if exp is None:
        add("JW002", "error", "no exp: the token never expires")
    elif isinstance(exp, (int, float)) and now > exp + a.leeway:
        add("JW003", "error", f"expired at {utc(exp)} ({now - int(exp)} s ago)")
    if a.secret is not None:
        algs = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}
        if alg in algs:
            mac = hmac.new(a.secret.encode(), f"{parts[0]}.{parts[1]}".encode(), algs[alg]).digest()
            try:
                ok = hmac.compare_digest(mac, b64d(parts[2]))
            except (ValueError, base64.binascii.Error):
                ok = False
            if not ok:
                add("JW004", "error", f"{alg} signature does not verify with the given secret")
        else:
            add("JW004", "error", f"--secret given but alg is {alg}: refuse tokens whose alg doesn't match the expected key type")
    if isinstance(exp, (int, float)) and isinstance(iat, (int, float)) and exp - iat > a.max_lifetime:
        add("JW005", "warn", f"lifetime {int(exp - iat)} s exceeds {a.max_lifetime} s: use short access tokens plus refresh tokens")
    aud = claims.get("aud")
    auds = aud if isinstance(aud, list) else [aud] if aud else []
    if not auds:
        add("JW006", "warn", "no aud: a token for one API can be replayed against another")
    elif a.audience and a.audience not in auds:
        add("JW006", "warn", f"aud {auds} doesn't include {a.audience}")
    if not claims.get("iss"):
        add("JW007", "warn", "no iss: verifiers can't pin the issuer")
    elif a.issuer and claims["iss"] != a.issuer:
        add("JW007", "warn", f"iss {claims['iss']} differs from expected {a.issuer}")
    if alg[:2] in ("RS", "ES", "PS", "Ed") and not header.get("kid"):
        add("JW008", "warn", "asymmetric alg without kid: verifiers can't select keys during rotation")
    for k, v in claims.items():
        if SENSITIVE.search(k) or (isinstance(v, str) and CARD.search(v)):
            add("JW009", "warn", f"claim '{k}' looks sensitive; JWT payloads are only base64-encoded, not encrypted")
    for name, v in (("iat", iat), ("nbf", nbf)):
        if isinstance(v, (int, float)) and v > now + a.leeway:
            add("JW010", "warn", f"{name} {utc(v)} is in the future")
    size = len(token.encode())
    if size > a.max_bytes:
        add("JW011", "warn", f"token is {size} bytes: sent on every request (at 1M req/s that's {size * 8 / 1e3:.0f} Gbit/s of headers)")
    if alg.startswith("HS"):
        add("JW012", "info", "HMAC alg: every service that verifies can also mint tokens; prefer RS256/ES256/EdDSA across services")
    if str(header.get("typ", "")).lower() not in ("at+jwt", "application/at+jwt"):
        add("JW013", "info", f"typ is '{header.get('typ', 'missing')}', not 'at+jwt' (RFC 9068); typ helps prevent token confusion")

    times = {k: utc(claims[k]) for k in ("iat", "nbf", "exp") if k in claims}
    if a.json:
        print(json.dumps({"header": header, "claims": claims, "times": times, "bytes": size,
                          "signature_verified": a.secret is not None and alg.startswith("HS") and not any(f["code"] == "JW004" for f in found),
                          "findings": found}, indent=2))
    else:
        print("header:", json.dumps(header))
        print("claims:", json.dumps(claims))
        for k, v in times.items():
            print(f"{k}: {v}")
        print(f"size: {size} bytes; signature: " + ("verified" if a.secret is not None and alg.startswith("HS") and not any(f["code"] == "JW004" for f in found)
                                                  else "INVALID" if any(f["code"] == "JW004" for f in found) else "not verified (needs key)"))
        print()
        for f in sorted(found, key=lambda f: ({"error": 0, "warn": 1, "info": 2}[f["severity"]], f["code"])):
            print(f"{f['code']} [{f['severity']}] {f['message']}")
    return 1 if any(f["severity"] in ("error", "warn") for f in found) else 0


if __name__ == "__main__":
    sys.exit(main())
