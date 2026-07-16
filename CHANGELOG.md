# Changelog

Notable changes to the wxcc-skills library. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); entries are dated, newest first.

## Unreleased

- **The helper graduated into an MCP server.** `mcp_server.py` exposes 8 tools over a
  13-entity registry. Writes are dry-run by default; `confirm=true` executes, then
  **re-reads and diffs**, reporting `SILENTLY_IGNORED` when the API returns 200 but drops
  a field. Deletes pre-flight references and block with a list of conflicts instead of
  surfacing the API's 412 after the fact. Required fields are checked before the call.
- **Every result names its tenant** — from `GET organization/{orgId}` (the tenant's own
  record), not a configured label, tagged `[PRODUCTION]` or `[trial/sandbox]` off
  `subscriptionType`. On writes it is the first field read.
- **Multi-tenant:** `WXCC_PROFILE` selects `.env.<profile>` + its own token store. One MCP
  server per tenant, so the tenant is part of the tool name. No "switch tenant" command,
  deliberately. `auth login` now refuses a login whose org collides with another profile,
  and sends `prompt=login` — though `--no-browser` is the control that actually works.
- **Cloud Run deployment** (`mcp_http.py`, `Dockerfile`): the same tools, with the caller's
  own Webex OAuth token arriving on the request. The server stores no credentials — no
  token store, no refresh race, no standing admin credential. Verified end-to-end.
- **All 19 skills now call the MCP tools** instead of shelling out to the CLI (110 CLI
  references → 9, both deliberate fallbacks). Facts the registry enforces were removed from
  the prose so they have one home.
- `wxcc.py`: `WxccError` (raises instead of exiting) and `WxccClient` with an injected
  token, so one code path serves the local token store and a request-header bearer.
- Docs rewritten (Draft 3): the setup path now actually works from a fresh clone — it was
  missing `pip install -r requirements.txt` entirely, plus the `.mcp.json`, approval, and
  restart steps.
- New confirmed API facts: the create-collection path drops `v2` (`POST v2/<entity>` → 405);
  team deletes are reference-blocked by users (412, `referencedEntities` nested under
  `error`); multi-team membership works; the API reorders `teamIds`.
- Added five skills, all probed live: `wxcc-entry-points-write` (EP lifecycle verified
  201/200/204; dial-number writes documented incl. the numbers-must-exist-in-Calling
  404), `wxcc-skill-profiles-write` (skill + profile lifecycles verified, ENUM value
  rules and the sub-entity-id 409/500 traps reproduced), `wxcc-desktop-layouts`
  (read + write; layout JSON travels as an embedded string), `wxcc-tasks-search`
  (GraphQL Search API + REST `v1/tasks` over interaction data), and `wxcc-webhooks`
  (event-type catalog + subscription CRUD — update is PATCH).
- `wxcc.py`: new `patch` command (subscriptions API updates use PATCH).
- Sibling read skills now point at their write counterparts; user guide updated
  (Draft 2): catalog, limits, roadmap.
- User-guide PDF now regenerates automatically: `scripts/build_user_guide_pdf.py`
  (markdown → styled HTML → headless Chrome) wired to a versioned `hooks/pre-commit`
  that rebuilds and stages the PDF whenever `docs/user-guide.md` is committed.
  Activate per clone with `git config core.hooksPath hooks`.
- Added four domain skills, all probed live: `wxcc-aux-codes` (full CRUD),
  `wxcc-address-books` (full two-level CRUD incl. entries), `wxcc-outdial-ani`
  (create/delete verified — endpoints absent from Cisco's collection; update pending),
  `wxcc-desktop-profiles` (reads + verified update shape; Desktop Profile is the current
  name — `agent-profile` in paths is backwards compatibility).
- First draft of the [User Guide](docs/user-guide.md).
- Added `wxcc-queues-write` (create 201 / update 200 / delete 204, all verified live;
  required-field rule for the five permission booleans reproduced from a real 400) and
  `wxcc-users-write` (update-only by design — identity fields immutable, one field
  silently ignored on 200, team-assignment validation rules documented; every probe
  reverted).
- Added `wxcc-teams-write`: create/update/delete teams with confirm-before-write and
  rollback discipline. Full lifecycle verified live (POST 201, PUT 200, DELETE 204,
  tenant restored to baseline). Write scope confirmed as `cjp:config_write`.
- `wxcc.py`: `post`/`put`/`delete` commands with `--body` (inline JSON, `@file`, or stdin).
- `auth status` now shows the scopes actually granted on the stored token when the token
  response includes them, alongside the configured (requested-at-next-login) scopes.

## 2026-07-11

- Published to GitHub: <https://github.com/dwolgast-lab/wxcc-skills> (public).
- Added `wxcc-entry-points` (entry points + dial numbers, incl. number→EP and EP→numbers
  lookups and the raw-`+` silent-zero-results trap) and `wxcc-skill-profiles` (routing
  skills + skill profiles).

## 2026-07-10

- Added `wxcc-teams`, `wxcc-queues`, `wxcc-sites` read-only skills. Confirmed the queue
  entity is `contact-service-queue` and that item paths drop `v2` (except queues, where
  both forms work).
- Added `wxcc-users` read-only skill; confirmed `filter`/`search`/`attributes` syntax.
- `wxcc.py`: `get --all` pagination; clean errors for Git Bash path mangling, broken
  pipes, and connection failures.
- Verified the full OAuth + API pipeline end-to-end against a live us1 tenant.
- Initial scaffold: `wxcc.py` helper (OAuth authorization-code flow, token store/refresh,
  org-id resolution), `wxcc-connect` setup skill, `.env.example`.
