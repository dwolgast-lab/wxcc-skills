# Running the local (stdio) servers from Docker on forge

**Built and verified 2026-07-28.** The servers execute in a container on `forge.fwnet.us`; your
laptop reaches them over SSH. The transport stays **stdio** — this is the same server with the same
stored-token model, just not running on your laptop. It is *not* the Cloud Run design.

---

## Why stdio-over-SSH rather than hosting the HTTP build

A stdio MCP server is a **child process of the client**. It has no port and no address — the
transport *is* the pipe to that child. So "run it on another machine" means "make the child process
run over there," which is what `ssh … docker run -i` does.

The alternative — self-hosting `mcp_http.py` on forge — would deliver the *cloud* model
(credential-free, each caller brings their own token), not the local one. That is a different
product with different trade-offs, and it would have made the demo's local-vs-cloud slide
incoherent.

---

## What is on forge

```text
/home/dave/wxcc-mcp/
  app/      wxcc.py, mcp_server.py, mcp_http.py, requirements.txt, Dockerfile   (0664)
  env/      .env, .env.ttecgt, .env.hdsupply                                    (0600, dir 0700)
  tokens/   bind-mounted to /app/.wxcc inside the container                     (dir 0700)
```

Image: `wxcc-mcp:local`, 231 MB, built from the project's **existing** `Dockerfile` — not a fork.
That Dockerfile copies `mcp_http.py`, so it is present in the image even though stdio never uses it.

**Credentials are never baked into the image.** They are bind-mounted at run time, which keeps the
Dockerfile's stated invariant ("this image deliberately contains NO Webex credentials") literally
true.

**Why the paths matter:** `wxcc.py:49` sets `REPO_DIR = Path(__file__).resolve().parent`, so both
`.env*` and `.wxcc/` are resolved *next to the script* — `/app` in the container. That is why the
mounts target `/app/.env…` and `/app/.wxcc` and not a home directory.

The image's `app` user is uid 1000 and `dave` is uid 1000, so bind-mount ownership lines up with no
`chown` juggling.

---

## Step 1 — Authenticate each profile — ✅ DONE 2026-07-28

All three profiles are authenticated and each verified to resolve to its expected org:
`tokens.json` → `174bc2cb-…`, `tokens.ttecgt.json` → `f766bc3c-…`,
`tokens.hdsupply.json` → `278aa0f3-…`.

**Use `~/wxcc-mcp/login.sh sandbox|gold|hds`, not the raw commands below.**

The raw `docker run` forms differ only by a `-e WXCC_PROFILE=` flag and a mount path. Running the
same one three times writes the same token file three times and silently keeps only the last — which
is exactly what happened on the first attempt, producing one token file where there should have been
three. `login.sh` takes one word, states the tenant it expects before opening the flow, and **deletes
the token if the resulting org is not the expected one.** It is kept on forge only, not in the git
repo, because it maps nicknames to real customer org ids.

The commands below are retained for reference and for rebuilding the script if it is lost.

### Reference: the raw per-profile commands

**Tokens were deliberately not copied from the laptop.** `tenants.local.md` says *"Never copy a
token file,"* so each profile signs in fresh on forge.

### The tunnel, and why it is needed

`wxcc.py:399` binds the OAuth callback listener to the **hostname in `WXCC_REDIRECT_URI`**, which is
`localhost`. Inside a container that means the container's *own* loopback, which `docker -p` cannot
reach. So the auth run uses `--network host`, which puts the listener on **forge's** `127.0.0.1:8484`
— verified: `LISTEN 127.0.0.1:8484 users:(("python",…))`.

An SSH tunnel then makes your laptop's `localhost:8484` reach it, which means
**`WXCC_REDIRECT_URI` stays `http://localhost:8484/callback` and the Webex Integration needs no
change at all.**

### Do this, once per profile

**Terminal 1 — hold the tunnel open:**

```bash
ssh -L 8484:localhost:8484 dave@forge.fwnet.us
```

**Terminal 2 — start the login.** Sandbox (default profile):

```bash
ssh dave@forge.fwnet.us "docker run --rm --network host \
  -v ~/wxcc-mcp/env/.env:/app/.env:ro \
  -v ~/wxcc-mcp/tokens:/app/.wxcc \
  wxcc-mcp:local python wxcc.py auth login"
```

Gold:

```bash
ssh dave@forge.fwnet.us "docker run --rm --network host -e WXCC_PROFILE=ttecgt \
  -v ~/wxcc-mcp/env/.env.ttecgt:/app/.env.ttecgt:ro \
  -v ~/wxcc-mcp/tokens:/app/.wxcc \
  wxcc-mcp:local python wxcc.py auth login"
```

HD Supply:

```bash
ssh dave@forge.fwnet.us "docker run --rm --network host -e WXCC_PROFILE=hdsupply \
  -v ~/wxcc-mcp/env/.env.hdsupply:/app/.env.hdsupply:ro \
  -v ~/wxcc-mcp/tokens:/app/.wxcc \
  wxcc-mcp:local python wxcc.py auth login"
```

It prints an authorize URL (the browser call fails harmlessly — there is no browser on forge).
**Copy that URL into a PRIVATE/incognito window** and sign in as an administrator **of that
tenant**. This is the trap that has already bitten three times: a browser reusing an existing Webex
session silently re-mints a token for the *first* tenant and looks like it worked.

### Verify before trusting it

```bash
ssh dave@forge.fwnet.us "ls -l ~/wxcc-mcp/tokens/"
```

Expect `tokens.json`, `tokens.ttecgt.json`, `tokens.hdsupply.json`. Then run `auth status` per
profile (same `docker run` as above, `auth status` instead of `auth login`) and confirm **all three
org ids are different.** If two match, one signed in to the wrong tenant — stop and redo it.

---

## Step 2 — Point Claude Code at forge

Add to `.mcp.json`. These are **added alongside** the laptop servers, not replacing them, so nothing
breaks if authentication is not finished yet — an un-authenticated server simply reports
`NOT authenticated` rather than failing.

```json
"wxcc-forge-sandbox": {
  "type": "stdio",
  "command": "ssh",
  "args": ["-o","BatchMode=yes","dave@forge.fwnet.us",
    "docker run -i --rm -v /home/dave/wxcc-mcp/env/.env:/app/.env:ro -v /home/dave/wxcc-mcp/tokens:/app/.wxcc wxcc-mcp:local python mcp_server.py"]
},
"wxcc-forge-gold": {
  "type": "stdio",
  "command": "ssh",
  "args": ["-o","BatchMode=yes","dave@forge.fwnet.us",
    "docker run -i --rm -e WXCC_PROFILE=ttecgt -v /home/dave/wxcc-mcp/env/.env.ttecgt:/app/.env.ttecgt:ro -v /home/dave/wxcc-mcp/tokens:/app/.wxcc wxcc-mcp:local python mcp_server.py"]
},
"wxcc-forge-hdsupply": {
  "type": "stdio",
  "command": "ssh",
  "args": ["-o","BatchMode=yes","dave@forge.fwnet.us",
    "docker run -i --rm -e WXCC_PROFILE=hdsupply -v /home/dave/wxcc-mcp/env/.env.hdsupply:/app/.env.hdsupply:ro -v /home/dave/wxcc-mcp/tokens:/app/.wxcc wxcc-mcp:local python mcp_server.py"]
}
```

Then restart Claude Code and run `wxcc_whoami` on each. Once they check out, delete the three
laptop entries — and add the forge nicknames to `tenants.local.md`.

**`-i` but never `-t`.** `-i` keeps stdin open, which *is* the transport. A TTY would inject control
characters into the JSON-RPC stream and corrupt it.

---

## What is verified, and what is not

**Verified live on 2026-07-28:**

- Host key checked against the fingerprint out-of-band, then trusted; `dave` authenticates by key
- `dave` is in group `999(docker)`; Docker 29.6.0; 31 GB free
- Image builds
- Both `default` and `ttecgt` read their config in-container and correctly report `NOT authenticated`
- `--network host` binds the callback listener on forge's `127.0.0.1:8484`
- The authorize URL is printed even with no browser present
- **The full MCP handshake over `ssh → docker run -i` returns a valid `initialize` result**, with the
  correct per-tenant `instructions` string

**Not verified:**

- The OAuth round trip through the tunnel — it needs a browser and a Webex sign-in. Everything
  *around* it is proven; the sign-in itself is Step 1.
- Token refresh behaviour when several containers run concurrently. Each profile writes its own
  file, so a race is not expected, but it has not been exercised.

---

## SDK drift — ✅ RESOLVED 2026-08-01

Measured 2026-07-28, both by `importlib.metadata.version('mcp')`, the drift that prompted the exact
pin:

| Host | mcp package (2026-07-28) | mcp package (now) |
|---|---|---|
| Laptop | **1.28.1** | **2.0.0** |
| Forge container | **1.29.0** | **2.0.0** |

Both satisfied the old `mcp>=1.28,<2`, so nothing was broken — but that pin guarded only the
**major**, so every fresh `docker build` floated to whatever was newest and the two hosts drifted
apart silently. "Verified on the laptop" had quietly stopped implying "verified on forge."

**Resolved by pinning exactly (`mcp==2.0.0`) and rebuilding both hosts on 2026-08-01.** The pin is
what keeps them identical; re-read it before any `docker build`. Full rationale for taking 2.x is in
`CHANGELOG.md` under 2026-08-01.

**Verified after the rebuild (2026-08-01)**, over the real `ssh → docker run -i` path, all three
profiles: the legacy `2025-11-25` handshake still negotiates (the 2.0.0 server negotiates *down*, so
an unchanged Claude Code client keeps working), and a live `wxcc_whoami` returned the correct tenant
on the correct, distinct org for each — `Personal Sandbox` → `174bc2cb-…`, `TTEC Gold Tenant` →
`f766bc3c-…`, `HD Supply` → `278aa0f3-…`. No org collision.

**Stale sentence retired:** this section previously read the handshake's `"version":"1.29.0"` as the
SDK version. That was correct for FastMCP, but `MCPServer` defaults `version` to `""`, so
`serverInfo.version` is now **empty**. Nothing consumes it.

**Rollback:** the pre-upgrade image is tagged on forge as `wxcc-mcp:pre-mcp2` —
`ssh dave@forge.fwnet.us "docker tag wxcc-mcp:pre-mcp2 wxcc-mcp:local"` restores it without a
rebuild. On the laptop, `pip install mcp==1.28.1`. Both also need the code reverted, since
`mcp.server.fastmcp` does not exist in 2.x and `mcp.server.mcpserver` does not exist in 1.x.

---

## Security note — read this before cutting over

This moves stored refresh tokens for **three tenants, two of them real, one a customer**, from a
laptop that is usually off and physically with you, onto a server that is always on.

Mitigations in place: forge is internal-only, the token directory is `0700` and the env files
`0600`, access is gated by SSH key, and no tokens were copied — each was minted fresh on the host
that will hold it.

This is the trade the stdio-on-forge model requires. It is *not* what the Cloud Run build does; that
one holds no credentials at all. If token-at-rest on an always-on host is not acceptable for the
customer tenant, run **that** profile only from the laptop, or reach it through the cloud service.

---

## Rollback

```bash
ssh dave@forge.fwnet.us "rm -rf ~/wxcc-mcp && docker rmi wxcc-mcp:local"
```

Then remove the `wxcc-forge-*` entries from `.mcp.json`. The laptop servers are untouched throughout,
so this is a clean revert.

## Redeploying after a code change

```bash
scp wxcc.py mcp_server.py mcp_http.py requirements.txt Dockerfile dave@forge.fwnet.us:~/wxcc-mcp/app/
ssh dave@forge.fwnet.us "cd ~/wxcc-mcp/app && docker build -t wxcc-mcp:local ."
```

Restart Claude Code. Containers are `--rm` and per-connection, so there is nothing to stop or clean
up. **Note:** copying `.env*` with a multi-file `scp` from PowerShell silently drops dot-prefixed
names — copy them one at a time.
