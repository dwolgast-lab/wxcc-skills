# wxcc-skills

A library of [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills) for administering a **Webex Contact Center (WxCC)** tenant through natural-language prompts.

Each skill is a runbook that teaches Claude how to perform a specific class of WxCC administrative task — reading and mutating tenant configuration (users/agents, teams, queues, sites, entry points, skills, and so on) against the Webex Contact Center REST APIs.

## Status

Foundation in place: a shared helper (`wxcc.py`) plus read-only skills — `wxcc-connect`
(OAuth setup/verify), `wxcc-users`, `wxcc-teams`, `wxcc-queues`, `wxcc-sites`,
`wxcc-entry-points` (incl. dial numbers), `wxcc-skill-profiles` (incl. routing skills).
Write operations come next.

**Architecture:** skills call a thin shared Python helper (`wxcc.py`, stdlib only) that owns
OAuth, token storage/refresh, org-id resolution, and authenticated requests. Auth is an
**OAuth Integration** (user-context, authorization-code flow). Longer term this helper is
intended to graduate into an MCP server.

Verified end-to-end against a live us1 tenant (2026-07-10): consent flow, token storage,
orgId auto-derivation, and an authenticated List Users read. Responses paginate via
`meta.page`/`pageSize` (default 100) with `meta.links.next`; records are in `data[]`.

**Convention:** pass API paths to `wxcc.py get` **without a leading slash**
(`organization/{orgId}/v2/user`) — Git Bash rewrites leading-slash arguments into
filesystem paths.

**New here? Start with the [User Guide](docs/user-guide.md)** — what it does, setup, the
safety model, and the full skill catalog.

## Quick start

Load the **wxcc-connect** skill (or read `.claude/skills/wxcc-connect/SKILL.md`) and follow
it: register an OAuth Integration at developer.webex.com, copy `.env.example` → `.env`, run
`python wxcc.py auth login`, then verify with `python wxcc.py auth status`.

## Layout

```text
wxcc.py                                # shared helper CLI (auth + GET/POST/PUT/DELETE)
.env.example                           # config template (copy to gitignored .env)
.claude/skills/<skill-name>/SKILL.md   # individual skills (Claude loads these)
CHANGELOG.md                           # dated log of notable changes
docs/                                  # user guide (md = source of truth, pdf = export)
scripts/build_user_guide_pdf.py        # regenerates the guide PDF (markdown + Chrome)
hooks/pre-commit                       # auto-rebuilds the PDF when the guide is committed
```

The guide PDF regenerates automatically on commit. One-time setup per clone:
`git config core.hooksPath hooks` (needs `pip install markdown` and Chrome or Edge).

## Safety

- API tokens and credentials must **never** be committed. See `.gitignore`.
- Administrative operations are mutating and often hard to reverse. Skills that
  change tenant state must confirm before writing and state how to roll back.
