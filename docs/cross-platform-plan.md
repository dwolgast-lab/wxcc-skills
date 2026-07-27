# Plan: running these tools outside Claude Code

Target hosts: **Claude chat** (claude.ai / Claude Desktop connectors), **ChatGPT**
(developer-mode connectors / Apps), **Codex** (CLI and IDE), **Gemini CLI**.

The short version: **the tools already port; the auth does not.** Every one of these hosts
speaks MCP, so `mcp_server.py` needs no rewrite for any of them. What differs is how each
host obtains a Webex token — and two of the four refuse the only way Webex will issue one.

---

## 1. What actually has to move

Three layers, and only the first is hard.

| Layer | What it is | Portability |
|---|---|---|
| **Transport + auth** | Streamable HTTP, OAuth to Webex, the `?org=` tenant guard | **The whole problem.** See §3. |
| **Tool surface** | 18 tools, `ENTITIES`, dry-run/confirm/verify | Already portable. Plain MCP. |
| **Skills** | 30 `SKILL.md` files | Now an open standard. Nearly free. |

**The tool layer is genuinely done.** `mcp_http.py` is a standard Streamable HTTP MCP server
with an RFC 9728 protected-resource document and a bearer-token verifier. Nothing in it is
Claude-specific. `_client()` already takes the token off the request rather than a store, and
`_served_remotely()` already refuses local-file uploads with an accurate reason.

**The skills layer got easy while we weren't looking.** Agent Skills was published as an open
standard (`agentskills.io`) in December 2025; Codex CLI and Gemini CLI both discover
`~/.agents/skills/` and `.agents/skills/`, and claude.ai takes a zip upload. Better still,
our skills are already host-neutral: they call tools by bare name (`wxcc_list`, 81 times),
and only **10 of 30** files mention a Claude-style `mcp__wxcc-<tenant>__` name at all — one
boilerplate sentence each. See §6.

So the plan is: fix auth, harden the write gate, make ten sentences host-neutral.

---

## 2. Step 0 — the one probe that decides everything

**Before writing any code, find out whether Webex publishes OAuth discovery metadata.**
Every downstream decision hangs on it, and it is three commands.

```bash
curl -sS https://webexapis.com/v1/.well-known/openid-configuration          | jq .
curl -sS https://webexapis.com/.well-known/oauth-authorization-server/v1    | jq .
curl -sS https://webexapis.com/v1/.well-known/oauth-authorization-server    | jq .
```

You are looking for a document containing `authorization_endpoint`, and specifically a
`token_endpoint` of `https://webexapis.com/v1/access_token`.

**Why it matters.** `mcp_http.py` advertises Webex itself as the authorization server
(`WEBEX_ISSUER = "https://webexapis.com/v1"`). A spec-compliant MCP client fetches our
`/.well-known/oauth-protected-resource`, follows that pointer to Webex, and asks Webex for
its metadata. If discovery fails, the MCP spec's fallback is `{issuer}/authorize` +
`{issuer}/token` — and `https://webexapis.com/v1/token` **is not** Webex's token endpoint;
`/v1/access_token` is. A client relying on the fallback would authorize successfully and then
fail the code exchange.

The cloud chain is verified working with Claude Code against three tenants (2026-07-14/16),
so *something* resolves correctly today. Confirm which:

- **Metadata is published** → any spec-compliant client can discover Webex unaided. Claude.ai
  and Gemini CLI should work with configuration alone, and the broker in §4 is needed only
  for ChatGPT and Codex.
- **Nothing is published** → Claude Code is compensating with client-side knowledge that
  other hosts won't have. **The broker becomes mandatory for all four hosts**, and it also
  removes a latent fragility in the current Claude Code setup.

Record the answer in this file. It changes the size of the job by roughly half.

---

## 3. Compatibility matrix

Two questions decide each host: can it be *pointed* at a Streamable HTTP MCP server, and can
it be told to use a **pre-registered** OAuth client? Webex only issues credentials through a
manually registered Integration — it supports neither Dynamic Client Registration (RFC 7591)
nor Client ID Metadata Documents.

| Host | Remote MCP | Pre-registered OAuth client | Custom headers | Verdict |
|---|---|---|---|---|
| **Claude Code** (today) | yes | yes — `oauth.clientId` + `--client-secret` | yes | works |
| **Claude chat** (claude.ai / Desktop) | yes, custom connectors | **yes** — Advanced settings → Client ID / Secret | **no** | config only |
| **Gemini CLI** | yes — `httpUrl` | **yes** — full `oauth` block incl. explicit URLs | yes | config only |
| **ChatGPT** (dev mode / Apps) | yes | **no — DCR or CIMD only** | no | **needs broker** |
| **Codex** | yes — `url` | **no for OAuth** (`codex mcp login` wants DCR); yes for static bearer | yes | broker, or bearer |

Sources for the two blockers: openai/codex issues
[#19154](https://github.com/openai/codex/issues/19154) (*"codex mcp login appears to require
dynamic client registration for private OAuth MCP servers; cannot use pre-registered client
identity"*) and [#15818](https://github.com/openai/codex/issues/15818); OpenAI's connector
docs list CIMD, DCR and PKCE as the supported client-registration paths.

**Consequence:** Claude chat and Gemini CLI are configuration exercises. ChatGPT and Codex
need something in front of Webex that speaks DCR. That something is one small service, and
it is the single largest work item in this plan.

---

## 4. Work item A — the OAuth broker (unblocks ChatGPT and Codex)

### What it is

An **authorization-server façade** in front of Webex. It is not a token store, not a proxy
for API traffic, and it never holds a user's credentials.

```
MCP client ──DCR──▶ broker /register        (issues a client_id; all map to ONE Webex Integration)
           ──────▶ broker /authorize  ──▶ webexapis.com/v1/authorize
           ◀────── broker /callback   ◀──  (broker's own registered redirect URI)
           ──PKCE─▶ broker /token     ──▶ webexapis.com/v1/access_token
           ◀────── the Webex token, unmodified
           ──Bearer──▶ mcp_http.py    (unchanged — verifier still sees a real Webex token)
```

### The design property that must not be lost

**The broker hands back Webex's own access token, verbatim.** It mints nothing of its own.
That is what keeps `mcp_http.py` unchanged, keeps `wxcc.extract_org_id` authoritative, and
keeps the `?org=` guard and `WXCC_ALLOWED_ORGS` meaningful. A broker that issued its own
opaque tokens would need a token store — reintroducing exactly the standing self-renewing
org-admin credential the Cloud Run design exists to avoid. Don't.

State the broker actually holds:

- the Webex **client secret** (unavoidable — it performs the confidential-client exchange);
- a registry of DCR-issued `client_id` → `redirect_uri` (small, durable, non-secret);
- auth codes in flight, ~60 seconds each.

The user's **refresh token goes to the MCP client**, not the broker. The broker is stateless
between flows.

### Endpoints

| Endpoint | Does |
|---|---|
| `GET /.well-known/oauth-authorization-server` | RFC 8414 metadata: our own `/authorize`, `/token`, `/register`, plus `scopes_supported` naming the three `cjp:` scopes |
| `POST /register` | RFC 7591. Accept the client's `redirect_uris`, issue a `client_id`. **Validate the redirect URI against an allowlist** — an open registration endpoint that will redirect anywhere is a token-exfiltration primitive |
| `GET /authorize` | Store `(client_id, redirect_uri, state, code_challenge)`, redirect to Webex with the **broker's** redirect URI and `prompt=login` |
| `GET /callback` | Webex's registered redirect URI. Swap Webex's code for a broker code, redirect back to the client's `redirect_uri` |
| `POST /token` | **Terminate PKCE here** (verify `code_verifier` against the stored challenge), then exchange upstream as a confidential client with the Webex secret. Return Webex's token response unchanged |

### Two details that will otherwise cost an afternoon

- **PKCE terminates at the broker.** MCP requires PKCE; Webex's Integration flow is a
  classic confidential-client code exchange. Do not attempt to forward `code_challenge`
  upstream and hope. Verify it locally, use the secret upstream.
- **`resource` (RFC 8707).** MCP clients send a `resource` indicator on `/authorize` and
  `/token`. Webex will not understand it. Consume it at the broker (validate it names our
  service, then drop it) rather than forwarding it.
- **`prompt=login` must survive.** This is the browser-session trap that has caused three
  wrong-tenant logins. `wxcc.py` sends it; the broker must too, on every upstream authorize.

### Deploy

Same shape as the existing service — a second Cloud Run service, or a second route on the
same one. It needs the Webex client secret in Secret Manager; the MCP service still needs
none. Register **one** redirect URI on the Webex Integration: `https://<broker>/callback`.

Then point the resource server at it — one line, env-driven:

```python
# mcp_http.py
WEBEX_ISSUER = os.environ.get("WXCC_ISSUER_URL", "https://webexapis.com/v1")
```

Set `WXCC_ISSUER_URL=https://<broker>` and discovery lands on the broker for every client.
Clients that already work directly against Webex keep working if you leave it unset.

### The alternative, and why not

Hosted MCP auth gateways (Auth0, Stytch, WorkOS, Cequence, Zuplo) do exactly this and are
faster to stand up. They also put a third party in the token path, which contradicts the one
property this repo advertises: *the server holds no credentials at all*. If you take that
trade, take it deliberately and say so in the README — don't let it arrive as a default.

---

## 5. Work item B — make the write gate server-enforced

**This is the part that is genuinely unsafe to port as-is.**

Today `confirm: bool = False` is *advice to the model*. Nothing prevents a model from calling
`wxcc_delete(..., confirm=True)` on the first try without ever showing a dry run. On Claude
Code that is backstopped by the host's per-call approval prompt. Off Claude Code that backstop
varies: claude.ai and ChatGPT prompt per tool call; Gemini CLI prompts unless the server is
configured `trust: true`; **Codex in an auto-approval mode does not prompt at all.**

So a design whose safety currently rests on the host's UI is about to be run on hosts whose UI
we don't control.

**Fix:** make the dry run a precondition the server can check.

1. A `confirm=False` call returns, alongside the existing diff and rollback, a
   `confirm_token` — an HMAC over `(tenant org, tool, entity, id, the exact payload)` with a
   short TTL.
2. A `confirm=True` call requires that token, and recomputes the HMAC over the payload it was
   actually given. A payload that changed after the preview fails.

The model then *cannot* write without having first produced a preview whose contents match
what it is about to send. The human still approves; the difference is that the preview is now
guaranteed to have existed and to describe the real write.

Cost is small — one signing key (per-instance random is fine; a rejected stale token just
means re-previewing), one helper, and a mechanical change at six call sites. It improves
Claude Code too. **Do this before exposing writes on any new host**; until it lands, deploy
new hosts with `cjp:config_read` only.

---

## 6. Work item C — skills

### The good news

Agent Skills is an open standard. The interoperable discovery path is `~/.agents/skills/`
(user) and `.agents/skills/` (workspace), honoured by Claude Code, Codex CLI and Gemini CLI.
So for the three CLI hosts, distribution is a copy:

```bash
mkdir -p ~/.agents/skills
cp -r .claude/skills/wxcc-* ~/.agents/skills/
```

Nothing about the skills' content needs to change for that to work — they already call bare
tool names.

Better: keep one source of truth and publish outward, rather than forking 30 files. Add to
`scripts/`:

```
python scripts/sync_skills.py --target agents   # .claude/skills -> .agents/skills
python scripts/sync_skills.py --target zip      # one .zip per skill, for claude.ai upload
```

### The ten sentences

Ten skills carry a Claude-Code-shaped tool reference:

> Call the **`wxcc_list` / `wxcc_get`** MCP tools on the server for the tenant the user named
> (`mcp__wxcc-<tenant>__wxcc_list`).

Rewrite the parenthetical to name the *concept* rather than Claude's naming convention —
"on the MCP server registered for that tenant" — and the file is host-neutral. The
tenant-selection rule that sentence exists to enforce is unaffected.

Also check `wxcc-connect`, which documents `claude mcp login` and `.mcp.json` throughout. It
should gain a short per-host table rather than be genericised — the traps it describes are
real and host-specific.

### Hosts with no skills mechanism

ChatGPT has no skills; claude.ai has skills but they live in account settings, not the repo.
Three thousand lines of skill won't fit in a Project instruction box.

**Portable answer: serve the skills through MCP itself.** Add one tool:

```python
@mcp.tool()
def wxcc_guide(topic: str = "") -> dict:
    """Procedures, field requirements and known traps for a WxCC entity.
    Call this BEFORE any create/update/delete. topic="" lists available topics."""
```

It reads the same `SKILL.md` files. Every host on this list can call a tool, and only some
can load a skill — so this is the lowest common denominator, and it keeps one source of
truth. Pair it with a router in the server's `instructions` field (already populated with
`_IDENTITY`) listing the topics, so the model knows the tool is worth calling.

MCP *prompts* are the tempting alternative and the wrong one: most hosts surface them as
user-typed slash commands, so the model cannot pull one on its own initiative.

---

## 7. Per-host instructions

Convention below: **[verify]** marks a value to confirm against the live host rather than
trust from this document. Connector UIs and callback URLs change.

### 7.1 Claude chat — claude.ai and Claude Desktop

**Feasible today, config only.** Claude supports DCR *and*, since July 2025, a manually
supplied client ID and secret for servers that don't do DCR — which is exactly our case.

**Server side**

1. Add Claude's connector callback to the Webex Integration's redirect URIs. Expected value
   is `https://claude.ai/api/mcp/auth_callback` **[verify]** — capture the real one from the
   `redirect_uri` parameter on the consent screen, or from Webex's rejection message, which
   names the URI it refused.
2. No code change. The `?org=` guard and `WXCC_ALLOWED_ORGS` work unmodified.

**Client side** — Settings → Connectors → Add custom connector:

| Field | Value |
|---|---|
| Name | the tenant nickname — this is what you'll say out loud |
| URL | `https://<service>/mcp?org=<that tenant's org id>` |
| Advanced → OAuth Client ID | the Integration's client id |
| Advanced → OAuth Client Secret | the Integration's secret |

**One connector per tenant**, same as one MCP server per tenant. Sign in through a
private window — the browser-session trap is identical here.

**Watch for**

- **Custom headers are not supported** ([anthropics/claude-ai-mcp#112](https://github.com/anthropics/claude-ai-mcp/issues/112)),
  so `X-WXCC-Expected-Org` is unavailable. Use the `?org=` query form — which is why
  `ExpectedOrgGuard` accepts both. Confirm the query string survives round-tripping through
  the connector UI **[verify]**; if it is stripped, the guard silently disarms. Test by
  pointing a connector at the *wrong* org id and confirming you get `403 wrong_tenant`.
- **Scopes.** There is no scope field in the connector UI. The client takes scopes from the
  authorization server's metadata, so `scopes_supported` must name
  `cjp:config_read cjp:config cjp:config_write`. If Step 0 finds Webex publishes no metadata,
  this is a second reason the broker becomes mandatory here.
- **Tool naming.** Whether the connector name appears in the tool name is host-controlled
  **[verify]**. If it doesn't, the "tenant is part of the tool name" property degrades — but
  the `?org=` guard is server-side and still hard-fails a wrong-tenant call. The safety
  property survives; the *legibility* doesn't.
- **Audio upload is unavailable.** No local stdio fallback exists on a web host. `_read_upload`
  already refuses with an accurate message. Leave it.

**Skills:** Settings → Capabilities → Skills → upload one zip per skill (needs code execution
enabled). Use `sync_skills.py --target zip`.

### 7.2 ChatGPT

**Needs the broker (§4).** ChatGPT registers OAuth clients by DCR or CIMD; there is no field
for a pre-registered client id and secret, and no custom-header path to work around it.

**Prerequisites**

- Developer mode enabled: Workspace Settings → Permissions & Roles → Connected Data →
  developer mode / create custom MCP connectors. Business/Enterprise/Edu on ChatGPT web
  **[verify — availability by plan moves]**.
- Broker deployed; `WXCC_ISSUER_URL` on the MCP service pointing at it.

**Setup**

1. On the broker's `/register`, allowlist ChatGPT's redirect URI:
   `https://chatgpt.com/connector_platform_oauth_redirect` **[verify]** — the docs note a
   callback ID may be appended, so allowlist by prefix, not exact match, and log the value
   the first attempt actually sends.
2. Add a custom connector per tenant, URL `https://<service>/mcp?org=<org id>`.
3. Complete the OAuth flow in a private window.
4. First call: `wxcc_whoami`. Confirm the org before anything else.

**Watch for**

- **Deploy read-only until §5 ships.** ChatGPT's confirmation UX for MCP write tools is not
  something we control or can test on someone else's account.
- **No skills mechanism.** `wxcc_guide` (§6) is the whole answer. Optionally add a Project
  with instructions that say: *this connector administers exactly one WxCC tenant; call
  `wxcc_whoami` first; call `wxcc_guide` before any write.*
- Historically ChatGPT connectors were limited to `search`/`fetch` tools for deep research;
  developer mode lifted that. Confirm all 18 tools enumerate **[verify]**.

### 7.3 Codex

Two routes. Take the first now; the second when the broker lands.

**Route A — local stdio (works today, zero new infrastructure).** Codex runs on a machine
that can hold a token, so it can use the existing local server exactly as Claude Code does.
`~/.codex/config.toml`:

```toml
[mcp_servers.wxcc-sandbox]
command = "python"
args = ["/abs/path/to/wxcc-skills/mcp_server.py"]
env = { WXCC_PROFILE = "sandbox" }
```

One block per tenant, `WXCC_PROFILE` per block — the same multi-tenant model, unchanged.
Authenticate with `python wxcc.py auth login` per profile as today. **This is the fastest
path to a working Codex setup and needs nothing from this plan.**

**Route B — the cloud server over HTTP.**

```toml
[features]
experimental_use_rmcp_client = true   # needed on older versions for HTTP servers

[mcp_servers.wxcc-cloud-acme]
url = "https://<service>/mcp?org=<org id>"
bearer_token_env_var = "WXCC_TOKEN_ACME"
startup_timeout_sec = 20
```

or `codex mcp add wxcc-cloud-acme --url https://<service>/mcp?org=<org id> --bearer-token-env-var WXCC_TOKEN_ACME`.

The bearer-token form sidesteps OAuth entirely — but it means a Webex access token sitting in
an environment variable, which is a materially worse posture than the local token store it
replaces (that store is at least scoped, refreshed and per-profile). **Treat it as a
short-lived test path, not a deployment.** Once the broker exists, use `codex mcp login
wxcc-cloud-acme` and let it do DCR against the broker.

**Watch for**

- **Approval mode is the real risk here.** Codex's auto-approval modes will call `confirm=True`
  without asking anyone. Do not enable write scopes for Codex until §5 lands. This host is the
  reason §5 is on the plan.
- Codex reads `~/.agents/skills/` — see §6.

### 7.4 Gemini CLI

**Best case of the four.** Gemini CLI accepts an explicit OAuth block including client id,
client secret, endpoint URLs and scopes — so it needs neither DCR nor Step 0 to resolve
favourably. `~/.gemini/settings.json` (or `.gemini/settings.json` in the repo):

```json
{
  "mcpServers": {
    "wxcc-cloud-acme": {
      "httpUrl": "https://<service>/mcp?org=<acme's org id>",
      "oauth": {
        "enabled": true,
        "clientId": "<integration client id>",
        "clientSecret": "<integration secret>",
        "authorizationUrl": "https://webexapis.com/v1/authorize",
        "tokenUrl": "https://webexapis.com/v1/access_token",
        "scopes": ["cjp:config_read", "cjp:config", "cjp:config_write"],
        "redirectUri": "http://localhost:8484/callback"
      },
      "trust": false
    }
  }
}
```

Then `/mcp auth wxcc-cloud-acme`, and `wxcc_whoami` to confirm the org.

**Watch for**

- **`redirectUri` must exactly match one registered on the Integration.** Pin it as above and
  reuse the port already registered, rather than letting Gemini pick a random one.
- **Keep `trust: false`.** `trust: true` bypasses every tool-call confirmation — the same
  hazard as Codex auto-approval.
- Gemini CLI also supports `headers`, so `X-WXCC-Expected-Org` is available here as an
  alternative to `?org=`. Prefer `?org=`, to keep one form across hosts.
- **Secrets in `settings.json`.** Use `"$WXCC_CLIENT_SECRET"` — Gemini expands `$VAR` — and
  keep the file out of git. It is not currently in `.gitignore`; add `.gemini/` when this
  lands.
- Skills: `~/.gemini/skills/` or the `~/.agents/skills/` alias (§6). `/skills list` to confirm
  discovery.

---

## 8. Sequencing

Ordered so that each phase ships something usable on its own.

| Phase | Work | Unlocks |
|---|---|---|
| **0** | The discovery probe (§2). Record the answer here. | Sizes everything else |
| **1** | Ten sentences (§6); `sync_skills.py`; `.agents/skills/` | **Codex + Gemini CLI, read-only, today** — Codex via local stdio needs nothing else |
| **2** | Claude chat connector (§7.1), read-only | Non-technical users, no CLI, no repo |
| **3** | `confirm_token` (§5) | Writes become safe to enable on *any* host |
| **4** | The broker (§4) | ChatGPT; Codex over HTTP; removes a latent fragility in Claude Code |
| **5** | `wxcc_guide` (§6) | Skill knowledge on hosts with no skills mechanism |

Phase 1 and 2 are days. Phase 3 is a day. Phase 4 is the real build.

**Rule for every phase: new host goes live with `cjp:config_read` only, until phase 3 has
shipped and been tested on that specific host.**

---

## 9. What could still bite

- **Step 0 comes back empty.** Then the broker is mandatory for all four hosts and phases 2
  and 4 swap order. This is the single largest branch point in the plan.
- **A connector UI strips the query string** and the `?org=` guard silently disarms. The guard
  fails *open* when it can't find an expected org — that is deliberate for backwards
  compatibility, and it means a stripped query string looks exactly like a working
  connector. **Test wrong-tenant rejection explicitly on every new host**; a guard nobody has
  seen fire is a guard nobody knows is off. (`TODO.md` already flags a related fail-open in
  `ExpectedOrgGuard` for unparseable tokens — fix both together.)
- **`prompt=login` doesn't survive a host's OAuth implementation.** The browser-session trap
  has produced three wrong-tenant logins, once leaving a server named *sandbox* holding a
  *production* token. Any host that opens its own browser window rather than printing a URL is
  a fresh opportunity for it. Insist on a private window in every runbook, and check
  `wxcc_whoami` after every first sign-in.
- **Region.** `WXCC_API_BASE` is per-service, not per-caller. A non-`us1` tenant needs its own
  service on every host equally. Unchanged by this plan; still true.
- **Audio upload has no cloud story** and gains none here. On CLI hosts, keep a local stdio
  server alongside for that one call. On web hosts it is simply unavailable. If it becomes
  load-bearing, the fix is a base64 argument on `wxcc_create`, not a shared filesystem.
- **Skill drift.** The moment `.agents/skills/` is a committed copy rather than a generated
  one, the two will diverge. `sync_skills.py` should be verifiable — `--check`, like
  `build_api_reference.py` — and wired into the same gate.
- **Everything marked [verify] in §7.** Connector UIs, callback URLs and plan availability all
  moved more than once in the last year. Treat this document's specifics as a starting point
  and the live consent screen as ground truth.

---

*Draft 1 — 2026-07-27. Verified against the repo as of `e3b0727`; host behaviour from vendor
docs and issue trackers, not from live setup on each host.*
