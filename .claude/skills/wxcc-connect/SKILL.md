---
name: wxcc-connect
description: Use when first setting up Webex Contact Center (WxCC) admin access, or when a wxcc.py call fails with "not authenticated", HTTP 401, an expired/invalid token, or a redirect/scope mismatch during consent. Covers registering the OAuth Integration on developer.webex.com, filling .env, running the one-time consent flow, and verifying connectivity with a read call. Run this before any other wxcc-* admin skill.
---

# wxcc-connect — set up and verify WxCC API access

This skill establishes the OAuth connection that every other `wxcc-*` skill depends on.
It is done once per machine (plus occasional re-auth). All API calls go through the shared
helper `wxcc.py` at the repo root.

## Use when / Do NOT use when

**Use when:**
- Setting up WxCC admin access on a new machine for the first time.
- A `wxcc.py` call fails with `not authenticated`, HTTP `401`, or a token error.
- Consent fails with a redirect-URI or scope mismatch.
- You need to add write scopes (see "Adding write access" below).

**Do NOT use when:**
- You are already connected (`python wxcc.py auth status` shows `valid`) and want to perform
  a specific admin task → use the matching `wxcc-<domain>` skill for that task.
- You need to change the helper's code itself → that is a development change to `wxcc.py`,
  not this runbook.

## Definitions

| Term | Meaning |
|---|---|
| Integration | A Webex OAuth app (user-context, authorization-code flow) registered at developer.webex.com. Yields a `client_id` + `client_secret`. |
| Scope | An OAuth permission string. `cjp:config_read` = read CC config; `cjp:config` = write. The authorizing user must be a WxCC administrator. |
| orgId | Your tenant's Contact Center org identifier, injected into API paths as `{orgId}`. Auto-derived from the token; overridable via `WXCC_ORG_ID`. |
| API host | Region-specific runtime host, e.g. `https://api.wxcc-us1.cisco.com`. Set via `WXCC_API_BASE`. |
| Token store | `.wxcc/tokens.json` (gitignored). Holds access + refresh tokens and expiry. |

## Prerequisites

- Python 3 on PATH. → verify: `python --version`
- A Webex account with **Contact Center administrator** privileges on the target tenant.

## Procedure

### 1. Register an OAuth Integration (one time, in a browser)

Go to **developer.webex.com** (the converged portal — the old `developer.webex-cx.com` is
deprecated) and create a new **Integration**. As of 2026-07-10 this is under your profile
menu → "My Webex Apps" → "Create a New App" → "Integration"; if the labels differ, follow
the portal's official guide: https://developer.webex.com/docs/integrations

Set these fields:
- **Redirect URI:** `http://localhost:8484/callback` (must match `WXCC_REDIRECT_URI` exactly).
- **Scopes:** select `cjp:config_read` (add `cjp:config` only when you need write skills).

Save. Copy the generated **Client ID** and **Client Secret**.

### 2. Fill in `.env`

From the repo root:

```bash
cp .env.example .env      # PowerShell: Copy-Item .env.example .env
```

Edit `.env` and set `WXCC_CLIENT_ID`, `WXCC_CLIENT_SECRET`, and `WXCC_API_BASE` to your
region's host. Leave `WXCC_REDIRECT_URI` and `WXCC_SCOPES` at their defaults unless you
changed them in step 1. `.env` is gitignored — never commit it.

> Region note: only `api.wxcc-us1.cisco.com` (US) is confirmed here. For other regions, set
> `WXCC_API_BASE` to your tenant's host (find it in your CC admin portal / Cisco docs).

### 3. Run the one-time consent flow

```bash
python wxcc.py auth login
```

This opens a browser to Webex, where you sign in as the admin and approve the scopes. The
helper catches the redirect on `localhost:8484`, exchanges the code for tokens, and saves
them to `.wxcc/tokens.json`. On success it prints your `org_id`.

### 4. Verify connectivity

```bash
python wxcc.py auth status
```
→ verify: prints `status : valid, ~NNNh left` and a non-empty `org_id`.

Then confirm a real read against the tenant (List Users is a confirmed read endpoint):

```bash
python wxcc.py get "/organization/{orgId}/v2/user"
```
→ verify: prints a JSON body of users (not an error). This proves auth, org resolution,
region host, and scope are all correct end-to-end.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Browser shows redirect-URI error | The URI in the Integration ≠ `WXCC_REDIRECT_URI`. Make them identical, including scheme, host, port, and `/callback`. |
| `state mismatch on callback` | A stale/duplicate browser tab answered. Re-run `auth login` and use the freshly opened tab. |
| HTTP `401` on `get` | Token expired or scope missing. Try `python wxcc.py auth refresh`; if it persists, re-run `auth login`. Confirm the authorizing user is a CC admin. |
| `org id is unknown` / 404 on org | Auto-derivation from the token failed (this method is unverified). Set `WXCC_ORG_ID` in `.env` to your tenant's CC org id. |
| Reads work but writes 403 | You only have `cjp:config_read`. See "Adding write access". |
| Wrong/empty data | `WXCC_API_BASE` points at the wrong region. Set it to your tenant's host. |

## Adding write access (later)

Write skills need the `cjp:config` scope. To add it: edit the Integration on
developer.webex.com to include `cjp:config`, set `WXCC_SCOPES=cjp:config_read cjp:config`
in `.env`, then re-run `python wxcc.py auth login` to re-consent to the broader scope.

## Provenance and maintenance

Facts below were confirmed on 2026-07-10 from official Webex docs (fetched that day) and by
running the helper locally. The full OAuth round-trip (`auth login`) is verified by the
operator against a live tenant, not by the skill author.

- OAuth endpoints `https://webexapis.com/v1/authorize` and `/v1/access_token`; access token
  ~14 days, refresh token ~90 days rolling — doc'd from developer.webex.com OAuth guide,
  2026-07-10; re-verify: `curl -s -o /dev/null -w "%{http_code}" https://developer.webex.com/docs/understanding-oauth-flow-of-webex-integration` (expect 200, then re-read).
- Register Integration on developer.webex.com; `developer.webex-cx.com` deprecated — per
  operator (2026-07-10) and the converged-portal announcement.
- CC read scope `cjp:config_read` (write `cjp:config`); authorizing user must be a CC admin —
  doc'd from the Webex CC API authentication blog, 2026-07-10.
- API host `https://api.wxcc-us1.cisco.com` and List Users path `/organization/{orgId}/v2/user` —
  doc'd from the same blog, 2026-07-10.
- orgId derived from the substring after the token's final `_` — doc'd but **UNVERIFIED**
  against a live tenant; treat as candidate until step 4 succeeds. `WXCC_ORG_ID` overrides it.
- Helper interface (`auth login|status|refresh|logout`, `get PATH`) — ran locally 2026-07-10;
  re-verify: `python wxcc.py --help`.
