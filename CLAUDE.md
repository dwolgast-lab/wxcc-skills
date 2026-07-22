# wxcc-skills — working notes for Claude

## Tenants: never guess which one

Every tenant is a **profile** (`WXCC_PROFILE`) with its own `.env.<profile>` and its own
token store. There is deliberately **no "switch tenant" command** — a mutable current-tenant
pointer is how a delete meant for sandbox lands on production.

Each tenant gets **its own MCP server**, so the tenant is part of the tool name
(`mcp__wxcc-sandbox__wxcc_delete` vs `mcp__wxcc-gold__wxcc_delete`). Acting on the wrong
tenant therefore requires calling a differently-named tool — it cannot happen silently.

**People refer to tenants by nicknames, not profile names.** The mapping of nickname →
profile is customer-confidential (it names real customers), so it lives in a gitignored
file rather than in this public repo:

@.claude/tenants.local.md

If that import is empty or missing, **ask which tenant is meant. Do not guess**, and do not
infer a tenant from a name you have not been told. Confirm with `wxcc_whoami`, which reports
the tenant label and the resolved `org_id`.

## The trap that has already bitten twice

Authenticating a second profile while the browser still holds a Webex session silently
re-mints a token for the **first** tenant — and it looks like it worked. `wxcc.py` now sends
`prompt=login` and refuses a login whose org collides with another profile, but if you ever
see two profiles reporting the same `org_id`, **stop and treat it as the wrong tenant.**

## Writes

Reads are free. Writes confirm first, state a rollback, and are verified by a re-read —
this API can return 200 while silently ignoring a field. The MCP write tools enforce this:
`confirm=false` is a dry run, deletes pre-flight references and block with a conflict list.

## The API reference is generated, not written

Cisco publishes an OpenAPI spec for WxCC. Three artifacts are derived from it plus the
`ENTITIES` registry — **never hand-edit them**, re-run the script:

```powershell
python scripts/build_api_reference.py           # regenerate all three
python scripts/build_api_reference.py --check   # did the published API move?
```

- `docs/api-coverage.md` — every operation, and either the tool that reaches it or the
  reason it is deliberately refused. Gets a PDF via the pre-commit hook.
- `.claude/skills/wxcc-api-map/SKILL.md` — thin index for *extending* this project:
  entity → routes → which skill owns the detail. It deliberately restates no traps.
- `docs/api-fingerprint.json` — the route inventory, so `--check` can name what upstream
  added or removed. The spec itself is **not vendored**: it changes about weekly, so a
  static copy would be stale within days.

**The spec maps what exists, not what works** — it claims `audio-file` accepts JSON, and
it does not. Where the spec and a live probe disagree, the probe wins, and the probe's
finding belongs in the entity's `note`.

## Flows are out of scope

Cisco ships its own `flow-store` MCP server for flow authoring. Do not build flow tools.
This project owns the config that flows bind to: entry points, queues, teams, skill profiles.
