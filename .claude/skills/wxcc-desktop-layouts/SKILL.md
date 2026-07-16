---
name: wxcc-desktop-layouts
description: Use when asked about Webex Contact Center desktop layouts (Agent Desktop screen layouts) - "what desktop layouts exist", "show the global layout", "export layout X's JSON", "create a desktop layout for team X", "update/delete layout X". Reads and writes; the layout definition itself is a JSON document embedded in the config object as a string.
---

# wxcc-desktop-layouts — Agent Desktop layouts (read + write)

Call the `wxcc_*` MCP tools with `entity="desktop-layout"` on the server for the tenant the
user named. **If no tenant was named, ask — do not guess.**

Each object is metadata **plus the entire layout JSON embedded as a string** in
`jsonFileContent` (~20 KB for the default).

## Use when / Do NOT use when

**Use when:** listing/inspecting/exporting layouts, or creating/updating/deleting them.

**Do NOT use when:**
- Desktop *behavior* (wrap-up, auto-answer, viewable queues) → **wxcc-desktop-profiles**.
  Layouts are **screens**; profiles are **permissions and behavior**. Different entities,
  commonly confused.
- Which team uses a layout → layouts carry `teamIds` (read it here); team config →
  **wxcc-teams**.
- Auth errors or 403 on write → **wxcc-connect**.

## Reads

| Goal | Call |
|---|---|
| All layouts | `wxcc_list(entity="desktop-layout", attributes="id,name,global,systemDefault,teamIds", all_pages=true)` |
| One layout **incl. its JSON** | `wxcc_get(entity="desktop-layout", id="LAYOUT-ID")` |

**The list omits `jsonFileContent` — only the item read returns it.** To export the layout,
parse `jsonFileContent` out of the item read: it is a JSON *string*, so decode it before
editing.

Fields observed live: `name`, `description`, `editedBy`, `jsonFileName`, `jsonFileContent`,
`global`, `status`, `defaultJsonModified`, `teamIds`, `systemDefault`, `validated`.

## Writes

```
wxcc_create(entity="desktop-layout", fields={
  "name": "LAYOUT-NAME", "description": "...",
  "jsonFileName": "LAYOUT-NAME.json",
  "jsonFileContent": "<the layout JSON, SERIALIZED AS A STRING>",
  "global": false, "teamIds": [],
  "defaultJsonModified": false, "status": true, "editedBy": "your-name"
})

wxcc_update(entity="desktop-layout", id="LAYOUT-ID", changes={"description": "..."})
wxcc_delete(entity="desktop-layout", id="LAYOUT-ID")
```

`defaultJsonModified`, `status`, and `editedBy` are **required on create** (a 400 names
them) — not obvious, and not defaulted. The tool checks before calling.

**The practical path (verified):** read an existing layout, copy its `jsonFileContent`,
modify, create under a new name. Do not hand-write a layout from scratch.

Assigning teams at create via `teamIds` is untested (**candidate**) — the probe used `[]`.

## Traps

| Item | Detail |
|---|---|
| **Layout JSON is NOT validated at create** | The probe object came back `validated: false`. A malformed layout **breaks agents' desktops at load time, not at POST** — the API will happily accept garbage. Test on a non-production team first. |
| `jsonFileContent` is a string, not an object | Serialize before embedding; decode after reading |
| List vs item shape | `jsonFileContent` only on the item read |
| **Never touch the `systemDefault` Global Layout** | It is the tenant-wide fallback — breaking it breaks every agent with no layout of their own |
| Delete | No rollback; recreate yields a new id and teams pointing at the old one break |

## Provenance and maintenance

Lifecycle run live on a us1 sandbox 2026-07-11 (201/200/204; the probe copied the system
default's `jsonFileContent`; baseline of 2 layouts restored). The layout-JSON schema itself
(widgets, panels) is Cisco-documented and out of scope here. Re-verify with a `zz-` named
copy→update→delete cycle.
