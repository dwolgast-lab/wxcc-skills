# TODO

Open work, with the reason it matters. Anything struck as *decided* belongs in
`docs/api-coverage.md` (generated) or the entity's registry `note`, not here.

Ordered by what breaks if it is left undone.

---

## Verification

- [ ] **Live read-only test tier.** `tests/test_registry.py` proves the registry is
      internally consistent; it cannot prove a path still exists upstream. Add a
      tenant-backed tier that, for all 23 entities, runs list → get → references and
      asserts each reaches the exact path the registry claims. Sandbox only, no writes.
      *Why:* every "verified live" claim in the CHANGELOG is a one-time manual probe.
      Nothing re-runs them, so a path that moves is discovered by a failing write.

- [x] ~~**`team`, `skill`, `skill-profile`, `agent-profile` publish NO request-body
      schema**, so schema-drift can never cover them.~~ **WRONG, corrected 2026-07-26.**
      They declare no `requestBody`, but the object is a fully-schema'd **required query
      parameter** — `?teamDTO=`, `?payloadDTO=`, `?skillProfileDTO=`, `?agentProfileDTO=`
      (not even consistently named). The detector hashed only request bodies, so it
      skipped create AND update on four core entities. Fixed: it now hashes the whole
      declared payload (body **and** required non-path params), taking coverage from
      74/82 to **82/82 with no sentinels**. Note the tools send a JSON *body* to these
      routes and get 201/200 — the API accepts both forms; the spec documents only one.

- [ ] **Webhook delivery payload + signing still unverified.** Needs a real receiving
      endpoint. *Deferred deliberately (2026-07-25): build a test scenario first —
      there is no good one yet.* The homelab (NGINX + LetsEncrypt on `fwnet.us`) is the
      intended receiver when that scenario exists.

## MCP 2026-07-28 spec revision — ✅ ADOPTED 2026-08-01

`requirements.txt` is now `mcp==2.0.0` (`LATEST_PROTOCOL_VERSION = 2026-07-28`). Both
items previously held here as blocking were validated on a real wire and are closed; the
detail is in `CHANGELOG.md` under 2026-08-01. Summary of what was settled, so nobody
re-derives it: the SDK supplies `ttlMs`/`cacheScope` defaults itself, `ExpectedOrgGuard`
is transparent to the new headers *and* still rejects a wrong tenant through both the
`?org=` and header forms, and a legacy 2025-11-25 client is still served by negotiating
down (confirmed over HTTP and over real stdio).

The 2026-07-27 assessment's one real miss, worth remembering as a method lesson: it cleared
the revision from the **spec changelog** without importing the SDK, and so did not see that
`mcp.server.fastmcp` is gone in 2.x. Spec-level reasoning does not catch packaging changes.

**Both hosts are on `mcp==2.0.0` as of 2026-08-01** and each was verified by a live read, not by
a version string: the laptop via a real stdio `wxcc_whoami`, and forge over the real
`ssh → docker run -i` path for all three profiles, each resolving to its own distinct org.
The drift that motivated the exact pin (laptop 1.28.1 vs forge 1.29.0) is closed.

Left over, neither blocking:

- [ ] **`serverInfo.version` is now `""`** (`MCPServer(version=...)` defaults empty where
      FastMCP reported the SDK version). Nothing consumes it, and the stale sentence in
      `docs/forge-deployment.md` has been corrected — but passing a real version string
      would be better than shipping an empty one.

- [ ] **Cloud Run is the third host.** It builds from the same `Dockerfile`/`requirements.txt`,
      so it takes 2.0.0 on its next deploy. Unlike stdio, it exercises `mcp_http.py` —
      `ExpectedOrgGuard`, `WebexTokenVerifier` and the `AnyHttpUrl` change — against real
      clients. Those were verified locally (see CHANGELOG 2026-08-01) but a post-deploy
      smoke test against the live URL is still worth doing.

## Correctness

- [ ] **`entry-point` is the only entity with no registry `note`.** 22 of 23 carry
      their probe findings; this one never got one. Currently allowlisted in
      `tests/test_registry.py::NOTE_OPTIONAL` so the gap is visible rather than silent.
      Close it and drop it from the allowlist.

- [ ] **Probed-and-refused routes render as `GAP`.** `refusal()` in
      `scripts/build_api_reference.py` is a hand-maintained `if` ladder; the registry
      `note` is prose the generator cannot parse. They have already diverged:
      `PATCH agent-personal-greeting/{id}` is recorded in the note as a nameless 409
      (probed, decided) but shows as **GAP** in `docs/api-coverage.md`. So the headline
      gap count overstates the real gaps. *Fix:* give the registry a structured
      `refused: {route: reason}` key the generator reads, so there is one home per fact.

- [ ] **`payload_hash` silently ignores OpenAPI payload forms it does not handle.**
      It reads only inline, operation-level `parameters` and an inline
      `requestBody.content["application/json"]`. Four other legal forms would be
      dropped **with no signal at all**: path-item-level `parameters`, a `$ref`'d
      parameter, a `$ref`'d `requestBody`, and a parameter carrying `content` instead
      of `schema`. *Not a defect today* — measured against the live spec 2026-07-27,
      all four occur **zero** times anywhere in the document, and zero times on the 82
      tracked write ops; the fingerprint has no sentinels. But this is a detector whose
      entire job is catching change nobody announced, and the failure mode is silence,
      not a sentinel. *Fix:* run `_deref` (it already exists) over parameters and
      `requestBody`, merge path-item `parameters`, and — more important than any of
      that — make an unrecognised payload form return a **distinct** marker rather than
      `NO_PAYLOAD`, so "I found nothing" and "I did not understand this" stop looking
      alike. Raised by an external review; the review filed it as blocking, which the
      measurement does not support.

- [ ] **`wxcc.py::extract_org_id` docstring says "UNVERIFIED against a live tenant."**
      It is verified — two profiles on distinct orgs both return HTTP 200 on a derived
      org id (2026-07-25), and a wrong id would 404/403. The function is load-bearing
      for the `{orgId}` path, the profile-collision guard, `WXCC_ALLOWED_ORGS`, and the
      cloud wrong-tenant guard. Leaving "UNVERIFIED" on it invites someone to work
      around it.

- [x] ~~**Two pre-existing pyright errors in `mcp_http.py:105-106`** — `AuthSettings` wants
      `AnyHttpUrl` and gets `str` for `issuer_url` / `resource_server_url`.~~ **Done
      2026-08-01** during the MCP 2.0 migration, as intended — same constructor. Both are
      now wrapped in `AnyHttpUrl(...)`. Whole-project pyright baseline is **0 errors**
      (1 warning: `markdown` unresolved in `scripts/build_user_guide_pdf.py`).

- [ ] **`mcp_http.py::ExpectedOrgGuard` fails open on an unparseable token.** The check
      is `if actual and actual != expected` — a token whose org cannot be derived yields
      `actual = None` and passes the middleware unguarded. `verify_token` rejects it a
      layer later, so this is not believed exploitable, but a guard that opens when it
      cannot parse its input is the wrong default here.

## Coverage

- [ ] **`*/delete-reference`** (`contact-service-queue`, `agent-personal-greeting`) —
      both GAP. Deletes are reference-blocked and hand back a list of what to fix; these
      endpoints *are* the automated fix. Note the published doc for the
      `agent-personal-greeting` one is copy-pasted from a queue endpoint and contradicts
      its own summary — probe before wiring.

- [ ] **`cad-variable/reportable-count`** — GAP. Semantics already confirmed (counts
      `reportable AND active`); WxCC caps how many globals may be reportable and the cap
      value is still unknown. Design choice deferred: dedicated tool vs a registry
      `extras` key folded into `wxcc_list`.

- [ ] **`v3/user-profile/{id}/acl`** — GAP. What a profile actually resolves to, versus
      what it claims.

- [ ] **Unregistered config roots:** `agent-burnout`, `ai-feature`, `auto-csat`,
      `generated-summaries`. Expected to be entitlement-gated (cf.
      `fetch-by-grouped-assistant-skill` → 412 "License check failed"), but that is
      inferred — one `GET v2/ai-feature` settles it.
      *`work-type` and `dial-plan` are struck as deprecated — do not re-litigate.*

---

## Running the gates

```bash
python -m unittest discover tests -v     # offline; no tenant, no token, no deps
python scripts/build_api_reference.py --check   # routes + write PAYLOAD schemas vs upstream
python tests/verify_drift_detection.py   # proves --check still detects planted drift
```
