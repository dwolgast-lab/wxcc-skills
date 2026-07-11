# Changelog

Notable changes to the wxcc-skills library. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); entries are dated, newest first.

## Unreleased

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
