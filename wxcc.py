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
  post PATH      Authenticated POST with a JSON body (--body).
  put PATH       Authenticated PUT with a JSON body (--body).
  patch PATH     Authenticated PATCH with a JSON body (--body).
  delete PATH    Authenticated DELETE.

--body accepts inline JSON, @path/to/file.json, or - (read stdin).

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
from typing import NoReturn

# --- Confirmed Webex OAuth endpoints (developer.webex.com). Portal move to the
#     converged portal did not change these; webex-cx.com is deprecated. ---
AUTHORIZE_URL = "https://webexapis.com/v1/authorize"
TOKEN_URL = "https://webexapis.com/v1/access_token"

REPO_DIR = Path(__file__).resolve().parent

# --- Multi-tenant: WXCC_PROFILE picks which tenant this process talks to. ---
# Unset          -> .env              + .wxcc/tokens.json          (default tenant)
# WXCC_PROFILE=x -> .env.x            + .wxcc/tokens.x.json
# There is deliberately NO "switch tenant" command: a mutable current-tenant
# pointer is how a delete meant for sandbox lands on production. The tenant is
# chosen by the environment the process starts in, and `auth status` prints it.


def profile() -> str | None:
    return os.environ.get("WXCC_PROFILE") or None


def env_file() -> Path:
    p = profile()
    return REPO_DIR / (f".env.{p}" if p else ".env")


def token_store() -> Path:
    p = profile()
    return REPO_DIR / ".wxcc" / (f"tokens.{p}.json" if p else "tokens.json")

# Refresh a bit before actual expiry to avoid using a token mid-flight.
EXPIRY_SKEW_SECONDS = 300


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    """Environment variables win; `.env` next to this script fills the gaps."""
    cfg: dict[str, str] = {}
    envf = env_file()
    if envf.exists():
        for raw in envf.read_text(encoding="utf-8").splitlines():
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
        "WXCC_TENANT_LABEL",
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
            f"Set them in {env_file().name} or the environment (see .env.example).")


class WxccError(Exception):
    """Any failure a caller should surface: config, auth, or API.

    Raised rather than exiting so this module works as a library (the MCP
    server turns these into tool errors); `main` renders it and sets the code.
    """

    def __init__(self, msg: str, code: int = 1):
        super().__init__(msg)
        self.code = code


def die(msg: str, code: int = 1) -> NoReturn:
    raise WxccError(msg, code)


# --------------------------------------------------------------------------- #
# Token store
# --------------------------------------------------------------------------- #
def load_tokens() -> dict | None:
    store = token_store()
    if not store.exists():
        return None
    return json.loads(store.read_text(encoding="utf-8"))


def save_tokens(tok: dict) -> None:
    store = token_store()
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(tok, indent=2), encoding="utf-8")


def all_profile_orgs() -> dict[str, str]:
    """Map every authenticated profile -> the org its stored token resolves to.

    Two profiles pointing at the same org means one of them authenticated to the
    wrong tenant - almost always because the browser silently reused an existing
    Webex session. Cheap to check, and the only reliable way to catch it.
    """
    out: dict[str, str] = {}
    store_dir = REPO_DIR / ".wxcc"
    if not store_dir.exists():
        return out
    for f in store_dir.glob("tokens*.json"):
        name = "(default)" if f.name == "tokens.json" else f.name[len("tokens."):-len(".json")]
        try:
            tok = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if tok.get("org_id"):
            out[name] = tok["org_id"]
    return out


def warn_on_org_collision(this_profile: str, this_org: str | None) -> bool:
    """Print a loud warning if another profile already resolves to this org."""
    if not this_org:
        return False
    clashes = [p for p, org in all_profile_orgs().items()
               if org == this_org and p != this_profile]
    if not clashes:
        return False
    print("", file=sys.stderr)
    print("  !!  WRONG TENANT?  " + "-" * 52, file=sys.stderr)
    print(f"  !!  Profile '{this_profile}' resolves to org {this_org}", file=sys.stderr)
    print(f"  !!  ...which is ALREADY used by: {', '.join(clashes)}", file=sys.stderr)
    print("  !!", file=sys.stderr)
    print("  !!  Two profiles should never share an org. The browser most likely",
          file=sys.stderr)
    print("  !!  reused an existing Webex session instead of asking you to sign in.",
          file=sys.stderr)
    print("  !!", file=sys.stderr)
    print(f"  !!  Fix: WXCC_PROFILE={this_profile} python wxcc.py auth logout",
          file=sys.stderr)
    print("  !!       then `auth login` again in a PRIVATE browser window,",
          file=sys.stderr)
    print("  !!       signed in as an admin of the tenant you actually want.",
          file=sys.stderr)
    print("  " + "-" * 70, file=sys.stderr)
    return True


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


def multipart_body(parts: list[tuple[str, str | None, str | None, bytes]],
                   boundary: str = "----wxccpy7f3a1c") -> tuple[bytes, str]:
    """Encode multipart/form-data. Parts are (name, filename, content_type, bytes).

    Needed because `audio-file` create/replace accept ONLY multipart - a JSON body
    returns 500 whatever its shape, despite the portal documenting application/json
    as an alternative (verified against the sandbox 2026-07-22). A part's
    content_type is not optional decoration: sending the metadata part without an
    explicit `application/json` returns 415.
    """
    out = b""
    for name, filename, ctype, payload in parts:
        out += f"--{boundary}\r\n".encode()
        disp = f'form-data; name="{name}"'
        if filename:
            disp += f'; filename="{filename}"'
        out += f"Content-Disposition: {disp}\r\n".encode()
        if ctype:
            out += f"Content-Type: {ctype}\r\n".encode()
        out += b"\r\n" + payload + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return out, f"multipart/form-data; boundary={boundary}"


def _request(url: str, token: str, method: str = "GET",
             body: dict | list | None = None,
             raw: tuple[bytes, str] | None = None) -> tuple[int, str]:
    """`raw` is (bytes, content_type) and wins over `body` - for multipart uploads."""
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if raw is not None:
        data, headers["Content-Type"] = raw
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
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


class WxccClient:
    """Authenticated access to one org's WxCC API.

    The token is supplied, not looked up: locally it comes from the token store
    (`client_from_store`), and in a remote MCP server it is the caller's own
    OAuth token, arriving on the request. Nothing here touches disk.
    """

    def __init__(self, api_base: str, token: str, org_id: str | None = None):
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.org_id = org_id or extract_org_id(token)

    def url(self, path: str) -> str:
        if "{orgId}" in path:
            if not self.org_id:
                die("path needs {orgId} but org id is unknown - set WXCC_ORG_ID.")
            path = path.replace("{orgId}", self.org_id)
        return self.api_base + "/" + path.lstrip("/")

    def request(self, method: str, path: str,
                body: dict | list | None = None) -> tuple[int, str]:
        return _request(self.url(path), self.token, method=method, body=body)

    def upload(self, method: str, path: str, field: str, filename: str,
               file_bytes: bytes, file_type: str,
               info_field: str, info: dict) -> tuple[int, object]:
        """Send a file plus a JSON metadata part as multipart/form-data.

        The shape `audio-file` requires: the binary under `field` (with a filename
        and its own content type) and the metadata under `info_field` as an
        explicitly-typed application/json part.
        """
        raw = multipart_body([
            (field, filename, file_type, file_bytes),
            (info_field, None, "application/json", json.dumps(info).encode()),
        ])
        status, text = _request(self.url(path), self.token, method=method, raw=raw)
        if not text:
            return status, None
        try:
            return status, json.loads(text)
        except json.JSONDecodeError:
            return status, text

    def json(self, method: str, path: str,
             body: dict | list | None = None) -> tuple[int, object]:
        """Same as `request`, but parses the body. Non-JSON is returned as text."""
        status, text = self.request(method, path, body)
        if not text:
            return status, None
        try:
            return status, json.loads(text)
        except json.JSONDecodeError:
            return status, text

    def list_all(self, path: str) -> tuple[list, int]:
        """Follow meta.links.next to exhaustion. Returns (records, pages)."""
        records: list = []
        pages = 0
        url = self.url(path)
        while url:
            status, text = _request(url, self.token)
            if status >= 400:
                die(f"request failed on page {pages}: HTTP {status}\n{text}", code=2)
            doc = json.loads(text)
            data = doc.get("data")
            if not isinstance(data, list):
                die("--all requires a paginated list response (meta + data[]); "
                    "got a different shape - retry without --all.")
            records.extend(data)
            pages += 1
            if pages > 500:
                die("--all aborted after 500 pages - raise pageSize or narrow the query.")
            next_link = (doc.get("meta") or {}).get("links", {}).get("next")
            url = self.api_base + next_link if next_link else None
        return records, pages


def client_from_store(cfg: dict) -> WxccClient:
    """Build a client from the locally stored tokens, refreshing if needed."""
    token, tok = valid_access_token(cfg)
    return WxccClient(cfg["WXCC_API_BASE"], token,
                      cfg.get("WXCC_ORG_ID") or tok.get("org_id"))


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
    # Webex may include the granted scopes in the token response; keep them if
    # present so `auth status` can show what the token actually carries.
    if resp.get("scope"):
        tok["granted_scopes"] = resp["scope"]
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

    # Signature matches BaseHTTPRequestHandler.log_message exactly - the base
    # calls it with `format` as a keyword in places, so `*_` is not a drop-in.
    def log_message(self, format, *args):  # silence the default request logging
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
        # Force a fresh sign-in instead of silently reusing whatever Webex
        # session the browser already holds. Without this, authenticating a
        # second profile just re-mints a token for the FIRST tenant, and it
        # looks like it worked. (OIDC prompt=login; ignored if unsupported,
        # which is why the org-collision check below is the real backstop.)
        "prompt": "login",
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
    prof = profile() or "(default)"
    print(f"Authorized. Tokens saved to {token_store()}.")
    print(f"profile: {prof}")
    print(f"org_id: {tok.get('org_id', '(not resolved - set WXCC_ORG_ID)')}")
    if warn_on_org_collision(prof, tok.get("org_id")):
        die("authenticated to a tenant another profile already owns - see above.",
            code=3)


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
    print(f"profile  : {profile() or '(default)'}  [{env_file().name}]")
    print(f"api base : {cfg['WXCC_API_BASE']}")
    print(f"scopes   : {cfg['WXCC_SCOPES']} (configured; requested at next login)")
    if not tok:
        print("status   : NOT authenticated (run `auth login`).")
        return
    if tok.get("granted_scopes"):
        print(f"granted  : {tok['granted_scopes']} (actually on the stored token)")
    remaining = tok.get("expires_at", 0) - int(time.time())
    state = f"valid, ~{remaining // 3600}h left" if remaining > 0 else "EXPIRED (will refresh on next call)"
    print(f"status   : {state}")
    print(f"org_id   : {tok.get('org_id', '(not resolved)')}")
    if cfg.get("WXCC_TENANT_LABEL"):
        print(f"tenant   : {cfg['WXCC_TENANT_LABEL']}")
    warn_on_org_collision(profile() or "(default)", tok.get("org_id"))


def cmd_auth_refresh(cfg: dict) -> None:
    tok = load_tokens() or die("nothing to refresh - run `auth login`.")
    tok = refresh_tokens(cfg, tok)
    print(f"refreshed; ~{(tok['expires_at'] - int(time.time())) // 3600}h left.")


def cmd_auth_logout(_cfg: dict) -> None:
    store = token_store()
    if store.exists():
        store.unlink()
        print(f"deleted {store}.")
    else:
        print("no tokens to delete.")


def cmd_get(cfg: dict, path: str, all_pages: bool = False) -> None:
    client = client_from_store(cfg)

    if not all_pages:
        status, body = client.request("GET", path)
        try:
            print(json.dumps(json.loads(body), indent=2))
        except json.JSONDecodeError:
            print(body)
        if status >= 400:
            die(f"request failed: HTTP {status}", code=2)
        return

    records, pages = client.list_all(path)
    print(json.dumps({"totalRecords": len(records), "pagesFetched": pages,
                      "data": records}, indent=2))


def _parse_body(body_arg: str | None) -> dict | list | None:
    if body_arg is None:
        return None
    if body_arg == "-":
        raw = sys.stdin.read()
    elif body_arg.startswith("@"):
        f = Path(body_arg[1:])
        if not f.exists():
            die(f"body file not found: {f}")
        raw = f.read_text(encoding="utf-8")
    else:
        raw = body_arg
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"--body is not valid JSON: {e}")


def cmd_write(cfg: dict, method: str, path: str, body_arg: str | None) -> None:
    body = _parse_body(body_arg)
    if method in ("POST", "PUT", "PATCH") and body is None:
        die(f"{method} requires --body (inline JSON, @file.json, or - for stdin).")
    client = client_from_store(cfg)
    status, resp_body = client.request(method, path, body)
    print(f"HTTP {status}", file=sys.stderr)
    if resp_body:
        try:
            print(json.dumps(json.loads(resp_body), indent=2))
        except json.JSONDecodeError:
            print(resp_body)
    if status >= 400:
        die(f"request failed: HTTP {status}", code=2)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str]) -> None:
    # __doc__ is None when run under `python -OO`, which strips docstrings.
    parser = argparse.ArgumentParser(prog="wxcc",
                                     description=(__doc__ or "wxcc.py").splitlines()[0])
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

    for verb in ("post", "put", "patch", "delete"):
        p = sub.add_parser(verb, help=f"authenticated {verb.upper()} (supports {{orgId}})")
        p.add_argument("path", help="API path (no leading slash)")
        p.add_argument("--body", default=None,
                       help="JSON body: inline string, @file.json, or - for stdin")

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
    elif args.cmd in ("post", "put", "patch", "delete"):
        cmd_write(cfg, args.cmd.upper(), args.path, args.body)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except WxccError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(e.code)
    except BrokenPipeError:
        # Downstream closed the pipe (e.g. `| head`). Point stdout at devnull
        # so the interpreter's exit-time flush doesn't traceback, exit clean.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        raise SystemExit(0)
