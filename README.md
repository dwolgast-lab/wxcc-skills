# wxcc-skills

A library of [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills) for administering a **Webex Contact Center (WxCC)** tenant through natural-language prompts.

Each skill is a runbook that teaches Claude how to perform a specific class of WxCC administrative task — reading and mutating tenant configuration (users/agents, teams, queues, sites, entry points, skills, and so on) against the Webex Contact Center REST APIs.

## Status

Scaffold only. No skills authored yet. Architecture (auth model + how skills invoke the API) is being decided before the first skill is written.

## Layout

```
.claude/skills/<skill-name>/SKILL.md   # individual skills (Claude loads these)
```

## Safety

- API tokens and credentials must **never** be committed. See `.gitignore`.
- Administrative operations are mutating and often hard to reverse. Skills that
  change tenant state must confirm before writing and state how to roll back.
