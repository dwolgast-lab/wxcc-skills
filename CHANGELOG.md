# Changelog

Notable changes to the wxcc-skills library. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); entries are dated, newest first.

- **`docs/marketing-hype.md` rewritten as plain Markdown**, matching the style of
  `user-guide.md`/`cloud-mcp-onboarding.md` instead of the hand-rolled HTML/CSS dashboard
  layout it started as, so it now flows through the same shared CSS in
  `build_user_guide_pdf.py` (cover band, styled tables, blockquote) rather than fighting it
  with inline styles. Dropped `scripts/download_logo.py` and `docs/webex_logo.svg`: neither
  was actually wired into the doc's real content (it had its own different inline SVG), and
  the two sibling docs don't use a logo either. **Found and fixed a real bug in
  `hooks/pre-commit`** while doing this: `check_and_build()` takes an explicit
  `(src, out)` pair but never passed `out` to the build script, relying on the script's
  default filename derivation to happen to match — true by coincidence for
  `cloud-mcp-onboarding.md` (same stem), false for `marketing-hype.md` (wanted the branded
  `wxcc-marketing-hype.pdf`, would have derived plain `marketing-hype.pdf`). The hook would
  have `git add`ed a stale or missing file silently. Now passes `--out "$out"` explicitly.
- **`multimedia-profile` now has verified full CRUD** (14th registry entity), closing the
  gap `wxcc-sites` had been flagging: a site's `multimediaProfileId` can be resolved to a
  name and channel caps, and profiles can be created/updated/deleted. New
  `wxcc-multimedia-profiles` (read) and `wxcc-multimedia-profiles-write` skills;
  `wxcc-sites` routes to them. All paths and the write contract verified live on the
  sandbox and re-verified through the MCP tools (create 201, update 200, delete 204,
  baseline restored): list `v2/multimedia-profile`, item/create paths drop v2
  (`v2/.../{id}` 404s), `filter=name==` works. Required create fields: name, active, the
  four channel caps (telephony/chat/email/social), blendingMode
  (`BLENDED|BLENDED_REALTIME|EXCLUSIVE`), blendingModeEnabled, and the nested
  `manuallyAssignable`. The per-channel integers are concurrent-contact caps, not booleans.
  Delete is reference-blocked by sites via the incoming-references pre-flight.
- **`wxcc_update` gained an adaptive feature-flag retry.** A read-modify-write PUT re-sends
  every field the GET returned, including ones a tenant is not entitled to write — the API
  returns `multimedia-profile.workItem` on GET (top-level and nested in `manuallyAssignable`)
  but rejects it on PUT when the workItem feature flag is off (`400 "workItem is not allowed
  when feature flag is disabled"`). The tool now strips exactly the field the API names and
  retries once, reporting it under `stripped_for_feature_flag`. This is discovered per call,
  not hardcoded — a flag-enabled tenant's first PUT succeeds and nothing is stripped — and it
  only triggers on that specific 400, so every other entity's update is unaffected
  (regression-checked with a site update round-trip).
- **New teammate one-pager**: [`docs/cloud-mcp-onboarding.md`](docs/cloud-mcp-onboarding.md)
  (+ auto-built PDF) — explicit, no-assumed-knowledge steps for connecting Claude Code to a
  cloud `wxcc-mcp` tenant, written for someone new to both Claude Code and this project.
  Covers what to get from the tenant admin, the `add-json` + `--no-browser` sign-in flow
  including the expected "connection refused" redirect, and a table of example prompts with
  their expected (non-tenant-specific) outcomes.
- **PDF auto-build generalized to any doc**, not duplicated: `scripts/build_user_guide_pdf.py`
  takes `--src` (defaults to the original `user-guide.md`/`wxcc-skills-user-guide.pdf` pair
  for back-compat) and derives `--out` from the source's stem otherwise.
  `hooks/pre-commit` loops a small table of (markdown, pdf) pairs instead of checking one
  hardcoded filename, so a third doc is a one-line addition.
- Two real bugs found and fixed while building the second doc: a relative `--src` produced a
  relative derived `--out`, which headless Chrome's `--print-to-pdf` silently failed to write
  (it doesn't resolve relative paths against this process's cwd) — now resolved to absolute
  before use. And long unbroken command lines were **clipped** in the printed PDF, not just
  scrollable — `overflow-x: auto` has no effect once Chrome prints to PDF — fixed with
  `white-space: pre-wrap; word-break: break-all` so they wrap instead of disappearing.
  Re-verified the original user-guide PDF still renders correctly after the shared CSS change.
- Noted, not fixed (pre-existing, out of scope here): the `gcloud run services update` block
  in "Adding a customer tenant" renders as inline text instead of a code block in the PDF —
  an indentation/fencing issue in the existing markdown source.
- **`wxcc_list` now URL-encodes filter/search/attributes values**, which kills the
  raw-`+` silent-zero trap at the tool layer: `dialledNumber==+1719...` and a `+` in
  `search=` now match (verified live — the same search returned 0 of 2 records before the
  fix). The spaces question is answered too: a bare space inside an RSQL value is a syntax
  error, but a *quoted* value works — and the old "quoted values → 400" rule turns out to
  have been transport-layer all along (raw quotes rejected before RSQL ever parsed them;
  encoded, both quote styles parse fine). DN `search=` confirmed: substring match over the
  number digits. Callers pass raw characters now — pre-encoding would double-encode. The
  CLI path keeps all the old traps.
- **Sites are writable.** Full lifecycle verified live: create 201, rename 200, delete 204,
  each confirmed by re-read. All three create fields (`name`, `active`,
  `multimediaProfileId`) are required — the 400 names the missing ones. Deleting a
  referenced site is pre-flighted; a live site showed 15 blockers across teams and users.
- **GraphQL aggregations verified** (they were candidate syntax from Cisco's collection):
  types are `count|sum|average|min|max|cardinality` (`avg` is rejected); the scalar fields
  selected in `tasks{}` become the GROUP BY keys; `filter:` composes. By-queue counts were
  cross-checked against the plain-count baseline. Also fixed a fabricated example in
  `wxcc-tasks-search`: `queue { name }` does not exist — the field is `lastQueue`, and a
  `lastQueue: null` group is real data (tasks that never touched a queue).
- **Desktop Profile writes closed**: create 201, delete 204, and field-level update 200,
  all verified live (previously refused as unprobed). Create means cloning a sibling, and
  the naive clone 409s with an uninformative "Internal error" — isolated to a nested
  sub-entity id, so `wxcc_create` now strips nested ids for entities marked
  `clone_safe: false`. Found the paired-field rule: `autoWrapAfterSeconds` alone is a
  clean 400 — it must travel with `autoWrapUp`.
- **The delete pre-flight now asks the API itself**: `GET {entity}/{id}/incoming-references`
  exists on every entity tested (10 of 10) and is authoritative, retiring the hand-written
  reference map — which was provably incomplete (12 blockers found by hand vs. 15 by the
  API on the same object). Reading it right matters: `data[]` holds only
  `meta.currentEntity` — walk `?type=<each>` per referencing type.
- **A wrong-tenant login is now refused by the cloud server**, not just detectable: a
  client entry declares its org (`?org=<id>` on the URL or `X-WXCC-Expected-Org`) and a
  token from any other org gets **403 `wrong_tenant`** naming both orgs. The org is read
  from the token itself, so it cannot be spoofed; declaring nothing keeps the old
  behaviour. Also fixed: `allowed_hosts` hardcoded port 8080 (any other local port
  answered 421 Misdirected Request); it now derives from `WXCC_PUBLIC_URL`.
- **Cloud teammate onboarding documented** — two commands, no repo, no Python, no `.env`.
  What actually gates it: the teammate must be a CC admin of that tenant (OAuth is
  per-user), needs the Integration's client secret (Webex has no public client), and their
  org must be in `WXCC_ALLOWED_ORGS` — a gcloud step, not self-service. `WXCC_API_BASE` is
  per-service, so another region needs its own Cloud Run service.
- **Entry sub-resource tools**: `wxcc_list_entries` / `wxcc_add_entry` /
  `wxcc_update_entry` / `wxcc_remove_entry` for `outdial-ani` and `address-book`, verified
  live (POST 201 / PUT 200 / DELETE 204; GET on the child collection is 405 — entries are
  read from the parent). Retires the earlier full-replace advice, which was accurate and
  dangerous: an entry you omit is deleted, and a kept entry without its own id 409s.
- **`SILENTLY_IGNORED` no longer cries wolf.** The API enriches sub-objects with
  ids/timestamps and reorders arrays, so a correct array write used to be flagged as
  ignored. Scalars are still compared exactly; complex values are reported under
  `needs_your_eyes` with the actual value to read. The real trap
  (`userLevelSummariesInclusion`: 200 but unchanged) is still caught — its enum is
  `EXCLUDED | NOT_APPLICABLE | INCLUDED`, so the silent ignore is entitlement-gated, not
  validation.
- **The helper graduated into an MCP server.** `mcp_server.py` exposes 12 tools over a
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
