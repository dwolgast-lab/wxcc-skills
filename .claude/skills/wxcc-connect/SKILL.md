---
name: wxcc-connect
description: Use when first setting up Webex Contact Center (WxCC) admin access, when adding a new tenant, or when anything fails with "not authenticated", HTTP 401/403, an expired/invalid token, a scope mismatch, or a tool reporting the WRONG ORG. Covers the OAuth Integration, per-tenant profiles, local vs cloud MCP servers, and the browser-session trap.
---

# wxcc-connect — get connected, to the tenant you actually meant

## First: which tenant?

**Every tenant is a separate MCP server.** The tenant is part of the tool name
(`mcp__wxcc-gold__wxcc_list`), so acting on the wrong one requires calling a
differently-named tool. There is deliberately **no "switch tenant" command** — a mutable
current-tenant pointer is how a delete meant for sandbox lands on production.

**If the user has not named a tenant, ask.** The nickname → server map lives in the repo's
CLAUDE.md (gitignored — it names real customers). Never infer a tenant from a name you have
not been told.

**`wxcc_whoami` is the ground truth.** It reports the tenant's *own* name (from
`GET organization/{orgId}`, not a configured label) plus `[PRODUCTION]` or `[trial/sandbox]`.
Run it whenever anything looks off.

## One-time setup

1. **Register an Integration** at developer.webex.com (Manage Apps → Create an Integration):
   - Redirect URI: `http://localhost:8484/callback`
   - Scopes: `cjp:config_read cjp:config cjp:config_write` (read-only? just the first)
   - The authorizing user must be a **CC administrator of that tenant**.
2. **`cp .env.example .env`** and fill in client id/secret and `WXCC_API_BASE`
   (region-specific — only `us1` has ever been exercised here).
3. **`python wxcc.py auth login`**, then **`python wxcc.py auth status`** → expect `valid`
   plus the granted scopes.

## Adding another tenant

```powershell
# 1. Config file - copy the .env, NEVER copy a token file
#    (a copied token is a live credential for the WRONG tenant wearing the RIGHT name)
cp .env .env.<profile>        # set WXCC_API_BASE (region!), WXCC_TENANT_LABEL, WXCC_TENANT_ALIASES

# 2. Authenticate AS THAT TENANT'S ADMIN
$env:WXCC_PROFILE = "<profile>"
python wxcc.py auth login
python wxcc.py auth status    # org_id MUST be unique across profiles
Remove-Item Env:WXCC_PROFILE
```

Then add a server to `.mcp.json` named **the way you talk about the tenant**
(`wxcc-acme`, not `wxcc-org2`), add a row to the alias table, and restart Claude Code.

**`WXCC_PROFILE` picks `.env.<profile>` + `.wxcc/tokens.<profile>.json`.** The profile name
must match the `.env.<profile>` filename exactly — a mismatch makes the server report
`authenticated: false` while looking for a file that does not exist.

PowerShell has **no inline env-var prefix**: `$env:VAR = "x"` on its own line.
`VAR=x cmd` is bash-only.

## ⚠️ The browser-session trap — this has caused three wrong-tenant logins

Authenticating a second profile while your browser still holds a Webex session **silently
mints a token for the FIRST tenant — and it looks like it worked.** `wxcc.py` sends
`prompt=login`, but **that is not enough**; the browser hands back whoever it already knows.

**What actually works:**

- **Local:** `python wxcc.py auth login` prints the authorize URL. Paste it into a
  **private/incognito window you opened yourself**, or sign out of Webex first.
- **Cloud:** `claude mcp login <server> --no-browser` — it prints the URL instead of opening
  one. Paste it into a private window, then paste the redirect URL back.
- **Never rely on remembering to use incognito.** A rule that has failed three times is not
  a control.

**Local detection (automatic):** two profiles resolving to the same `org_id` is almost
always this mistake. `auth login` now **refuses** it (exit 3), `auth status` warns loudly,
and `wxcc_whoami` returns `WRONG_TENANT_WARNING`.

**The cloud server cannot do this** — it is stateless and sees one token at a time. There,
the only check is reading the org name back from `wxcc_whoami`. Do it.

## Local vs cloud servers

| | Local (stdio) | Cloud (Cloud Run) |
|---|---|---|
| Config | `.env.<profile>` + local token store | none — the caller's token decides the org |
| Auth | `python wxcc.py auth login` | `claude mcp login <server> --no-browser` |
| Wrong-tenant detection | Yes, cross-profile | **No** — stateless |
| Needs repo + Python | Yes | No |

Both expose the same tools. The cloud server holds **zero** Webex credentials.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `authenticated: false` on a server that used to work | Profile name ≠ `.env.<profile>` filename, or the token was cleared. Check `auth status` for that profile. |
| **403 on a write, 200 on reads** | Token lacks `cjp:config_write`. Re-consent with the wider scope: `auth logout` then `auth login`. Scopes on the *app* are not on the *token* until re-consent. |
| 401 everywhere | Token expired past its refresh window (~14d access / ~90d rolling refresh) → `auth login`. |
| `wxcc_whoami` shows an unexpected org | **Stop.** Wrong-tenant login. `auth logout` that profile (or `claude mcp logout <server>`) and redo it in a private window. |
| `.mcp.json` server "awaiting approval" | Run `claude` interactively in the repo and approve. Renaming a server invalidates its prior approval. |
| Server missing entirely (Windows) | Drive-letter case: `--scope local` keys to the cwd's case, so `C:\` and `c:\` are two records. Use `--scope project` / `.mcp.json`. |
| `Invalid Host header` from the cloud server | Its host is not in the SDK's DNS-rebinding allowlist — a deploy config issue, not auth. |

## Provenance and maintenance

OAuth endpoints, the ~14d/~90d token lifetimes, and the scope names were confirmed live
(2026-07-10/11). The `oauth.scopes` override, per-server-name token isolation, and the
cloud auth chain were verified end-to-end 2026-07-14/16 against three tenants. The
browser-session trap is documented from three real occurrences, not theory.
