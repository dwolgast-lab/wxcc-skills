# Changelog

Notable changes to the wxcc-skills library. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); entries are dated, newest first.

- **2026-08-01 — Take MCP 2.0.0 / the 2026-07-28 revision. The pin's own rationale was wrong.**
  `mcp 2.0.0` is stable on PyPI and speaks `LATEST_PROTOCOL_VERSION = 2026-07-28`. The
  2026-07-27 assessment cleared the revision as costing this project almost nothing. It
  **missed the only change that actually broke us**, because it read the spec changelog and
  never imported the SDK: **`mcp.server.fastmcp` does not exist in 2.x.** `FastMCP` is now
  `mcp.server.mcpserver.MCPServer`. Both entrypoints failed at line 1 on import.
  - **Migration, and it is smaller than that sounds.** `MCPServer` keeps `.tool()`,
    `.streamable_http_app()`, `.run()` and `._token_verifier` with the same shapes, so all
    **18 tool decorators are untouched**. `mcp.server.auth` — `AuthSettings`, `TokenVerifier`,
    `AccessToken`, `auth_context.get_access_token` — is unchanged, so `_client()` and
    `_served_remotely()` needed nothing.
  - **The transport knobs moved off `settings` onto `streamable_http_app()`**
    (`stateless_http`, `transport_security`, `host`; `port` is uvicorn's). This was the one
    genuinely dangerous shape, and it lands **safe**: `Settings` is a pydantic model that
    now *rejects* the old names — `mcp.settings.stateless_http = True` raises
    `ValueError: "Settings" object has no field "stateless_http"` at import. Verified by
    assignment, all three. A stale line fails loudly; it does not silently stop applying.
  - **Both items TODO.md held as blocking are cleared, on a real wire — not by reading.**
    - `ttlMs`/`cacheScope`: **the SDK supplies them.** `apply_cache_hint` fills any field
      the handler did not set from a default `CacheHint(ttl_ms=0, scope="private")`. A live
      `tools/list` came back `"cacheScope":"private"` with no application code at all.
      Per-tool tuning is available via the `cache_hints=` constructor arg; we take defaults.
    - `Mcp-Method`/`Mcp-Name` vs `ExpectedOrgGuard`: **the guard is transparent and still
      fires.** Enforcement lives in the SDK kernel (`classify_inbound_request` rung 2), not
      in our ASGI layer. Six assertions against the guard wrapping a real 2.0.0 app: a
      matching org passes through to a `200` `tools/list`; a mismatched org is rejected
      `403 wrong_tenant` via **both** the `?org=` and `X-WXCC-Expected-Org` forms; a
      disagreeing `Mcp-Method` and a disagreeing `Mcp-Name` each return `-32020` **through**
      the guard, proving it neither eats nor corrupts header enforcement. The wrong-tenant
      guard is the one safety device here with no fallback; it is no longer inferred-safe.
  - **What still speaks the old contract — checked, because this is the part that bites.**
    A 2.0.0 server serves a **legacy 2025-11-25 client** unchanged: `initialize` negotiates
    *down* to `2025-11-25`, and `tools/list`/`tools/call` answer `200` with **no** envelope
    and **no** `Mcp-Method` header, correctly omitting `ttlMs`/`cacheScope`/`resultType`.
    Confirmed over HTTP *and* over a real **stdio** subprocess — the transport the six
    configured `wxcc-*` servers actually use — which returned all 18 tools by name.
    2026-07-27 recorded this as "inferred from the changelog's own provisions"; it is now
    measured.
  - **Pinned `mcp==2.0.0` exactly, both bounds.** The old `>=1.28,<2` guarded only the major,
    and forge had already drifted to `1.29.0` against the laptop's `1.28.1` — so "verified on
    the laptop" had quietly stopped implying "verified on forge." An exact pin is what makes
    the two hosts identical.
  - Cleared the two pre-existing pyright errors in the same constructor
    (`issuer_url`/`resource_server_url` want `AnyHttpUrl`, got `str`). Whole-project
    baseline **2 errors → 0**.
  - `pydantic>=2` is now a **declared** dependency. `mcp_http.py` imports it by name for
    `AnyHttpUrl`; it arrived transitively via `mcp` before, which would have broken with no
    line to point at if a future `mcp` dropped it.
  - **Both hosts migrated and verified the same day, by live read rather than version string.**
    Laptop (`pip install -r requirements.txt`, 1.28.1 → 2.0.0): a real stdio `wxcc_whoami`
    returned `Personal Sandbox` with write scopes intact. Forge (`docker build`, 1.29.0 →
    2.0.0): over the real `ssh → docker run -i` path, all three profiles negotiated the
    legacy handshake and each returned its own distinct org — `174bc2cb-…`, `f766bc3c-…`,
    `278aa0f3-…`. No collision. The pre-upgrade image is retained as `wxcc-mcp:pre-mcp2`.
  - **Known cosmetic regression:** `serverInfo.version` is now `""` where FastMCP reported
    the SDK version. The sentence in `docs/forge-deployment.md` that read the handshake's
    `"version":"1.29.0"` as the SDK version has been corrected. Nothing consumes it.

- **2026-07-27 — The test that proved the query-DTO fix could not actually have caught it.**
  External code review (Codex Sol 5.6) flagged it; measurement confirmed it. The
  correction below called `rename_in_query_dto_schema` "the case that would have caught
  this." **It would not have.**
  - Every one of the four DTOs is also `$ref`d from its own **bulk-request envelope**, so
    renaming a `TeamDTO` property moves `POST team/bulk` too — and the test asserted only
    that *some* drift was reported. Reconstructing the pre-fix implementation and
    re-running it: the mutation moved **1 route** (`POST team/bulk`), the assertion was
    satisfied, and the test passed **against the exact bug it was written to catch**.
  - **Fixed by asserting the exact route set, not a boolean.** A query-DTO rename must move
    all three of `POST <entity>`, `PUT <entity>/{id}` and `POST <entity>/bulk`; the first
    two are reachable *only* through the query parameter, so a body-only detector cannot
    produce them. Extended from `team` alone to **all four** DTO-backed entities — they are
    masked identically, so covering them without the route assertion would have fixed
    nothing. Six cases became nine, every one now naming the routes it expects.
  - **Validated the way the detector itself was**: rebuilt the pre-fix world entirely
    (body-only hashing *and* a body-only baseline) and re-ran. The four query-DTO cases
    **fail**, the other five still pass — which is correct, since those test behaviour
    body-only hashing also had. A test that has only ever passed proves nothing; this one
    has now been shown to fail against the implementation it exists to reject.
  - Review's second finding — `payload_hash` ignoring `$ref`d/path-item/`content`
    parameters — **measured and not reproduced**: zero occurrences in the live spec, zero
    on the 82 tracked writes, no sentinels. Filed in `TODO.md` as the latent risk it is
    (the miss would be *silent*), not the blocker it was reported as.
  - Housekeeping the same review surfaced: `pyrightconfig.json` used a `"_comment"` key,
    which pyright rejects as an unrecognised setting, printing
    `Config contains unrecognized setting "_comment"` to stderr on every run. **The commit
    message on `930000c` claims this made pyright exit non-zero; that is wrong** — tested
    in isolation, `_comment` with zero type errors still exits 0, and the repo's non-zero
    exit comes entirely from the two pre-existing `mcp_http.py` errors. The real cost was
    noise on top of a gate whose output is read for exactly that. `930000c` is already
    pushed, so its message stands uncorrected; this is the correction. Moved to `//`
    comments, which pyright does accept; the file must stay **BOM-free**, since a BOM
    makes it unparseable (both confirmed by test, and the BOM is what made the first
    attempt look like comments were unsupported). Two entries below were dated
    `2026-07-26` but committed `2026-07-27`, which left the correction below claiming
    "yesterday's entry" about an entry sharing its own date — both re-dated. Stale
    body-only wording fixed in `build_api_reference.py` and `TODO.md`. The
    **2026-07-26 entry is left as written**: this file corrects in a new entry rather
    than editing history, and its `74/82` claim is already corrected below.

- **2026-07-27 — CORRECTION: the drift detector was blind to query-parameter payloads.**
  Yesterday's entry claimed `team`, `skill`, `skill-profile` and `agent-profile` "publish
  NO request body at all" and that "schema drift can never cover them." **The first half is
  misleading and the second is false.** User-supplied correction, confirmed against the spec.
  - Those four declare no `requestBody` because the object rides in a **required query
    parameter** holding urlencoded JSON — and the parameter is not even consistently named:
    `team` → `?teamDTO=` (`TeamDTO`), `skill` → `?payloadDTO=` (`SkillDTO`), `skill-profile`
    → `?skillProfileDTO=`, `agent-profile` → `?agentProfileDTO=`. All four are fully
    schema'd. **The payload was always hashable; the detector was looking in one place.**
  - `body_hash` → `payload_hash`: it now hashes the request body **and** every required
    non-path parameter. Coverage went **74/82 → 82/82, no sentinels left**. Path params are
    excluded (orgid/id, pure noise) and so are optional query params, so pagination churn
    still cannot trip it. Create and update now share a hash per entity, which is the
    correct signal — same DTO on both.
  - **The negative test grew the case that would have caught this**: renaming a property in
    `TeamDTO`, reachable *only* through `?teamDTO=`, must trip. Plus a new noise guard —
    adding an optional query parameter must NOT trip. Six cases, all passing.
  - **A JSON body works on these routes anyway** (verified live 201/200 2026-07-11) and is
    what the tools send. The API accepts both forms; the spec documents only one. Recorded
    in all four registry notes, because someone reading the spec could otherwise "fix" a
    working code path to match it.
  - `pyrightconfig.json` added (`extraPaths: ["scripts"]`) so `tests/` importing
    `build_api_reference` resolves for the type checker instead of being silenced with
    `type: ignore`. Whole-project pyright is back to its **2 pre-existing** errors
    (`mcp_http.py:105-106`, `AnyHttpUrl` vs `str`), now tracked in `TODO.md`.

- **2026-07-27 — Pin the MCP SDK below 2.x ahead of the 2026-07-28 spec revision.**
  `requirements.txt` was `mcp>=1.28`, an open upper bound. The 2026-07-28 revision
  **removes the `initialize`/`initialized` handshake and protocol-level sessions**, and SDK
  support for it lands in the **2.x** line (`2.0.0rc1` is on PyPI; latest stable is
  `1.28.1`, which speaks `2025-11-25`). Without a bound, a routine
  `pip install -r requirements.txt` would have silently changed the wire protocol on a
  project whose entire discipline is probe-before-trust. Now `mcp>=1.28,<2` — verified to
  admit 1.28.x/1.29.x and reject `2.0.0rc1`/`2.0.0` even with prereleases enabled.
  - **Most of the revision costs this project nothing**, which is worth recording so nobody
    re-derives it in a panic: `stateless_http` was already on, the transport is already
    `streamable_http_app()` (HTTP+SSE is now Deprecated), and the server registers **18
    tools and nothing else** — so the Roots/Sampling/Logging deprecations and the entire
    Multi Round-Trip Requests redesign are inapplicable. The hardened authorization rules
    are client-side; we are a resource server.
  - **Two items genuinely need validation before taking 2.x**, both now in `TODO.md`:
    `ttlMs`/`cacheScope` becoming required on `tools/list`, and the new mandatory
    `Mcp-Method`/`Mcp-Name` headers landing in the same ASGI layer as `ExpectedOrgGuard` —
    the wrong-tenant guard, which has no fallback if it silently stops firing.

- **2026-07-26 — The first committed tests, and drift detection that reads schemas.**
  Two gaps closed, both of which undercut every "verified live" claim in this file.
  - **THE REPO HAD NO TRACKED TESTS.** The "audio suite" referenced in the 2026-07-22 entry
    was never committed, so 23 entities' worth of hard-won path quirks had nothing re-checking
    them. New `tests/test_registry.py` — **13 tests, stdlib `unittest`, no pytest and no new
    dependency**. It reads `ENTITIES` by reusing `load_entities()` (which parses
    `mcp_server.py` with `ast`), so it runs with no `mcp` package, no token and no tenant.
  - **Every assertion cites the line that consumes the key**, because a test that guards
    nothing real is decoration. The one most worth having: `_path` builds the create path as
    `spec["item"].replace("/{id}", "")`, so an `item` missing that exact substring makes every
    CREATE silently POST to the item path instead of the collection.
  - **The suite was validated by planting 12 defects and confirming each fails.** A green
    suite that has never failed is not evidence — the same bar the route fingerprint was held
    to when it was deliberately corrupted.
  - **`--check` now compares write-body schemas, not just routes.** The old check printed
    "Schemas may still have changed" and meant it: Cisco can rename a required field without
    touching a single path, and the first you hear of it is a 400 on a live tenant. 82
    reachable `POST`/`PUT`/`PATCH` bodies are now hashed into `docs/api-fingerprint.json`.
  - **Deliberately narrow on both axes.** Writes only (a drifting response is a visibly odd
    read; a drifting request corrupts a write) and structure only — property names, types,
    enums, required — with descriptions excluded. Verified with four planted mutations: it
    trips on a renamed field and on a body appearing where there was none, and stays quiet on
    a reworded description and on a refused route. **A detector that cries wolf gets muted,
    and a muted detector is worse than none.** `tests/verify_drift_detection.py` keeps that
    negative test runnable.
  - **NEW FINDING: `team`, `skill`, `skill-profile` and `agent-profile` publish NO request
    body at all** for create/update — 8 reachable write ops with nothing to hash. Their
    `create` field lists rest **entirely** on live probing, and schema drift can never cover
    them. Recorded as `(no-body-schema)` so Cisco finally documenting one shows up as drift.
  - **Open work is now tracked in `TODO.md`** rather than scattered across doc prose: the
    live read-only test tier, `entry-point` being the only entity with no registry `note`
    (allowlisted in the suite so the gap is visible, not silent), and the `refusal()`-vs-`note`
    divergence that renders `PATCH agent-personal-greeting/{id}` as a **GAP** when it was in
    fact probed and refused — so the headline gap count overstates the real gaps.

- **2026-07-22 — `agent-personal-greeting`, queue lookups, and the Global Variables skill.**
  Entities **23**, tools **18**, skills **30**. Coverage **210/249**. All verified live.
  - **THE SPEC IS INCOMPLETE, not merely wrong.** Creating a greeting file kept returning a
    nameless `409 "Internal error. Please contact Cisco Support Team"`. The missing field
    was `greetingPurposeId`, and the only way to get one is **`GET v2/greeting-purpose` — a
    route that does not appear anywhere in Cisco's published OpenAPI spec**, which lists
    only `agent-personal-greeting/*`. Until now the spec's failure mode was "says JSON works
    when it does not"; this is a whole route missing. **Absence from the spec is not
    evidence of absence in the API.**
  - **`agent-personal-greeting`** (per-agent greetings, NOT the shared `audio-file` prompts)
    is registered with create/update/delete, all multipart — a JSON body is a bare 500, the
    same lie as `audio-file`. There is **no metadata-only update**: `PATCH` returns the same
    nameless 409, so renaming means re-uploading the audio, and `wxcc_update` now refuses
    without `file_path` rather than letting a rename silently do nothing. Its
    `incoming-references` is **broken exactly like `contact-number`** (400 "specify a valid
    external entity type"), so deletes carry `REFERENCES_NOT_CHECKED`. Item path works with
    and without `v2`; `v3` lists but has no item path.
  - **New `wxcc_find_queues`** answers "which queues does this agent serve?" — six routes,
    because each routing type has its own. **Routing types are not exclusive**, so the tool
    repeats in every response that an empty result from one lookup does not mean the user
    serves no queues. The records are **slim** (`id`, `name`, `routingPattern`); the tool
    passes through what is actually there rather than projecting `queueType`/`channelType`,
    which came back null in the first cut.
  - **Three queue routes refused, each for a stated reason:**
    `fetch-manually-assignable-queues` **404s for all six users tried**, each with a valid
    `ciUserId` from their own record; `fetch-by-grouped-assistant-skill` is **412 "License
    check failed for Suggested responses"**; and `reassign-agents` **cannot be verified
    here at all — this tenant has no agent-based queues**, so it is refused rather than
    shipped untested.
  - **New `wxcc-global-variables`** closes the orphan the generated index found yesterday:
    `cad-variable` had full CRUD and bulk but no skill. Its `variableType` enum publishes
    **every value twice, in two casings** (`STRING` and `String`); the tenant uses
    TitleCase, and whether the two are interchangeable on write is unverified. Global
    variables are **referenced by flows** — and while delete is reference-blocked, **rename
    is not**, so renaming a referenced variable breaks the flow at runtime.
  - **`wxcc_create` now reports every problem at once.** It used to check the file before
    the required fields, so a caller who omitted both fixed one, retried, and was told about
    the next. One flipped test in the audio suite was traced to this deliberate shape change
    (`error` → `needs_file`), not a regression, and the assertion was updated.
- **2026-07-22 — The API reference is now generated, with drift detection.**
  `scripts/build_api_reference.py` fetches Cisco's live spec, merges it with the `ENTITIES`
  registry, and emits three artifacts. Skills reach **28**.
  - **`docs/api-coverage.md`** — every operation with the tool that reaches it, or the
    reason it is refused. **`.claude/skills/wxcc-api-map/SKILL.md`** — a thin index for
    *extending* the project (entity → routes → owning skill) that deliberately restates no
    traps, so there is still one home per fact. **`docs/api-fingerprint.json`** — 26 KB of
    route inventory instead of a 3.5 MB vendored spec.
  - **`--check` names what moved upstream.** Verified by corrupting a fingerprint on
    purpose: it reported the 7 restored `audio-file` routes as additions and the planted
    fake as a removal, exit 1. A clean run against an unchanged spec proves nothing on its
    own, which is why the failing case was tested too.
  - The generator reads `ENTITIES` by **parsing `mcp_server.py` with `ast`**, not importing
    it — a docs build has no business requiring the MCP package or a tenant config.
  - **Two bugs caught during the build, both by the harness rather than by inspection.**
    The generated SKILL.md put its "do not hand-edit" banner *above* the YAML frontmatter,
    so the skill registered with an HTML comment as its description. And the first
    ownership heuristic matched any mention of an entity, so `wxcc-api-map` and `wxcc-bulk`
    — which name every entity by design — looked like the owner of all 22.
  - **The index immediately found a real gap: `cad-variable` (WxCC "Global Variables") has
    NO owning skill.** Full CRUD plus bulk are reachable, but nothing documents them or
    warns about the traps already recorded in its registry note. Ownership is now derived
    from a skill actually *calling* an entity, and anything with only incidental mentions
    is flagged rather than credited to whoever happened to name it.
- **2026-07-22 — Cisco publishes an OpenAPI spec, and it changes how this project works.**
  `webex/webex-openapi-specs` → `public-spec/webex-contact-center.json`: **448 operations,
  327 paths, 756 schemas**, OpenAPI 3.0.0, updated roughly weekly (15 commits since
  2026-06-08, one the same day this was written). Tag counts match the portal screenshots
  exactly, so the two are the same source.
  - **It is a map of what EXISTS, not proof of what WORKS.** The spec declares
    `application/json` as an accepted body for `POST`/`PUT` on `audio-file` — five distinct
    JSON shapes all return 500, and only multipart succeeds. **Where the spec and a live
    probe disagree, the probe wins.** Schema quality is also uneven: `PATCH user/{id}`
    documents its body as `JsonValue` with a single field, which is no documentation at all.
  - **It independently confirmed two findings made by probing**: `audio-file` publishes no
    bulk route, and there is **no `contact-number/{id}/incoming-references` path at all** —
    the defect behind the delete bug fixed earlier today.
  - **`docs/api-coverage.md`** is generated from the spec plus the registry: every operation
    with the tool that reaches it, or the reason it is deliberately refused. Pinned to
    upstream commit `2a282a07cede`. The spec is deliberately **not vendored** — at weekly
    cadence a static copy would be stale within days.
  - Coverage today: **194 of 236** operations on registered entities are reachable. Of the
    42 gaps, 10 are purge (403 tenant-wide), 8 are bulk-export (out of scope), 2 are
    child `entry/bulk` (unprobed), leaving ~22 genuinely unexplored. **22 of 29 config path
    roots are registered**; the unregistered ones are `agent-personal-greeting` (13 ops),
    `ai-feature` (8), `auto-csat` (8), `agent-burnout` (3), `generated-summaries` (3), plus
    `work-type` and `dial-plan`, both already struck as deprecated.
- **2026-07-22 — `user`: a real PATCH, bulk update, and seven lookups. Tools go to 17.**
  Verified live against one designated test user, with a full field baseline captured first
  and **zero drift** at the end.
  - **`wxcc_update` on a user is now a PATCH, not a read-modify-write PUT.** `user` has a
    genuine single-item partial update: changing `agentProfileId` left `teamIds`, `siteId`
    and `userProfileId` untouched. This matters because the user record carries fields the
    API returns on GET but refuses to write — a full PUT has to echo them back, a PATCH never
    mentions them. The body is a plain partial object; JSON-Patch array form returns **500**.
  - **New `wxcc_find_users`** exposes the seven routes `wxcc_list` cannot express:
    `with_profile` (users joined to their profile in one call), `with_profile_by_id`,
    `ci_user_id` (Control Hub id → CC user), `dynamic_skill`, `call_monitoring_id`, `ids`,
    and `skill_requirements`. Bodies were read from the spec rather than guessed:
    `fetch-user-details-by-ids` wants `{userIds:[...]}`, `fetch-by-skill-requirements` wants
    `{skillRequirements:[{skillId}]}`.
  - **`with_profile` returns a BARE LIST** — no envelope, no `totalRecords`, no pagination —
    so the tool flags `UNPAGINATED`: there is no way to know whether the server truncated it.
  - **Bulk update for `user`** on `PATCH user/bulk` (207 + items). No bulk create/delete:
    Control Hub owns the lifecycle.
  - **`PATCH user/{id}/reskill` is NOT exposed:** 403 *"User must have a supervisor profile
    to reskill agents"* — a Supervisor Desktop endpoint. Everything it does is reachable by
    PATCHing `skillProfileId`, which was confirmed to both **assign and clear** (null).
  - **`userLevelAutoCSATInclusion` is silently ignored** on a 200, exactly like
    `userLevelSummariesInclusion`. Two fields now share this behaviour; treat both as
    unwritable until a tenant proves otherwise.
  - **Method lesson that nearly shipped a false all-clear:** the dynamic-skill bulk route
    really did assign a skill to the test user, but **dynamic skills are not fields on the
    user record**, so a field-by-field baseline diff reported "no drift" while the
    assignment was live. It was found by querying `by-dynamic-skill-id` across every skill,
    and removed with `requestAction: DELETE`. **A baseline diff only covers the surface it
    can see** — for anything stored outside the object, the restore check has to query the
    other side.
- **2026-07-22 — `purge-inactive-entities` is 403 TENANT-WIDE, settled on three entities.**
  The Desktop Layout / Desktop Profile endpoint lists contained **no new routes** — every
  one was already registered except purge, the same single gap the aux-code list had. Fired
  against real inactive objects the tenant admin created for the test (one unreferenced,
  non-`systemDefault` `_copy` in each family): `desktop-layout` **403**, `agent-profile`
  **403**, byte-identical to `auxiliary-code`'s, with the control `POST
  agent-profile/notaroute` returning **405** in the framework's `timestamp` shape. The
  routes are real and the gate is authorization, and three entities behaving identically
  makes it **tenant-wide, not per-entity**. Nothing was destroyed — both inactive copies
  survived and both families stayed at 3.
  - The canonical note now lives once, in **wxcc-bulk**; `wxcc-aux-codes`,
    `wxcc-desktop-layouts` and `wxcc-desktop-profiles` point at it instead of restating it.
    This supersedes the `wxcc-desktop-profiles` line calling purge "unprobed".
  - **`desktop-layout`'s active flag is `status`, not `active`** — noticed while enumerating
    what purge would hit. Every other entity uses `active`, so filtering `active=false` on
    layouts silently matches nothing: a filter that looks clean while finding no inactive
    records. Recorded in the registry note and the skill.
- **2026-07-22 — BUG: `wxcc_delete` could never delete a `contact-number`, and the registry
  claimed it could.** Found while writing skills for the scheduling group. `GET
  contact-number/{id}/incoming-references` answers **400 "specify a valid external entity
  type"** for a valid id, a bogus id, and every `?type=` tried (user, team, flow, site,
  contact-number, agent-profile) — the route simply does not work for this entity.
  `_find_references` correctly refuses to let a failed scan read as "clean" and returns a
  `scan_failed` marker, but `wxcc_delete` counted every returned element as a conflicting
  reference. Net effect: the tool reported *"1 object(s) still reference this"* when nothing
  did, and **the delete was unreachable**. The prior "verified delete round trip" for this
  entity must have gone through the raw CLI, not the tool.
  - **Fix:** a registry flag `no_incoming_references` marks an entity whose scan route does
    not exist. `wxcc_delete` then skips the pre-flight and returns `REFERENCES_NOT_CHECKED`
    stating plainly that nothing was checked and that only the API's own 412 remains — a
    backstop confirmed for other entities and **unconfirmed for this one**. `wxcc_references`
    returns `SCAN_IMPOSSIBLE` with `total: null` rather than an empty list, because "nobody
    can tell you" must never render as "nothing points here."
  - **Regression-checked:** entities with a working scan are unchanged — `holiday-list` still
    blocks with its three real referents named, and an unreferenced `business-hours` dry run
    still reports `no_blocking_references` with no spurious warning.
- **2026-07-22 — Skills for the scheduling family and contact numbers; no new endpoints.**
  Skills reach **27**. Diffing the portal's endpoint list against the registry found **zero
  gaps**: all 21 Business Hours / Holiday List / Overrides routes and all of Contact
  Number's were already registered (2026-07-21), so the work was documentation plus the
  delete bug above. `contact-number/all-numbers` stays unexposed (bare strings, no ids) and
  bulk-export is out of scope.
  - **New `wxcc-business-hours`** covers all three interlocking entities. New facts probed
    today: **`business-hours.overridesId` is a second real reference** (→ `overrides`), and a
    record with no holiday or override binding simply **omits the key** — this API drops
    unset fields rather than returning null, so a missing key is not a list/item discrepancy
    (checked per record; list and item agree on all three). **Business hours are referenced
    by flows** — the sandbox's `StandardCallFlow` binds `Standard_Working_Hours` — so an
    hours edit changes live routing.
  - **Holiday recurrence rules, probed:** `frequency` is OPTIONAL (omit for a one-off);
    `Yearly` requires `recurrence.specificMonth`; `Monthly` requires **either**
    `specificDayOfMonth` **or** `occurrenceInTheMonth`; `Weekly` takes `daysOfWeek`. There is
    no `"None"` value — `frequency:"None"` is a deserialize error.
  - **Name charset is enforced tenant-wide** on all three: alphanumerics, space, `_`, `-`
    only; `.`, `+` and `/` each 400. Worth recording because it cost a wasted probe round —
    three "recurrence" failures were actually the validator rejecting the *test label* I had
    put in `name`, which briefly looked like a recurrence rule that does not exist.
  - **New `wxcc-contact-numbers`** documents the 9-character cap, the absence of any
    `name`/`description` field, the `all-numbers` projection trap, and the broken reference
    scan above.
- **2026-07-22 — `audio-file`: the first entity that takes a file, and the first with a real
  single-item PATCH.** Registry goes to **22 entities**, skills to **25**. Verified live on
  the sandbox 2026-07-22 through a full create / read / patch / multipart-put / references /
  delete round trip; every probe object was deleted and the count swept back to 11.
  - **Multipart is the ONLY way in, and the portal says otherwise.** Cisco's schema documents
    the create body as "either application/json or multipart/form-data". **The JSON half is
    false** — five distinct JSON shapes (bare fields, the documented
    `{audioFileInfo, audioFile}` envelope, base64 in `audioFile`, base64 in both places, the
    literal `"string"` placeholder) all return a bare **500**, as does a JSON `PUT`. The
    working shape is two parts: `audioFile` (bytes, with a filename and its own content type)
    and `audioFileInfo` (metadata JSON that **must** declare `Content-Type: application/json`
    — omit that header and the request is **415**, omit the part and it is **400**).
    Consequence for method: **the probe-an-empty-body-and-read-the-400 technique that mapped
    the other 21 entities cannot work here** — it returns a 500 that names nothing.
  - **`PUT` demands the record's OWN `blobId`**, and it is an ownership token rather than a
    selector: omitting it is `400 "blobId: invalid value"`, and passing *another* record's
    blobId is the same 400 (tested — record unchanged). The blob is overwritten **in place**,
    so **blobId does not rotate on replace**.
  - **A replace cannot be verified, and the tools now say so.** There is no download route —
    the DTO documents a `url` field that **no** sandbox record returns, and `.../content` and
    `.../download` 404. So after any audio replacement `wxcc_update` returns
    `AUDIO_NOT_VERIFIABLE` and the dry run returns `ALSO_REPLACES_AUDIO` warning that the old
    audio is unrecoverable. Only playback in Control Hub can confirm a replace.
  - **Upload is local-only by design.** `wxcc_create`/`wxcc_update` take `file_path`, an
    absolute path on the machine running the server. The cloud servers share no filesystem
    with the caller, so they refuse the upload with an explanation and point at the local
    server; every other audio-file operation works on both.
  - **`contentType` has two live spellings for the same thing** — `AUDIO_WAV` and
    `AUDIO_X_WAV` both occur among the 11 sandbox records, so neither is "the" correct value.
  - **Cisco doc bug, recorded so nobody re-derives meaning from it:** the schema describes
    `audio-file.description` as *"a short description of the dial plan"* — a copy-paste from
    a different, deprecated entity.
  - `wxcc.py` gains `multipart_body()` and `WxccClient.upload()`; `_request` gained a `raw`
    parameter so a non-JSON body can be sent. Existing callers are untouched.
- **2026-07-22 — `auxiliary-code` purge: route exists, 403s, deliberately NOT exposed.**
  `POST auxiliary-code/purge-inactive-entities` is real — it answers **403 "Access denied"**
  with the app's `trackingId` error shape, where a nonexistent sub-path answers **405** with
  the framework's `timestamp` shape. It 403s for a **full-rights tenant admin** holding
  `cjp:config_write`, and the required scope is undocumented. Rather than ship a destructive
  tool nobody can call, the skill now routes "delete all the inactive codes" through
  list → filter `active=false` in code → `wxcc_bulk_delete`, which is aimable at exactly the
  codes the user chose. The remaining aux-code endpoints in Cisco's list were **already
  shipped** — only purge was a gap, and bulk-export is out of scope.
  - **Method note:** the first control batch for this probe would have fired
    `purge-inactive-entities` at `agent-profile` and `team` as "controls" — two more
    mass-destructive calls on entity families nobody had authorized. A guardrail caught it.
    The only safe control for a destructive route is a **harmless sibling path on the same
    entity**, never the same destructive route aimed somewhere else.

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
