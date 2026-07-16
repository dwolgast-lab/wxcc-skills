# wxcc-skills

MCP tools and [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills) for
administering a **Webex Contact Center (WxCC)** tenant through natural-language prompts.

Ask for what you want — "create a team called Billing on the Denver site", "which entry
point does +1 719 555 0100 route to?", "raise queue X's service level to 30 seconds" — and
Claude calls verified WxCC Admin APIs on your behalf.

## Status

An **MCP server** (8 tools over 13 config entities) plus **19 skills** that route to it.
Every recipe was run against a live tenant before it was written down; anything unverified
is labeled a *candidate*. Runs locally over stdio, or on **Cloud Run** where the server
holds no credentials at all and each caller authenticates as themselves.

**New here? Start with the [User Guide](docs/user-guide.md)** — setup from scratch, the
safety model, multi-tenant, and the honest list of limits.

## Why it's built this way

**Writes are mechanically gated, not politely requested.** A write call without `confirm`
returns a dry run — the tenant, a field-level diff, and the rollback — and writes nothing.
A confirmed write **re-reads and diffs**, because this API can return `200` while silently
ignoring a field. Deletes pre-flight references and refuse with a list of what to fix.

**Every result names the tenant it came from** — pulled from the tenant's own record, not a
configured label, and tagged `[PRODUCTION]` or `[trial/sandbox]`.

**One MCP server per tenant, so the tenant is part of the tool name.** There is deliberately
no "switch tenant" command: a mutable current-tenant pointer is how a delete meant for
sandbox lands on production.

**Facts live in code, judgement lives in skills.** Which paths drop `v2`, which fields a
create requires, which deletes get reference-blocked — those are enforced by the entity
registry rather than hoped for. Skills carry when-to-use and the traps you still control.

## Quick start

```bash
git clone https://github.com/dwolgast-lab/wxcc-skills && cd wxcc-skills
pip install -r requirements.txt
cp .env.example .env          # add your Integration's client id/secret + region host
python wxcc.py auth login     # open the printed URL in a PRIVATE window
python wxcc.py auth status    # confirm the org id is the tenant you meant
cp .mcp.json.example .mcp.json
claude                        # approve the project MCP server, then /exit and restart
```

Then ask Claude to **"run wxcc_whoami"**. Full walkthrough, including the browser-session
trap that will otherwise authenticate you to the wrong tenant:
**[User Guide](docs/user-guide.md)**.

## Layout

```text
wxcc.py                                # OAuth + tokens + requests (stdlib only)
mcp_server.py                          # MCP tools + the entity registry
mcp_http.py, Dockerfile                # Cloud Run deployment (per-caller OAuth)
.env.example, .mcp.json.example        # copy these; the real ones are gitignored
.claude/skills/<name>/SKILL.md         # 19 skills
docs/                                  # user guide (md = source, pdf = export)
CHANGELOG.md
```

`wxcc.py` stays dependency-free on purpose — the CLI works with a bare Python install, and
only the MCP server needs `requirements.txt`.

The guide PDF regenerates on commit: `git config core.hooksPath hooks`
(needs `pip install markdown` and Chrome or Edge).

## Scope

**Flows are out of scope, by design.** Cisco ships its own `flow-store` MCP server for flow
authoring — run it alongside this one. This repo owns the config that flows bind to: entry
points, queues, teams, skill profiles.

## Safety

- Tokens and credentials are **never** committed. `.env*`, `.wxcc/`, and `.mcp.json` are
  gitignored — the last because server names tend to be real customer names.
- Administrative operations are mutating and often hard to reverse. The tools enforce
  dry-run → confirm → verify; skills state the rollback before anything runs.
