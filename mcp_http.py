#!/usr/bin/env python3
"""HTTP entrypoint for the wxcc MCP server (Cloud Run).

Difference from the stdio server, and the whole point of it: this process holds
NO Webex credentials. Each caller runs their own Webex OAuth flow (Claude Code
does this natively) and their token arrives on the request. The server reads it,
uses it, and forgets it. Nothing is stored.

That kills the token store, the refresh race, the 90-day idle expiry, and the
standing self-renewing org-admin credential that a service-account design would
have parked on the internet.

Consequences worth knowing:
  * The tenant is whatever the CALLER's token says. This process is
    tenant-agnostic - WXCC_PROFILE means nothing here.
  * Region is per-service, not per-caller: WXCC_API_BASE pins the host. Tenants
    in another region need their own service. (All-us1 fleets need only one.)

Local smoke test:
    python mcp_http.py            # http://localhost:8080/mcp
"""
from __future__ import annotations

import os
import sys
import time

import json as _json
from urllib.parse import parse_qs, urlparse

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings

import wxcc
from mcp_server import mcp

# Webex is the authorization server; we are only a resource server.
WEBEX_ISSUER = "https://webexapis.com/v1"

API_BASE = os.environ.get("WXCC_API_BASE", "https://api.wxcc-us1.cisco.com")

# Comma-separated org ids allowed to use this instance. Unset = any valid Webex
# CC token is accepted. That is not a data leak (a token only ever reaches its
# own org) but it does let strangers use your service as a free relay, so set it.
ALLOWED_ORGS = {o.strip() for o in os.environ.get("WXCC_ALLOWED_ORGS", "").split(",") if o.strip()}

# Public URL of this service, needed for the RFC 9728 protected-resource
# metadata that tells a client where to authenticate. Cloud Run knows its own
# URL only at request time, so it must be supplied.
RESOURCE_URL = os.environ.get("WXCC_PUBLIC_URL", "http://localhost:8080")

_TOKEN_TTL = 300          # re-validate a token against the live API this often
_cache: dict[str, tuple[float, AccessToken]] = {}


class WebexTokenVerifier(TokenVerifier):
    """Accept a caller's Webex token only if it really works against WxCC.

    The org id is derived from the token itself, so a caller cannot claim an org
    they do not hold a token for. Verification is a real API call (a 401 here is
    the only proof a token is live), cached briefly so it does not double the
    latency of every request.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        now = time.time()
        hit = _cache.get(token)
        if hit and hit[0] > now:
            return hit[1]

        org = wxcc.extract_org_id(token)
        if not org:
            return None
        if ALLOWED_ORGS and org not in ALLOWED_ORGS:
            print(f"reject: org {org} not in WXCC_ALLOWED_ORGS", file=sys.stderr)
            return None

        # Prove the token is live and CC-scoped. Cheapest authenticated read.
        client = wxcc.WxccClient(API_BASE, token, org)
        try:
            status, _ = client.request("GET", f"organization/{org}/v2/site?pageSize=1")
        except Exception as exc:
            print(f"reject: token check failed: {exc}", file=sys.stderr)
            return None
        if status >= 400:
            print(f"reject: token check returned HTTP {status}", file=sys.stderr)
            return None

        access = AccessToken(
            token=token,
            client_id=org,          # the org IS the caller's identity here
            scopes=["cjp:config_read"],
            expires_at=None,
        )
        _cache[token] = (now + _TOKEN_TTL, access)
        if len(_cache) > 256:       # bound it; this is a cache, not a store
            for k in [k for k, (exp, _) in _cache.items() if exp <= now]:
                _cache.pop(k, None)
        return access


mcp._token_verifier = WebexTokenVerifier()
mcp.settings.auth = AuthSettings(
    issuer_url=WEBEX_ISSUER,
    resource_server_url=RESOURCE_URL,
    required_scopes=None,
)

# The SDK rejects any Host it was not told to expect (DNS-rebinding defence, on
# by default with an empty allowlist - which is why a fresh deploy answers
# "Invalid Host header"). Name the real host rather than switching the check off:
# it stops a malicious page from driving this server through someone's browser.
_parsed = urlparse(RESOURCE_URL)
_host = _parsed.hostname
_allowed = {_host, f"{_host}:443"}
if _parsed.port:                     # a non-default port must be named explicitly,
    _allowed.add(f"{_host}:{_parsed.port}")   # or local runs answer 421
mcp.settings.transport_security = TransportSecuritySettings(
    allowed_hosts=sorted(h for h in _allowed if h),
    allowed_origins=[RESOURCE_URL],
)
mcp.settings.stateless_http = True   # Cloud Run may route a follow-up anywhere
mcp.settings.host = "0.0.0.0"
mcp.settings.port = int(os.environ.get("PORT", 8080))

class ExpectedOrgGuard:
    """Refuse a token whose org is not the one this client says it expects.

    Locally, `wxcc.py` catches a wrong-tenant login by comparing profiles. This
    server is stateless and sees one token at a time, so it cannot. That gap is
    not theoretical: a browser silently reusing a Webex session has produced a
    wrong-tenant login three times, once leaving a server NAMED sandbox holding a
    PRODUCTION token.

    So the client declares the org it believes it is talking to, and a mismatch is
    rejected here - before any tool runs, on every request, whether or not anyone
    remembered to check. Declare it either way:

        url:    https://<service>/mcp?org=<org id>          (always works)
        header: X-WXCC-Expected-Org: <org id>               (needs headers+oauth
                                                             to coexist in .mcp.json)

    Declaring nothing keeps the old behaviour: allowed, unguarded. The org is read
    from the token itself, so a caller cannot assert an org they lack a token for.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                   for k, v in scope.get("headers") or []}
        expected = headers.get("x-wxcc-expected-org")
        if not expected:
            qs = parse_qs(scope.get("query_string", b"").decode("latin-1"))
            expected = (qs.get("org") or [None])[0]
        if not expected:
            return await self.app(scope, receive, send)

        auth = headers.get("authorization", "")
        token = auth.split(None, 1)[1] if " " in auth else ""
        actual = wxcc.extract_org_id(token) if token else None

        if actual and actual != expected:
            print(f"REJECT wrong tenant: token org {actual} != expected {expected}",
                  file=sys.stderr)
            body = _json.dumps({
                "error": "wrong_tenant",
                "error_description":
                    f"This server expects org {expected} but your token is for "
                    f"{actual}. You are signed in to the wrong tenant - almost "
                    f"always a browser reusing an existing Webex session. Run "
                    f"`claude mcp logout <server>` then `claude mcp login <server> "
                    f"--no-browser` and paste the URL into a private window.",
                "expected_org": expected, "token_org": actual,
            }).encode()
            await send({"type": "http.response.start", "status": 403,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})
            return

        return await self.app(scope, receive, send)


app = ExpectedOrgGuard(mcp.streamable_http_app())

if __name__ == "__main__":
    import uvicorn

    print(f"wxcc MCP (http) on :{mcp.settings.port}{mcp.settings.streamable_http_path}",
          file=sys.stderr)
    print(f"  api base     : {API_BASE}", file=sys.stderr)
    print(f"  resource url : {RESOURCE_URL}", file=sys.stderr)
    print(f"  allowed orgs : {ALLOWED_ORGS or 'ANY (set WXCC_ALLOWED_ORGS)'}",
          file=sys.stderr)
    uvicorn.run(app, host=mcp.settings.host, port=mcp.settings.port)
