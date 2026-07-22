---
name: wxcc-business-hours
description: Use when asked about Webex Contact Center business hours, working hours, holiday lists, or schedule overrides - "when are we open", "what are the hours for X", "add a holiday", "close early on Christmas Eve", "create a business hours schedule", "what holiday list does X use", "add a one-off closure". Covers the three interlocking entities business-hours, holiday-list and overrides. Reads plus verified create/update/delete.
---

# wxcc-business-hours — working hours, holiday lists, and overrides

Three entities that only make sense together. Call `wxcc_list` / `wxcc_get` /
`wxcc_references` / `wxcc_create` / `wxcc_update` / `wxcc_delete` with
`entity="business-hours"`, `"holiday-list"`, or `"overrides"` on the server for the tenant
the user named. **If no tenant was named, ask — do not guess.**

**`business-hours` is the hub.** It holds the weekly schedule and points at the other two:

```
business-hours ──holidaysId──▶ holiday-list     (annual/recurring closures)
      │
      └────────overridesId──▶ overrides         (one-off or recurring exceptions)
```

**Flows bind to business hours.** On the sandbox, `Standard_Working_Hours` is referenced by
the flow `StandardCallFlow` — so editing hours changes live call routing. Run
`wxcc_references` before any change and tell the user what is downstream.

## Use when / Do NOT use when

**Use when:** reading or changing open hours; adding/removing holidays; adding a one-off
closure or extra-open window; asking which holiday list or override set a schedule uses;
asking what breaks if a schedule changes.

**Do NOT use when:**
- Editing the flow that *consumes* the schedule → Cisco's `flow-store` server.
- Queue-level routing or overflow → **wxcc-queues** / **wxcc-queues-write**.
- Auth errors or 403 → **wxcc-connect**.

## Read

```
wxcc_list(entity="business-hours")                  # also holiday-list, overrides
wxcc_get(entity="business-hours", id="<id>")
wxcc_references(entity="holiday-list", id="<id>")   # which schedules use this list
```

Resolve the links by hand — they are plain ids:
`GET holiday-list/{business_hours.holidaysId}` and `GET overrides/{...overridesId}`.

**A missing key is not a missing field.** This API **omits unset fields entirely** rather
than returning `null`. A `business-hours` record with no override set simply has no
`overridesId` key. That is *not* a list-vs-item discrepancy — verified per record; list and
item agree on all three entities.

## Shapes

All three take a **non-empty** nested array, and each one is named differently. An empty
array is a 400, so clone the shape from a live record rather than inventing one.

| Entity | Required | The array | Entry shape |
|---|---|---|---|
| `business-hours` | `name`, `timezone`, `workingHours` | `workingHours` | `{name, days:[MON..SUN], startTime, endTime}` — 24h `HH:MM`, days 3-letter UPPERCASE |
| `holiday-list` | `name`, `holidays` | `holidays` | `{name, startDate, endDate, frequency, recurrence:{...}}` — dates `YYYY-MM-DD` |
| `overrides` | `name`, `timezone`, `overrides` | `overrides` | `{name, startDateTime, endDateTime, workingHours:bool, frequency, recurrence:{...}}` — `YYYY-MM-DDTHH:MM`, **no seconds, no zone** |

**`holiday-list` does NOT require `timezone`; the other two do.** That asymmetry is real —
a `holiday-list` create with `name` + `holidays` alone returns 201.

## Holiday recurrence rules (probed live)

`frequency` is **optional** — omit it entirely for a one-off date. There is no `"None"`
value: `frequency: "None"` is a deserialize error, so **omit the key** instead.

| `frequency` | Also required in `recurrence` |
|---|---|
| *(omitted)* | nothing — one-off |
| `Yearly` | **`specificMonth`** (e.g. `"DEC"`) — 400 names it if absent |
| `Monthly` | **either** `specificDayOfMonth` **or** `occurrenceInTheMonth` — 400 names both |
| `Weekly` | `daysOfWeek` |

Both yearly styles work: a fixed date (`specificMonth` + `specificDayOfMonth`) and a
floating one (`specificMonth` + `occurrenceInTheMonth: "FOURTH"` + `daysOfWeek: ["MON"]`,
which is how Memorial Day is stored).

## Writes

Call without `confirm` → nothing is written; you get the tenant, the diff or what would be
destroyed, and the rollback. Show it, get an explicit yes, re-call with `confirm=true`.

Updates are read-modify-write full-object PUTs, so **the nested array is replaced wholesale**
— to add one holiday, read the list, append, and send the whole array back. `wxcc_update`
does the read for you; just make sure `changes` carries the complete intended array.

Deletes are pre-flighted. A `holiday-list` used by two schedules and a resource collection
comes back `blocked` with all three named — repoint them first.

Bulk is **create + delete only** on all three (`POST <entity>/bulk`); there is no bulk
update — an id-bearing item returns `400 "New configuration cannot have an id"` and `PATCH`
is 405. See **wxcc-bulk**.

## Traps

| Trap | What actually happens |
|---|---|
| Name with punctuation | **400** — names allow only alphanumerics, space, `_` and `-`. `.`, `+`, `/` all fail. Same validator on all three entities. |
| Empty nested array | 400 (`"Working hours cannot be empty"` / `"Holiday list cannot be empty"` / `"Overrides cannot be empty"`). |
| `Yearly` with no `specificMonth` | 400. Easy to miss because the entry otherwise looks complete. |
| Assuming `holiday-list` needs `timezone` | It does not — only `business-hours` and `overrides` do. |
| Entity names are **plural as written** | `business-hours` and `overrides` are plural; `holiday-list` is singular. `overrides` is also the name of its own payload key. |
| Bare `business-hours` list alias | Returns a **bare list**, not `{data:[...]}`. `v2/business-hours` is the list path; the item path drops `v2`. |
| Editing hours in isolation | A flow may bind to the schedule — check `wxcc_references` first. |

Reads, references, required-field validation, the recurrence matrix, and the name charset
rule were all verified live on the sandbox 2026-07-22; create/update/delete round trips
2026-07-21, re-confirmed for `holiday-list` 2026-07-22. Every probe object was deleted and
counts swept back to baseline (business-hours 3, holiday-list 1, overrides 3).
