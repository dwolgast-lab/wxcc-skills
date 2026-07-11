---
name: wxcc-desktop-layouts
description: Use when asked about Webex Contact Center desktop layouts (Agent Desktop screen layouts) - "what desktop layouts exist", "show the global layout", "export layout X's JSON", "create a desktop layout for team X", "update/delete layout X". Reads and writes in one skill; writes require cjp:config_write scope and explicit user confirmation. The layout definition itself is a JSON document embedded in the config object as a string.
---

# wxcc-desktop-layouts — Agent Desktop layouts (read + write)

Desktop layouts define what the Agent Desktop shows (widgets, panels, branding). The
entity is `desktop-layout`; each object is metadata **plus the entire layout JSON embedded
as a string** in `jsonFileContent` (~20 KB for the default). Full lifecycle verified
against a live sandbox tenant on 2026-07-11 (create 201, update 200, delete 204).

## Use when / Do NOT use when

**Use when:** listing/inspecting/exporting layouts, or creating/updating/deleting them.

**Do NOT use when:**
- Desktop *behavior* settings (wrap-up, auto-answer, viewable queues) → **wxcc-desktop-profiles**
  (a different entity — layouts are screens, profiles are permissions/behavior).
- Which team uses a layout → layouts carry `teamIds` (read it here); team config itself → **wxcc-teams**.
- Auth errors or missing write scope → **wxcc-connect**.

## Ground rules

- Paths go to `wxcc.py` **without a leading slash** (see wxcc-connect).
- List: `v2/desktop-layout` (paginated `meta` + `data[]`). Item paths have **no v2**.
- The list omits `jsonFileContent` — only the item GET returns it.
- Writes: confirm first, name the rollback, verify with a re-read (**wxcc-teams-write** rules).

## Recipes — reads

```bash
python wxcc.py get --all "organization/{orgId}/v2/desktop-layout?attributes=id,name,global,systemDefault,teamIds"
python wxcc.py get "organization/{orgId}/desktop-layout/LAYOUT-ID"          # full object incl. jsonFileContent
```

Fields observed live: `name`, `description`, `editedBy`, `jsonFileName`,
`jsonFileContent`, `global`, `status`, `defaultJsonModified`, `teamIds`, `systemDefault`,
`validated`. To export the layout JSON itself, parse `jsonFileContent` out of the item GET
(it is a JSON *string* — decode it before editing).

## Recipes — writes

### Create a layout

Beyond the obvious fields, validation requires `defaultJsonModified`, `status`, and
`editedBy` (400 names them). Bodies are large — use `--body @file.json`:

```bash
python wxcc.py post "organization/{orgId}/desktop-layout" --body @layout.json
```

with `layout.json` shaped like:

```json
{"name":"LAYOUT-NAME","description":"...","jsonFileName":"LAYOUT-NAME.json",
 "jsonFileContent":"<the layout JSON, serialized as a string>",
 "global":false,"teamIds":[],"defaultJsonModified":false,"status":true,
 "editedBy":"your-name"}
```

→ verify: HTTP 201; **capture `id`**. Practical path (verified): GET an existing layout,
copy its `jsonFileContent`, modify, and POST under a new name. Assigning teams at create
via `teamIds` is untested (candidate) — the probe used `[]`.

### Update a layout

```bash
python wxcc.py get "organization/{orgId}/desktop-layout/LAYOUT-ID" > prior.json   # rollback copy
python wxcc.py put "organization/{orgId}/desktop-layout/LAYOUT-ID" --body @updated.json
```

PUT the full object with `id` (same field set as create). → verify: HTTP 200 + re-read
(verified live with a description change). Rollback = PUT `prior.json`'s fields back.

### Delete a layout

```bash
python wxcc.py delete "organization/{orgId}/desktop-layout/LAYOUT-ID"
```

→ verify: HTTP 204, gone from the list. **No true rollback** (recreate = new id). Never
delete or overwrite the `systemDefault` **Global Layout** — it is the tenant-wide fallback.

## Traps (observed live, 2026-07-11)

| Item | Detail |
|---|---|
| `jsonFileContent` is a string, not an object | Serialize your layout JSON before embedding; decode after reading |
| List vs item shape | `jsonFileContent` only appears on the item GET |
| Missing `editedBy`/`status`/`defaultJsonModified` on create | 400 names them — they are required, not defaulted |
| Layout JSON content is **not validated** on create | `validated: false` on the probe object; a malformed layout breaks agents' desktops at load, not at POST — test on a non-production team first |

## Provenance and maintenance

Lifecycle run live on a us1 sandbox 2026-07-11 (201/200/204; probe layout copied the
system default's `jsonFileContent`; baseline of 2 layouts restored). Layout-JSON schema
itself (widgets, panels) is Cisco-documented, not covered here. Re-verify with a `zz-`
named copy-create→update→delete cycle.
