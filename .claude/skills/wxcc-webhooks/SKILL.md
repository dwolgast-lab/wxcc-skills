---
name: wxcc-webhooks
description: Use when asked about Webex Contact Center webhooks, event subscriptions, or event push - "what events can I subscribe to", "send task events to my server", "list/create/update/delete webhook subscriptions", "why isn't my webhook firing". Covers /v1/event-types (read) and /v1/subscriptions CRUD. Writes require explicit user confirmation; updates use PATCH, not PUT.
---

# wxcc-webhooks — event subscriptions (webhooks)

WxCC pushes agent/task/capture events to an HTTPS endpoint you register as a
*subscription*. Endpoints: `v1/event-types` (catalog) and `v1/subscriptions` (CRUD) —
both at the **API host root**, not under `organization/{orgId}`. Full lifecycle verified
against a live tenant on 2026-07-11 (create 201, PATCH 200, delete 204).

## Use when / Do NOT use when

**Use when:** listing available event types, or listing/creating/updating/deleting
event subscriptions.

**Do NOT use when:**
- Querying the interaction data itself → **wxcc-tasks-search**.
- Building/hosting the receiving endpoint → outside this API's scope entirely.
- Auth errors → **wxcc-connect**.

## Safety rules

Confirm before create/update/delete (**wxcc-teams-write** rules). Extra care: a
subscription starts delivering **real tenant event data** (caller numbers, agent
activity) to `destinationUrl` immediately — creating one with a wrong or third-party URL
leaks data. The API does **not** verify the URL is reachable or yours (confirmed live:
a dummy URL created fine).

## Recipes

### What events exist?

```bash
python wxcc.py get "v1/event-types"
```

→ 27 types observed live (2026-07-11): `agent:login|logout|state_change|
channel_state_change|channelType_state_change`, `task:new|parked|connect|connected|
failed|ended|on-hold|hold-done|consulting|consult-done|conferencing|conference-done|
join-conference|exit-conference|conference-transferred|customer-left|owner-changed|
primary-owner-left|origin-updated`, `capture:available`, `campaign:contact-disposition`,
`flow:error`.

### List subscriptions

```bash
python wxcc.py get "v1/subscriptions"
```

→ `data[]` plus `meta.subscriptionLimit` (20 per org, observed) and `subscriptionCount`.

### Create a subscription

```bash
python wxcc.py post "v1/subscriptions" --body '{"name":"SUB-NAME","description":"...","eventTypes":["task:ended"],"destinationUrl":"https://your-server.example.com/hook","secret":"a-32-plus-character-shared-secret....","orgId":"{orgId}"}'
```

→ verify: HTTP 201, `status: "active"`; **capture `id`**. The `secret` is **not echoed
back** in any response — store it; your receiver uses it to authenticate deliveries
(Cisco guidance says 32+ chars; length enforcement untested here). `orgId` goes **in the
body** (the `{orgId}` placeholder substitutes there too).

### Update a subscription — PATCH, not PUT

```bash
python wxcc.py patch "v1/subscriptions/SUB-ID" --body '{"description":"...","eventTypes":["task:ended"],"destinationUrl":"https://your-server.example.com/hook","status":"active","secret":"...same-or-new-secret...","orgId":"{orgId}"}'
```

→ verify: HTTP 200 echoes the updated object (verified live with a description change).
Rollback = PATCH the captured prior values back. `status` toggles delivery
(`active`/other values untested — candidate).

### Delete a subscription

```bash
python wxcc.py delete "v1/subscriptions/SUB-ID"
```

→ verify: HTTP 204, `subscriptionCount` back down in the list. Recreating is cheap
(unlike config entities, nothing else references a subscription id).

## Traps (observed live, 2026-07-11)

| Item | Detail |
|---|---|
| Update verb | **PATCH** — `wxcc.py patch` (PUT untested against this path) |
| `destinationUrl` unvalidated | 201 even for unreachable/dummy URLs — typos fail silently at delivery time |
| Secret write-only | Never returned by GET/POST/PATCH responses — capture at creation |
| Paths are host-root | `v1/subscriptions`, not `organization/{orgId}/...`; org binding is the body's `orgId` |
| Event payload shape | Not observable via this API — verify against a real receiver (candidate) |

## Provenance and maintenance

Lifecycle run live on a us1 sandbox 2026-07-11 (201 → PATCH 200 → 204; probe subscription
used a dummy URL and was deleted; count restored to 0). Event-type list is
tenant-observed. Delivery format/signing not exercised — needs a real receiving endpoint.
