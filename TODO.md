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

- [ ] **`team`, `skill`, `skill-profile`, `agent-profile` publish NO request-body
      schema** for create/update — 8 reachable write ops with nothing to hash
      (`(no-body-schema)` in `docs/api-fingerprint.json`). Their `create` field lists
      rest entirely on live probing and **schema-drift detection can never cover them**.
      These four need the live tier more than any other entity.

- [ ] **Webhook delivery payload + signing still unverified.** Needs a real receiving
      endpoint. *Deferred deliberately (2026-07-25): build a test scenario first —
      there is no good one yet.* The homelab (NGINX + LetsEncrypt on `fwnet.us`) is the
      intended receiver when that scenario exists.

## MCP 2026-07-28 spec revision

Ships 2026-07-28; SDK support is in the **2.x** line (`2.0.0rc1` on PyPI 2026-07-26).
`requirements.txt` is pinned `mcp>=1.28,<2` so the upgrade is a decision, not a drift.
Installed today: `mcp 1.28.1`, `LATEST_PROTOCOL_VERSION = 2025-11-25`.

**Not urgent.** The revision keeps explicit back-compat — `server/discover` doubles as a
stdio back-compat probe, and clients MUST treat results omitting `resultType` as
`"complete"`. So today's servers should keep working against new clients that negotiate
down. *Inferred from the changelog's own provisions; not tested against a real RC client.*

Most of the revision costs this project nothing, and that is worth knowing before anyone
panics about it: `stateless_http = True` is already set, the transport is already
`streamable_http_app()` (HTTP+SSE is now Deprecated), the server registers **18 tools and
nothing else** — no resources, prompts, sampling, elicitation, roots, logging or progress —
so the Roots/Sampling/Logging deprecations and the whole Multi Round-Trip Requests redesign
are inapplicable. Authorization hardening (`iss` validation, `application_type`, credentials
keyed by issuer) is client-side; we are a resource server. DCR being deprecated in favour of
Client ID Metadata Documents does not apply either — we use a manually-registered Webex
Integration, never DCR.

Two things to actually validate when taking the 2.x upgrade:

- [ ] **`ttlMs` / `cacheScope` are now required** on `tools/list` results (new
      `CacheableResult` interface). Whether the 2.x SDK supplies defaults or the app must
      set them per tool is **unverified** — check against the beta before upgrading.

- [ ] **`Mcp-Method` / `Mcp-Name` become required headers** on Streamable HTTP POSTs, and
      servers must reject requests whose headers and body disagree (`HeaderMismatchError`,
      `-32020`). **`ExpectedOrgGuard` is custom ASGI middleware in exactly that layer**
      (`mcp_http.py:127-190`). Reading it, it only inspects `authorization`,
      `x-wxcc-expected-org` and `?org=` and passes everything through untouched, so it
      *should* stay transparent — but that is inferred from reading, not tested. Put it on
      a real wire before trusting it. The wrong-tenant guard is the one piece of safety
      machinery here that has no fallback if it silently stops firing.

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

- [ ] **`wxcc.py::extract_org_id` docstring says "UNVERIFIED against a live tenant."**
      It is verified — two profiles on distinct orgs both return HTTP 200 on a derived
      org id (2026-07-25), and a wrong id would 404/403. The function is load-bearing
      for the `{orgId}` path, the profile-collision guard, `WXCC_ALLOWED_ORGS`, and the
      cloud wrong-tenant guard. Leaving "UNVERIFIED" on it invites someone to work
      around it.

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
python scripts/build_api_reference.py --check   # routes + write-body schemas vs upstream
python tests/verify_drift_detection.py   # proves --check still detects planted drift
```
