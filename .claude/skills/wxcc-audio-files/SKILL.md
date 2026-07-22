---
name: wxcc-audio-files
description: Use when asked about Webex Contact Center audio files - the prompts, greetings, and music-on-hold that flows play - "what audio files do we have", "upload a wav", "add a hold music file", "rename/replace/delete audio file X", "what references audio file X". Full CRUD. The ONLY entity that takes a file upload, and upload works only on the LOCAL server, not the cloud one.
---

# wxcc-audio-files — list, upload, edit, and delete WxCC audio files

Call `wxcc_list` / `wxcc_get` / `wxcc_references` / `wxcc_create` / `wxcc_update` /
`wxcc_delete` with `entity="audio-file"` on the server for the tenant the user named.
**If no tenant was named, ask — do not guess.**

An audio file is a prompt, greeting, or music-on-hold clip that **flows** play. This skill
owns the file objects; the flows that reference them belong to Cisco's `flow-store` MCP
server.

## Use when / Do NOT use when

**Use when:** listing or finding audio files; uploading a new .wav; renaming one or editing
its description; replacing the audio in an existing file; deleting one; asking what
references one.

**Do NOT use when:**
- Building or editing the flow that *plays* the prompt → Cisco's `flow-store` server.
- Auth errors or 403 → **wxcc-connect**.
- Music-on-hold *assignment* rather than the file itself → that lives in flow config.

## The two things that make this entity different

**1. It takes a real file, so upload is LOCAL-ONLY.** `wxcc_create` and audio-replacing
`wxcc_update` need `file_path` — an **absolute path on the machine running the server**.
The cloud servers (`wxcc-cloud-*`) share no filesystem with the user and refuse the call
with an explanation. Everything else — list, get, references, rename, re-describe, delete —
works on every server. If the user is on a cloud server and wants to upload, tell them to
run the same call against the local server for that tenant.

**2. Nothing can read the audio back.** There is no download route: the DTO documents a
`url` field but no record returns it, and `.../content` and `.../download` both 404. This
has a hard consequence — **a replace can never be verified.** Never tell the user the audio
was replaced; tell them the API accepted it and they should play the file in Control Hub.

## Read

```
wxcc_list(entity="audio-file")                 # meta.totalRecords, data[]
wxcc_get(entity="audio-file", id="<id>")
wxcc_references(entity="audio-file", id="<id>")   # what breaks if you change it
```

Fields: `id`, `name`, `contentType`, `blobId`, `description`, `createdTime`,
`lastUpdatedTime`. List and item agree (item just drops `links`) — verified across all
records 2026-07-22, so either view is safe to read from.

`contentType` is an enum and **both wav spellings occur live in one tenant**: `AUDIO_WAV`
and `AUDIO_X_WAV`. Do not "correct" one to the other. The portal's full set is
`AUDIO_WAV | AUDIO_X_WAV | TEXT_HTML | TEXT_PHP | APPLICATION_OCTET_STREAM`.

## Upload a new file

```
wxcc_create(entity="audio-file",
            fields={"name": "WelcomeMessage.wav",
                    "contentType": "AUDIO_WAV",
                    "description": "Main queue greeting"},
            file_path=r"C:\path\to\WelcomeMessage.wav")
```

Required: `name` and `contentType` (plus `file_path`). Give `name` the `.wav` extension.
Called without `confirm` it writes nothing and shows the preview — show that, get an
explicit yes, then re-call with `confirm=true`. Rollback is
`wxcc_delete(entity="audio-file", id=<new id>, confirm=True)`.

## Edit metadata vs replace the audio

**Metadata only** (name, description) — omit `file_path`. This is a real partial `PATCH`,
the only single-item PATCH in the whole registry, so nothing is read-modify-written and
there is no full-object echo to mangle:

```
wxcc_update(entity="audio-file", id="<id>",
            changes={"description": "Updated greeting"}, confirm=True)
```

**Replace the audio** — pass `file_path`. This is a multipart `PUT` and it is
**irreversible**: the blob is overwritten in place, and because nothing downloads the old
audio first, it cannot be restored unless the user still has the original file. Say that
before they approve.

```
wxcc_update(entity="audio-file", id="<id>",
            changes={}, file_path=r"C:\path\to\new.wav", confirm=True)
```

The tool returns `AUDIO_NOT_VERIFIABLE` on any replace. Relay it — do not report success.

## Delete

```
wxcc_delete(entity="audio-file", id="<id>", confirm=True)
```

Pre-flights references first. A file a flow still plays should be repointed in the flow
before deleting, or the flow breaks at runtime.

## Traps

| Trap | What actually happens |
|---|---|
| "The portal says JSON works" | **It does not.** Create and replacing PUT are multipart **only** — every JSON shape returns a bare 500, including the documented `{audioFileInfo, audioFile}` envelope. The tools already send multipart; never hand-roll a JSON create. |
| Metadata part with no content type | The whole request is **415**. The JSON part must declare `application/json` explicitly. |
| No `audioFile` part on create or PUT | **400**. Both parts are mandatory. |
| PUT without the record's `blobId` | **400 "blobId: invalid value"**. `wxcc_update` carries it forward for you. |
| Reusing another file's `blobId` | Also **400** — `blobId` is an ownership token, not a way to point one record at another's audio. |
| Expecting `blobId` to change after a replace | It does not. The blob is overwritten in place, so an unchanged `blobId` is **not** evidence the replace failed — and a changed description is not evidence it worked. |
| `description` "of the dial plan" | A copy-paste error in Cisco's own schema. It is just a description; Dial Plan is a different, deprecated entity. |
| Looking for bulk | No bulk route is published for this entity, and bulk-export is out of scope for these tools. |

All facts verified live against the sandbox 2026-07-22 through a full create / read / patch
/ multipart-put / delete round trip, with the count swept back to baseline afterward.
