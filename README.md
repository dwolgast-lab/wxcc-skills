# wxcc-skills

A library of [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills) for administering a **Webex Contact Center (WxCC)** tenant through natural-language prompts.

Each skill is a runbook that teaches Claude how to perform a specific class of WxCC administrative task — reading and mutating tenant configuration (users/agents, teams, queues, sites, entry points, skills, and so on) against the Webex Contact Center REST APIs.

## Status

Foundation in place: a shared helper (`wxcc.py`) and the first skill (`wxcc-connect`) that
sets up and verifies OAuth access. Domain admin skills (users, teams, queues, …) come next.

**Architecture:** skills call a thin shared Python helper (`wxcc.py`, stdlib only) that owns
OAuth, token storage/refresh, org-id resolution, and authenticated requests. Auth is an
**OAuth Integration** (user-context, authorization-code flow). Longer term this helper is
intended to graduate into an MCP server.

Not yet verified end-to-end against a live tenant: the `auth login` consent round-trip and
the orgId-from-token derivation. See `wxcc-connect`.

## Quick start

Load the **wxcc-connect** skill (or read `.claude/skills/wxcc-connect/SKILL.md`) and follow
it: register an OAuth Integration at developer.webex.com, copy `.env.example` → `.env`, run
`python wxcc.py auth login`, then verify with `python wxcc.py auth status`.

## Layout

```
wxcc.py                                # shared helper CLI (auth + authenticated GET)
.env.example                           # config template (copy to gitignored .env)
.claude/skills/<skill-name>/SKILL.md   # individual skills (Claude loads these)
```

## Safety

- API tokens and credentials must **never** be committed. See `.gitignore`.
- Administrative operations are mutating and often hard to reverse. Skills that
  change tenant state must confirm before writing and state how to roll back.
