---
name: wxcc-webhooks
description: Use when asked about Webex Contact Center webhooks, event subscriptions, or event push - "what events can I subscribe to", "send task events to my server", "list/create/update/delete webhook subscriptions", "why isn't my webhook firing". Writes require explicit user confirmation; updates use PATCH, not PUT.
---

# wxcc-webhooks — event subscriptions (read + write)

Call **`wxcc_webhooks`** on the server for the tenant the user named.
**If no tenant was named, ask — do not guess.**

```
wxcc_webhooks(action="list_event_types")     # the catalog: what you can subscribe to
wxcc_webhooks(action="list")                 # existing subscriptions
wxcc_webhooks(action="create", body={...})   # dry run unless confirm=true
wxcc_webhooks(action="update", subscription_id="...", body={...})
wxcc_webhooks(action="delete", subscription_id="...")
```

`create` / `update` / `delete` return a **dry run** unless you pass `confirm=true`. Show the
user what would be sent — **especially the URL** — and get an explicit yes first.

## Use when / Do NOT use when

**Use when:** browsing event types, or managing subscriptions that push WxCC events to an
external endpoint.

**Do NOT use when:**
- Auth errors → **wxcc-connect**.
- Querying past interactions → **wxcc-tasks-search**. Webhooks are push, for events from
  now on; they cannot backfill history.
- Tenant configuration → the entity skills.

## The one that matters: `destinationUrl` is never validated

**WxCC does not check that the URL is reachable, yours, or even real.** A typo means your
contact-center events — customer phone numbers, agent activity — are quietly POSTed to a
stranger's server, forever, with no error anywhere.

So: **read the exact URL back to the user before creating**, character for character. This
is the one place in this repo where a silent success is worse than a failure.

## Rules worth knowing

| Item | Detail |
|---|---|
| **Update is PATCH**, not PUT | Unlike every other entity here. The tool handles it (and `wxcc.py` grew a `patch` verb for it). |
| Limit | **20 subscriptions per org** |
| `secret` | **Write-only** — never echoed back. If it is lost, rotate it; you cannot read it. |
| Host-root API | `v1/subscriptions`, `v1/event-types` — not under `organization/{orgId}`. The tool handles this. |
| Event types | 27 as of 2026-07-11 — read them with `list_event_types` rather than guessing a name |

## Delivery behavior — unverified

**The payload shape, retry policy, and signature/secret verification have never been
observed here** — that needs a real receiving endpoint, which the probe did not have. If the
user asks "what will my server receive?", say it is unverified and point them at Cisco's
docs, or stand up a receiver and find out. Do not describe a payload you have not seen.

"Why isn't my webhook firing?" is therefore mostly unanswerable from this side. What you
*can* check: the subscription exists (`action="list"`), the event type is spelled exactly as
`list_event_types` returns it, and the org is the one you think it is (`wxcc_whoami`).

## Provenance and maintenance

Event-type catalog and subscription create/PATCH/delete run live on a us1 sandbox
2026-07-11 (subscription created and removed; baseline 0 restored). The 20/org limit and the
write-only secret are documented by Cisco; the unvalidated `destinationUrl` was observed
directly. Delivery payload and signing remain unverified.
