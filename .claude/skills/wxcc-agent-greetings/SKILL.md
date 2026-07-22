---
name: wxcc-agent-greetings
description: Use when asked about Webex Contact Center agent personal greetings - the per-agent recorded greeting played on their calls - "upload a greeting for agent X", "what greeting does X have", "replace/delete X's greeting", "list agent greetings". NOT the tenant's shared prompts or hold music, which are wxcc-audio-files. Upload works only on the LOCAL server.
---

# wxcc-agent-greetings — per-agent recorded greetings

Call `wxcc_list` / `wxcc_get` / `wxcc_create` / `wxcc_update` / `wxcc_delete` with
`entity="agent-personal-greeting"` on the server for the tenant the user named. **If no
tenant was named, ask — do not guess.**

**This is not `audio-file`.** A greeting belongs to **one agent** and is played on their
calls. Tenant-wide prompts, IVR audio, and hold music are `audio-file` →
**wxcc-audio-files**. If a user says "upload a greeting", find out whose.

## The greeting-purpose id — read this before creating one

Every greeting binds to **two** things: an `agentId` and a `greetingPurposeId`. Omit the
purpose and create fails with:

```
409  "Internal error. Please contact Cisco Support Team"
```

which names nothing and looks like an outage. It is a missing `greetingPurposeId`.

Get one from **`GET v2/greeting-purpose`** — the sandbox has a single `Default` purpose.
**That route is absent from Cisco's published OpenAPI spec**, which lists only
`agent-personal-greeting/*`, so it cannot be discovered from the documentation. There is no
tool for it yet; read it with the CLI:

```powershell
python wxcc.py get "organization/{orgId}/v2/greeting-purpose"
```

## Upload is LOCAL-only, and every write carries the audio

`file_path` is an absolute path **on the machine running the server**. The cloud servers
(`wxcc-cloud-*`) share no filesystem with you and refuse with an explanation; reads and
deletes still work there.

There is **no metadata-only update**. A JSON `PUT` is a bare 500 and `PATCH` returns the
same nameless 409, so **renaming means re-uploading the audio**. `wxcc_update` enforces
this — it refuses without `file_path` rather than letting you think a rename worked.

```
wxcc_create(entity="agent-personal-greeting", fields={
  "name": "AdamGreeting.wav",
  "contentType": "AUDIO_WAV",
  "agentId": "<user id>",
  "greetingPurposeId": "<from v2/greeting-purpose>"
}, file_path=r"C:\path\to\greeting.wav", confirm=True)

wxcc_update(entity="agent-personal-greeting", id="<id>",
            changes={"name": "NewName.wav"},
            file_path=r"C:\path\to\greeting.wav", confirm=True)

wxcc_delete(entity="agent-personal-greeting", id="<id>", confirm=True)
```

`agentId` is the **CC user id** (`user.id`), not the Control Hub `ciUserId`. Resolve a
person to their id with **wxcc-users**, or `wxcc_find_users(by="ci_user_id", ...)` if you
were handed a Control Hub id.

## Deletes are not reference-checked

`incoming-references` is **broken for this entity** — it answers
`400 "specify a valid external entity type"` for every id, the same defect as
`contact-number`. So `wxcc_delete` cannot pre-flight it and returns
`REFERENCES_NOT_CHECKED`. **Relay that**: the tool did not verify that nothing depends on
the greeting, and only the API's own 412 stands in the way.

## Traps

| Trap | What actually happens |
|---|---|
| Missing `greetingPurposeId` | **409 "Internal error. Please contact Cisco Support Team"** — nameless, and the single most likely thing to waste your time here. |
| "The spec says JSON works" | It does not. Every write is multipart; a JSON body is a bare 500 — same lie as `audio-file`. |
| Trying to rename without the file | Refused by the tool, because the API has no metadata-only route. Re-upload the same audio to rename. |
| Confusing it with `audio-file` | Different entity, different purpose. Greetings are per-agent. |
| `v3` | `v3/agent-personal-greeting` **lists**, but has no item path (404). The item path works with and without `v2`. |
| Reading the audio back | No download route, same as `audio-file`. A replace cannot be verified — the tool returns `AUDIO_NOT_VERIFIABLE`; tell the user to listen in Control Hub. |
| Reference check | Broken API-side; deletes proceed unchecked. |

All verified live on the sandbox 2026-07-22 through create → read → multipart PUT → delete
round trips via the MCP tools, with the greeting count returned to its baseline of 0.
