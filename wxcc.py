#!/usr/bin/env python3
"""wxcc.py - thin shared helper for Webex Contact Center admin skills.

Centralizes the things every WxCC skill needs so they don't re-derive them:
OAuth (authorization-code flow, user-context Integration), token storage and
auto-refresh, org-id resolution, and authenticated requests against the
region-specific CC API host.

Stdlib only - no pip install required.

Commands:
  auth login     One-time interactive consent; captures + stores tokens.
  auth status    Show token validity, org id, and configured API host.
  auth refresh   Force an access-token refresh using the stored refresh token.
  auth logout    Delete the stored tokens.
  get PATH       Authenticated GET; substitutes {orgId}; prints JSON.
                 --all follows meta.links.next and combines every page.

Config comes from environment variables, or a `.env` file next to this script.
See .env.example for the full list.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# --- Confirmed Webex OAuth endpoints (developer.webex.com). Portal move to the
#     converged portal did not change these; webex-cx.com is deprecated. ---
AUTHORIZE_URL = "https://webexapis.com/v1/authorize"
TOKEN_URL = "https://webexapis.com/v1/access_token"

REPO_DIR = Path(__file__).resolve().parent
ENV_FILE = REPO_DIR / ".env"
TOKEN_STORE = REPO_DIR / ".wxcc" / "tokens.json"

# Refresh a bit before actual expiry to avoid using a token mid-flight.
EXPIRY_SKEW_SECONDS = 300


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    """Environment variables win; `.env` next to this script fills the gaps."""
    cfg: dict[str, str] = {}
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            cfg[key.strip()] = val.strip()
    for key in (
        "WXCC_CLIENT_ID",
        "WXCC_CLIENT_SECRET",
        "WXCC_REDIRECT_URI",
        "WXCC_SCOPES",
        "WXCC_API_BASE",
        "WXCC_ORG_ID",
    ):
        if os.environ.get(key):
            cfg[key] = os.environ[key]
    cfg.setdefault("WXCC_REDIRECT_URI", "http://localhost:8484/callback")
    cfg.setdefault("WXCC_SCOPES", "cjp:config_read")
    cfg.setdefault("WXCC_API_BASE", "https://api.wxcc-us1.cisco.com")
    return cfg


def require(cfg: dict, *keys: str) -> None:
    missing = [k for k in keys if not cfg.get(k)]
    if missing:
        die(f"Missing required config: {', '.join(missing)}. "
            f"Set them in {ENV_FILE.name} or the environment (see .env.example).")


def die(msg: str, code: int = 1) -> "None":
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


# --------------------------------------------------------------------------- #
# Token store
# --------------------------------------------------------------------------- #
def load_tokens() -> dict | None:
    if not TOKEN_STORE.exists():
        return None
    return json.loads(TOKEN_STORE.read_text(encoding="utf-8"))


def save_tokens(tok: dict) -> None:
    TOKEN_STORE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_STORE.write_text(json.dumps(tok, indent=2), encoding="utf-8")


def extract_org_id(access_token: str) -> str | None:
    """Cisco documents the CC org id as the substring after the token's final
    '_'. UNVERIFIED against a live tenant - WXCC_ORG_ID overrides this."""
    return access_token.rsplit("_", 1)[-1] if "_" in access_token else None


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def _post_form(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        die(f"token endpoint {e.code}: {e.read().decode(errors='replace')}")


def _get(url: str, token: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except urllib.error.URLError as e:
        die(f"connection failed for {url}: {e.reason}")
    except http.client.InvalidURL as e:
        # Typically Git Bash (MSYS) rewriting a leading-slash path into
        # C:/Program Files/Git/... Pass API paths WITHOUT a leading slash.
        die(f"bad URL {url!r}: {e}")


# --------------------------------------------------------------------------- #
# OAuth
# --------------------------------------------------------------------------- #
def _store_token_response(resp: dict) -> dict:
    now = int(time.time())
    tok = {
        "access_token": resp["access_token"],
        "refresh_token": resp.get("refresh_token"),
        "expires_at": now + int(resp.get("expires_in", 0)),
        "obtained_at": now,
    }
    org = load_config().get("WXCC_ORG_ID") or extract_org_id(tok["access_token"])
    if org:
        tok["org_id"] = org
    save_tokens(tok)
    return tok


class _CallbackHandler(BaseHTTPRequestHandler):
    captured: dict = {}

    def do_GET(self):  # noqa: N802
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        _CallbackHandler.captured = {k: v[0] for k, v in params.items()}
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        ok = "code" in _CallbackHandler.captured
        msg = "Authorization complete. You can close this tab." if ok else \
              "Authorization failed. Check the terminal."
        self.wfile.write(f"<html><body><h3>{msg}</h3></body></html>".encode())

    def log_message(self, *_):  # silence the default request logging
        pass


def cmd_auth_login(cfg: dict) -> None:
    require(cfg, "WXCC_CLIENT_ID", "WXCC_CLIENT_SECRET", "WXCC_REDIRECT_URI")
    redirect = urllib.parse.urlparse(cfg["WXCC_REDIRECT_URI"])
    host = redirect.hostname or "localhost"
    port = redirect.port or 8484
    state = f"wxcc{int(time.time())}"

    authorize = AUTHORIZE_URL + "?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": cfg["WXCC_CLIENT_ID"],
        "redirect_uri": cfg["WXCC_REDIRECT_URI"],
        "scope": cfg["WXCC_SCOPES"],
        "state": state,
    })

    server = HTTPServer((host, port), _CallbackHandler)
    print(f"Opening browser for consent. If it doesn't open, visit:\n{authorize}\n")
    webbrowser.open(authorize)
    print(f"Waiting for the redirect on {cfg['WXCC_REDIRECT_URI']} ...")
    server.handle_request()  # blocks until the single callback arrives
    got = _CallbackHandler.captured

    if got.get("state") != state:
        die("state mismatch on callback - aborting for safety.")
    if "code" not in got:
        die(f"no authorization code returned: {got}")

    resp = _post_form(TOKEN_URL, {
        "grant_type": "authorization_code",
        "code": got["code"],
        "client_id": cfg["WXCC_CLIENT_ID"],
        "client_secret": cfg["WXCC_CLIENT_SECRET"],
        "redirect_uri": cfg["WXCC_REDIRECT_URI"],
    })
    tok = _store_token_response(resp)
    print(f"Authorized. Tokens saved to {TOKEN_STORE}.")
    print(f"org_id: {tok.get('org_id', '(not resolved - set WXCC_ORG_ID)')}")


def refresh_tokens(cfg: dict, tok: dict) -> dict:
    require(cfg, "WXCC_CLIENT_ID", "WXCC_CLIENT_SECRET")
    if not tok.get("refresh_token"):
        die("no refresh_token stored - run `auth login` again.")
    resp = _post_form(TOKEN_URL, {
        "grant_type": "refresh_token",
        "refresh_token": tok["refresh_token"],
        "client_id": cfg["WXCC_CLIENT_ID"],
        "client_secret": cfg["WXCC_CLIENT_SECRET"],
    })
    # Webex returns a rolling refresh_token; keep it if present.
    if "refresh_token" not in resp and tok.get("refresh_token"):
        resp["refresh_token"] = tok["refresh_token"]
    return _store_token_response(resp)


def valid_access_token(cfg: dict) -> tuple[str, dict]:
    tok = load_tokens()
    if not tok:
        die("not authenticated - run `python wxcc.py auth login` first.")
    if int(time.time()) >= tok.get("expires_at", 0) - EXPIRY_SKEW_SECONDS:
        tok = refresh_tokens(cfg, tok)
    return tok["access_token"], tok


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_auth_status(cfg: dict) -> None:
    tok = load_tokens()
    print(f"api base : {cfg['WXCC_API_BASE']}")
    print(f"scopes   : {cfg['WXCC_SCOPES']}")
    if not tok:
        print("status   : NOT authenticated (run `auth login`).")
        return
    remaining = tok.get("expires_at", 0) - int(time.time())
    state = f"valid, ~{remaining // 3600}h left" if remaining > 0 else "EXPIRED (will refresh on next call)"
    print(f"status   : {state}")
    print(f"org_id   : {tok.get('org_id', '(not resolved)')}")


def cmd_auth_refresh(cfg: dict) -> None:
    tok = load_tokens() or die("nothing to refresh - run `auth login`.")
    tok = refresh_tokens(cfg, tok)
    print(f"refreshed; ~{(tok['expires_at'] - int(time.time())) // 3600}h left.")


def cmd_auth_logout(_cfg: dict) -> None:
    if TOKEN_STORE.exists():
        TOKEN_STORE.unlink()
        print(f"deleted {TOKEN_STORE}.")
    else:
        print("no tokens to delete.")


def cmd_get(cfg: dict, path: str, all_pages: bool = False) -> None:
    token, tok = valid_access_token(cfg)
    if "{orgId}" in path:
        org = cfg.get("WXCC_ORG_ID") or tok.get("org_id")
        if not org:
            die("path needs {orgId} but org id is unknown - set WXCC_ORG_ID.")
        path = path.replace("{orgId}", org)
    base = cfg["WXCC_API_BASE"].rstrip("/")
    url = base + "/" + path.lstrip("/")

    if not all_pages:
        status, body = _get(url, token)
        try:
            parsed = json.loads(body)
            print(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            print(body)
        if status >= 400:
            die(f"request failed: HTTP {status}", code=2)
        return

    # --all: follow meta.links.next until exhausted; emit one combined document.
    records: list = []
    pages = 0
    while url:
        status, body = _get(url, token)
        if status >= 400:
            print(body, file=sys.stderr)
            die(f"request failed on page {pages}: HTTP {status}", code=2)
        doc = json.loads(body)
        data = doc.get("data")
        if not isinstance(data, list):
            die("--all requires a paginated list response (meta + data[]); "
                "got a different shape - retry without --all.")
        records.extend(data)
        pages += 1
        if pages > 500:
            die("--all aborted after 500 pages - raise pageSize or narrow the query.")
        next_link = (doc.get("meta") or {}).get("links", {}).get("next")
        url = base + next_link if next_link else None
    print(json.dumps({"totalRecords": len(records), "pagesFetched": pages,
                      "data": records}, indent=2))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="wxcc", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_auth = sub.add_parser("auth", help="authentication commands")
    auth_sub = p_auth.add_subparsers(dest="auth_cmd", required=True)
    auth_sub.add_parser("login", help="one-time interactive consent")
    auth_sub.add_parser("status", help="show token/org/host status")
    auth_sub.add_parser("refresh", help="force a token refresh")
    auth_sub.add_parser("logout", help="delete stored tokens")

    p_get = sub.add_parser("get", help="authenticated GET (supports {orgId})")
    p_get.add_argument("path", help="API path, e.g. organization/{orgId}/v2/user "
                                    "(no leading slash - Git Bash mangles it)")
    p_get.add_argument("--all", action="store_true", dest="all_pages",
                       help="follow meta.links.next and combine all pages")

    args = parser.parse_args(argv)
    cfg = load_config()

    if args.cmd == "auth":
        {
            "login": cmd_auth_login,
            "status": cmd_auth_status,
            "refresh": cmd_auth_refresh,
            "logout": cmd_auth_logout,
        }[args.auth_cmd](cfg)
    elif args.cmd == "get":
        cmd_get(cfg, args.path, all_pages=args.all_pages)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except BrokenPipeError:
        # Downstream closed the pipe (e.g. `| head`). Point stdout at devnull
        # so the interpreter's exit-time flush doesn't traceback, exit clean.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        raise SystemExit(0)
