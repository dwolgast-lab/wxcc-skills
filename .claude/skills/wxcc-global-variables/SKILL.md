---
name: wxcc-global-variables
description: Use when asked about Webex Contact Center Global Variables - the CAD variables flows read and write, and that agents can see on the Desktop - "what global variables do we have", "add a global variable", "make variable X agent-viewable", "change X's default value", "is X reportable", "delete global variable X". The API name is cad-variable. Full CRUD plus bulk, all verified live.
---

# wxcc-global-variables — the `cad-variable` entity

Call `wxcc_list` / `wxcc_get` / `wxcc_references` / `wxcc_create` / `wxcc_update` /
`wxcc_delete` with `entity="cad-variable"` on the server for the tenant the user named.
**If no tenant was named, ask — do not guess.**

**Say "Global Variable" to the user.** The API path is `cad-variable` (Call-Associated
Data), and that name appears nowhere in the admin UI.

A global variable carries data through a contact: flows set and read it, reports can group
by it, and the Desktop can show it to an agent. It is the main way information moves
between a flow and the people handling the contact.

## Use when / Do NOT use when

**Use when:** listing variables; creating one; changing a default value, type, or the
agent-visibility flags; deleting one; asking what a variable is used by.

**Do NOT use when:**
- Editing the flow that reads or writes the variable → Cisco's `flow-store` server.
- Per-contact values at runtime → that is interaction data, **wxcc-tasks-search**.
- Auth errors or 403 → **wxcc-connect**.

## Flows reference these — check before you change one

`wxcc_references(entity="cad-variable", id=...)` returns the flows and resource collections
that point at a variable. On the sandbox, `globalAllHandsMeetingTTS` is referenced by the
flow `StandardCallFlow`. **Renaming or deleting a referenced variable breaks that flow at
runtime, not at write time** — the API will let you do it.

Deleting is reference pre-flighted and will be blocked with the conflict list. Renaming is
**not** blocked. Say so before you rename.

## Read

```
wxcc_list(entity="cad-variable", all_pages=true)
wxcc_get(entity="cad-variable", id="<id>")
wxcc_references(entity="cad-variable", id="<id>")
```

Fields: `name`, `description`, `variableType`, `defaultValue`, `active`, `agentViewable`,
`agentEditable`, `reportable`, `sensitive`, plus `desktopLabel` when agent-viewable.

## Create

```
wxcc_create(entity="cad-variable", fields={
  "name": "Global_CustomerTier",
  "variableType": "String",
  "defaultValue": "unknown",
  "active": true,
  "agentViewable": true,
  "agentEditable": false,
  "reportable": true,
  "desktopLabel": "Customer Tier"
}, confirm=True)
```

All seven of `name`, `variableType`, `defaultValue`, `active`, `agentEditable`,
`agentViewable`, `reportable` are **required** — a 400 names them. Dry-run first as always.

## The `variableType` trap

Cisco's own schema lists **every value twice, in two casings**:

```
STRING | INTEGER | DATE_TIME | BOOLEAN | DECIMAL
String | Integer | DateTime  | Boolean | Decimal
```

Live sandbox data uses the **TitleCase** forms (`String`, `Boolean`). Match what the tenant
already uses — read an existing variable and copy its spelling rather than picking one.
Whether the two forms are interchangeable on write is **unverified**; do not assume.

`defaultValue` must be valid **for the type**, or you get a 400 naming
`validDefaultValueForVariabelType` (Cisco's typo, not ours). A `Boolean` variable wants
`"true"` / `"false"` as strings — that is how the sandbox stores them.

## Traps

| Trap | What actually happens |
|---|---|
| Calling it "CAD variable" to a user | The admin UI says **Global Variables**. Use that; mention the API name only if they need the path. |
| `agentViewable: true` without `desktopLabel` | 400. The label is what the agent actually sees. |
| `defaultValue` not matching `variableType` | 400 `validDefaultValueForVariabelType`. |
| Renaming a flow-referenced variable | **Allowed, and it breaks the flow at runtime.** Only delete is pre-flighted. Run `wxcc_references` first. |
| Assuming the enum casing | Both casings are published; the tenant uses TitleCase. Copy, do not guess. |
| Bulk | create + update + delete all work, all `POST cad-variable/bulk`; update is read-modify-write. See **wxcc-bulk**. |

Reads, references, the field list and the enum were verified live on the sandbox
2026-07-22; the create/update/delete round trip and bulk 2026-07-20/21. The `sensitive`
flag exists on live records but its write behaviour is **unprobed**.
