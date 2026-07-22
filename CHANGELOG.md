# Changelog

Notable changes to the wxcc-skills library. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); entries are dated, newest first.

- **2026-07-22 — CORRECTION: two shipped claims about entry/bulk routes were false.** Both had
  been published here as *confirmed*. Earlier entries below are left as originally written;
  this entry supersedes them.
  - ~~"`address-book` and `user` have no bulk route at all — confirmed, not merely
    unprobed."~~ **Wrong on both.** The evidence was sound but probed only the parent level.
    Bulk lives on the **child** collection: `POST address-book/{id}/entry/bulk` → **207 +
    `items`**, likewise `outdial-ani/{id}/entry/bulk`. And `POST user/bulk` → **207 + `items`**
    directly (`v2`/`v3` variants 404). Routes confirmed; **their accepted ops remain unprobed**,
    so the bulk tools still refuse all three.
  - ~~"`GET .../entry` → 405; the child collection has no list endpoint, entries are readable
    only from the parent."~~ **Wrong.** `GET v2/<parent>/{id}/entry` is a real paginated list
    (200, `meta.totalRecords`). The 405 came from GETting the non-`v2` **POST-only create**
    path — the house rule (list carries `v2`, create drops it) holding, not an exception.
  - **New trap found while correcting:** `GET v3/address-book/{id}` returns 200 but **omits
    `addressBookEntries`**; the non-`v2` item path embeds them. Modernizing the item read to
    `v3` would silently empty every entry list.
  - Fixed in `wxcc-bulk`, `wxcc-address-books`, `wxcc-outdial-ani`, and the `_parent_entries` /
    `wxcc_list_entries` docstrings. **Behavior unchanged** — `wxcc_list_entries` still reads
    entries embedded in the parent. That matched the list path exactly on re-check
    (address-book 4/4, outdial-ani 1/1) but does **not** paginate; moving it to the `v2` list
    path is a logged follow-up, not done here.
  - Method lesson, since the tests themselves were fine: probe **every path level** (parent,
    child, `v2`/`v3`) before recording a route as absent, and never promote "not found at the
    one level I tried" to "confirmed absent."

- **Four new entities — the scheduling family plus `contact-number` — taking the registry to
  21, and `wxcc.py` to zero type errors.** All verified live on the sandbox 2026-07-21 through
  full create/read/update/delete round trips; every probe object was deleted and a sweep across
  all touched entities confirmed zero leftovers.
  - **`business-hours`, `holiday-list`, `overrides`** (all three plural-or-not exactly as
    written) follow the house pattern: list at `v2/<entity>`, item at `<entity>/{id}` (v2 →
    404), create at bare `POST <entity>`, bulk at `<entity>/bulk`. Each requires a **non-empty
    nested array** — `workingHours`, `holidays`, `overrides` respectively — so an empty-payload
    probe can never finish the job; the shapes have to be cloned from a live record.
    **`holiday-list` is the asymmetry worth knowing**: it does *not* require `timezone`, while
    `business-hours` and `overrides` both do. `business-hours.holidaysId` is a real reference —
    `GET holiday-list/{holidaysId}` resolves it.
  - **`contact-number`** is the caller-ID value shown on **internal** calls (per the tenant
    admin; stated, not API-verified). Despite the name it is **not** the DID inventory and
    nothing links it to `dial-number`: `number` is the only required field and is capped at
    **9 characters**, so an E.164 value returns `400 "should not be more than 9 characters"`.
    Two traps: `contact-number/all-numbers` is a real route but returns a **bare list of
    strings**, not objects, so it cannot be the list path (`v2/contact-number` is); and its
    `PUT` demands the `id` **in the payload** matching the URL. Import/export exist at
    `contact-number/import|export` on **PUT** (GET 404s) — payload shape still unprobed.
  - **Bulk reaches 19 of 21 entities**, and the id-wall is now universal: every one of the 19
    supports create + delete and **none** of the four added here supports update — same
    `400 "New configuration cannot have an id"` with `PATCH` → 405.
  - **`address-book` and `user` have NO bulk route — confirmed, not unprobed.** This corrects a
    standing "unprobed" note. `address-book/bulk` answers *identically* to
    `address-book/<any-garbage-id>`, so `bulk` is simply being parsed as an `{id}`. The
    generalisable lesson: **only a `207` with an `items` envelope proves a bulk route exists.**
    Status code cannot distinguish them (`GET team/bulk`, a working route, 404s exactly like
    nonsense), and neither can the error-body shape (`trackingId` vs `timestamp` only reveals
    whether the entity prefix is routed).
  - **`wxcc.py`: 10 Pyright errors → 0**, eight of them from a single wrong annotation.
    `die()` was declared `-> "None"` but its body is `raise WxccError(...)`; annotating it
    `NoReturn` restored narrowing across the whole auth path at a stroke, with zero runtime
    effect. The two real fixes: `log_message` now matches
    `BaseHTTPRequestHandler.log_message(self, format, *args)` exactly, because the base calls
    it with `format` as a **keyword** and the old `*_` was not a drop-in; and
    `__doc__.splitlines()` is guarded, since `__doc__` is `None` under `python -OO`.
- **New `wxcc_references` tool, bulk for four more entities, and a type cleanup that turned
  out to be a real crash class.** Verified live on the sandbox 2026-07-21; every probe object
  created was deleted and re-read as 404, and the entity counts were swept back to baseline.
  - **`wxcc_references`** exposes `GET {entity}/{id}/incoming-references` — the same scan
    `wxcc_delete` already ran as a pre-flight — as a read-only tool, so "what breaks if I
    touch this?" can be asked about an object you intend to **keep**. It reads the object
    first on purpose: a bad id 404s the references endpoint, which would otherwise come back
    as an empty list and read as "nothing points here" — the most dangerous wrong answer this
    question has. Tools go to **16**.
  - **Bulk now covers 15 of 17 entities.** `site`, `multimedia-profile`, `agent-profile` and
    `desktop-layout` were blanks that turned out to be **unprobed, not unsupported** — all
    four are `POST <entity>/bulk`, create + delete, **no update** (the same
    `400 "New configuration cannot have an id"` as team/skill/skill-profile; `PATCH` is 405).
    Only `user` (Control Hub owns it) and `address-book` are left.
    - **`agent-profile` bulk create 403s on a clone**: `"User not Allowed to create system
      default entity"`. Every stock Desktop Profile is `systemDefault`, so send
      `systemDefault=false`.
    - **`desktop-layout` returns a misleading 400** naming `"Teams assigned ... already
      assigned to another desktop layout"` on a payload with **no teams key at all**. The
      field is `teamIds` plus a `global` boolean, and a global layout implicitly claims every
      team. Send `global=false` and `teamIds=[]`.
  - **There is no read-only way to detect a bulk route** — worth recording, because it cost a
    round of confidently wrong method. `GET team/bulk`, a route that demonstrably works, 404s
    exactly like `GET not-a-thing/bulk`. The error-body shape (`trackingId` vs `timestamp`)
    looked like a clean signal until the confound control `GET team/notabulkroute` returned
    the `trackingId` shape too — it only proves the entity prefix is routed. Only a real POST
    settles it.
  - **Ruled out, so it is not re-litigated:** sub-resource entry tools for
    `skill-profile.activeSkills` and `user-profile.permissions`. Both carry the same
    kept-entry-needs-its-id 409 the entry tools exist to solve, but neither has a route —
    with `outdial-ani/{id}/entry` (405) as a positive control and `.../notachild` (404) as a
    negative, all six candidate paths 404. Read-modify-write via `wxcc_update` is the only
    shape. **`work-type` is struck too**: deprecated and obsolete in WxCC, so
    `auxiliary-code.workTypeId` stays a value you copy from an existing code.
  - **Six Pyright errors fixed at the call sites instead of silenced at the annotation.**
    `WxccClient.json()` correctly returns `tuple[int, object]`; re-annotating it `Any` would
    have cleared five of them while hiding the exact crash class that already bit once — the
    bare-string error body two entries below. Instead: an `_as_dict()` helper for bodies read
    without an isinstance check, `_read` now **raises** on a non-dict 200 rather than handing
    a caller junk to crash on later, and `_org_info` returns early on an unresolved org id
    instead of requesting `organization/None` and 404ing into a generic message. `_read` was
    re-checked against all 16 populated entities. `mcp_server.py` is at 0 errors; `wxcc.py`
    still has 10, untouched and out of scope.
- **Two new entities — `user-profile` and `resource-collection` — and bulk for five more.**
  Registry goes to **17 entities**, skills to **24**. All verified live on the sandbox
  2026-07-21 through the MCP tools, baselines restored (17/17 end-to-end checks green).
  - **`user-profile`** (admin access rights — *not* the Desktop Profile) is **the only entity
    whose item path keeps its version prefix**. `v3/user-profile/{id}` and `user-profile/{id}`
    BOTH answer with **different schemas**, and **v2 writes are decommissioned per-org**
    (`400 "v2 user profile is decommissioned for this organization"`) while v2 reads still
    succeed — so it looks like a permissions problem. Everything is pinned to v3. Two further
    traps: the permission list's write key is **`permissions`**, not the
    `userProfilePermissions` the API's own 400 names (sending that key is treated as absent,
    so you get the same 400 forever); and cloning a profile without stripping sub-entity ids
    returns `409 "Internal error"`. The list omits `permissions` — read the item.
  - **`resource-collection`** (the scoped groupings a user profile points at) requires **all
    20 resource types** in `resources` — a partial list is a helpful 400 naming the missing
    ones, but **omitting the key entirely is a bare 500**. `site`, `channel`, `team` and
    `queue` must not be `NONE`. The list omits `resources` — read the item.
  - **Bulk now covers 11 entities**, and the shape of what's missing is the point: `team`,
    `skill` and `skill-profile` have create + delete but **no bulk update** — all three
    return the same `400 "New configuration cannot have an id"` as `outdial-ani`, which is
    the signature of an op that does not exist rather than a body you can fix.
    `user-profile` has all three (on `v3/user-profile/bulk`). `resource-collection` is
    **update-only and on PATCH** — bulk create returns `500 "no mapping for id"`, bulk delete
    a `400`, and despite being PATCH it is *not* partial: a partial item comes back as a
    leaked Java NPE, so the tool read-modify-writes.
  - **Fixed while testing:** `wxcc_bulk_create` / `wxcc_bulk_update` validated item shapes
    *before* checking whether the entity supports that op at all, so asking
    `resource-collection` for a bulk create reported "missing required fields" instead of
    "bulk create is not supported". The op check now runs first. Caught by the new
    end-to-end refusal checks, which is what they were for.
- **Fixed: an error body with `error` as a string crashed the caller instead of reporting.**
  `_put_adaptive` (the read-modify-write retry behind `wxcc_update`) and the bulk per-item
  collator both walked `error`/`apiError` assuming a nested dict, so a 4xx whose `error` is a
  bare string raised `AttributeError: 'str' object has no attribute 'get'` — the API's own
  message was lost and the tool call died. Both now go through one `_api_reason()` helper that
  accepts either shape and stringifies anything else rather than dropping it. It surfaced from a
  malformed request. The string-shaped body is **real, not hypothetical** — it is what the
  platform's default handler returns for an unknown *route*
  (`{"timestamp":…,"status":405,"error":"Method Not Allowed","path":…}`, reproduced on
  `GET resource-collection` and `GET v2/resource-collections` while probing the new entities).
  It is **not** reachable through `_put_adaptive` while every registry path is correct, since a
  bad *object id* on a valid route returns the dict-shaped error instead (checked). It becomes
  reachable the moment a registry path is wrong or a route is retired — which is precisely what
  happened to v2 user-profile writes, so the guard is worth having.
- **Bulk writes: `wxcc_bulk_update` / `wxcc_bulk_create` / `wxcc_bulk_delete`** — act on many
  objects of one entity in a single call, plus a `wxcc-bulk` skill. **Verified live on the
  sandbox for six entities**, each op exercised end-to-end through the tools with baselines
  restored: `contact-service-queue`, `entry-point`, `auxiliary-code`, `dial-number`,
  `outdial-ani`, and **`cad-variable`** — the WxCC *Global Variables* entity, added here as the
  15th registry entity (read + full single CRUD + bulk, all verified). Bulk support is
  **per operation, per entity**, because the API is not uniform: `dial-number` has no bulk
  delete (it would unmap a live number — refused by the tool), and `outdial-ani` has no bulk
  update (an id-bearing save item → 400 "cannot have an id" — refused). Facts nailed down by
  probing, each of which the tools now handle:
  - **Routes and available ops are per-entity, one nested envelope.** Queues expose two routes:
    `PATCH contact-service-queue/bulk` is a *partial* update and `POST
    contact-service-queue/v2/bulk` saves; `auxiliary-code` is the same shape but both on
    `/bulk`. `entry-point`, `cad-variable`, `dial-number` expose a single `POST {entity}/bulk`
    with **no partial-patch route**, so `wxcc_bulk_update` read-modify-writes there (transparent
    to the caller, who still passes only `{id, changed fields}`). A save item creates when it
    has no id, deletes with `requestAction: DELETE`. Body is
    `{"items":[{"itemIdentifier":<int>,"item":{...},"requestAction":"SAVE"|"DELETE"}]}` — the
    array key is `items` but each element wraps the object under `item`; the response reuses
    `items` with a per-item shape. Sending `{"items":[{id,...}]}` unwrapped is a 400.
  - **Always HTTP 207 Multi-Status.** The tools collate the per-item results into
    `succeeded` / `failed` (with the API's own reason) / `NOT_PROCESSED` — the last catches the
    empty-result no-op, because a 207 is not proof anything applied.
  - **Delete needs the FULL object**, not just an id (an id-only delete returns a misleading
    `"Cannot Update/Delete system generated Entities"` 400) — so `wxcc_bulk_delete` takes ids
    and fetches each object itself.
  - **The API self-guards references per item**: a still-referenced delete comes back `412`
    (proven on a queue's flow reference and an entry-point's dial-number reference), so no
    client-side pre-flight is needed for bulk.
  - **Registry-gated per (entity, op).** Each `bulk` block lists only the proven ops
    (`create`/`update`/`delete`), each with its method, path tail, and whether update is a
    native partial patch; the tools refuse an unverified entity or op and name what is
    supported. Adding an entity is a live probe (an empty-`items` POST is a safe existence
    check — 207 if the route exists, 404 if not) plus a registry block.
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
