# Connect Claude Code to Your Contact Center

This connects [Claude Code](https://claude.com/claude-code) to your company's Webex Contact Center (WxCC) configuration — teams, queues, sites, skills, and more — so you can ask questions and make changes in plain English, using your own Webex sign-in, with a safety check before anything is saved.

You don't need to write code, understand the underlying APIs, or install anything beyond Claude Code itself. This uses something called **MCP** (Model Context Protocol) — a standard way of giving Claude a specific set of tools to work with. You don't need to understand MCP either; "connecting an MCP server" is just what the steps below do. Nobody's password or account is shared — you sign in as yourself, and this connection only ever sees what your own Webex account is already allowed to see in your tenant.

> **New to Claude Code?** It's a command-line AI assistant — you type a request in plain English at a prompt, and it responds, asks clarifying questions, or takes an action, the same way you'd talk to a person.

---

## What you'll need before you start

Get these **three things** from whoever manages this connection for your company (your Contact Center admin or IT contact). Do not guess or reuse anything from another project:

| Item | What it looks like | How sensitive is it? |
|---|---|---|
| **Connection URL** | `https://wxcc-mcp-xxxxx.us-central1.run.app/mcp?org=xxxxxxxx-xxxx-...` | Not secret, but specific to your company |
| **Client ID** | A short identifier string | Not secret, but specific to your company |
| **Client Secret** | A longer string | **Treat like a password.** Ask for it over a secure channel, not plain email or chat if you can help it — and never paste it anywhere public |

You'll also pick **one thing yourself**: a short name for this connection, with no spaces — for example `wxcc-cloud-acme` if your company were named Acme. You'll use this name every time you ask Claude about your contact center.

You also need to be a **Contact Center administrator** for your organization's Webex tenant. If you're not sure whether you are, ask whoever gave you the three items above — this setup uses *your own* sign-in, so it only works if your account already has that access.

**Claude Code itself requires a paid plan** — a Claude Pro or Max subscription, or an Anthropic Console account with billing set up. A free claude.ai chat account is not enough on its own. If you don't already have Claude Code, check with whoever shared this document — they may have sent a referral link that includes a free trial period.

---

### 1. Confirm Claude Code is installed

Open a terminal and run:

```
claude --version
```

If that prints a version number, skip to Step 2. If it says the command isn't found, install Claude Code first — see [code.claude.com](https://code.claude.com) for instructions — then come back here. (You'll need a paid plan or trial to sign in — see the note above if you don't have one yet.)

### 2. Connect — one command

Fill the three items from your admin (and the name you picked) into the command below, then run it.

**On macOS or Linux:**
```bash
MCP_CLIENT_SECRET=PASTE_YOUR_CLIENT_SECRET claude mcp add-json wxcc-cloud-yourname '{"type":"http","url":"PASTE_YOUR_CONNECTION_URL","oauth":{"clientId":"PASTE_YOUR_CLIENT_ID","callbackPort":8484,"scopes":"cjp:config_read cjp:config cjp:config_write"}}' --client-secret --scope user
```

**On Windows (PowerShell):**
```powershell
$env:MCP_CLIENT_SECRET = "PASTE_YOUR_CLIENT_SECRET"
claude mcp add-json wxcc-cloud-yourname '{"type":"http","url":"PASTE_YOUR_CONNECTION_URL","oauth":{"clientId":"PASTE_YOUR_CLIENT_ID","callbackPort":8484,"scopes":"cjp:config_read cjp:config cjp:config_write"}}' --client-secret --scope user
```

Replace, in the command you use:
- `wxcc-cloud-yourname` — the name you picked (appears twice)
- `PASTE_YOUR_CLIENT_SECRET` — the Client Secret
- `PASTE_YOUR_CONNECTION_URL` — the whole Connection URL, including the `?org=...` part at the end — that's what points this at your specific organization
- `PASTE_YOUR_CLIENT_ID` — the Client ID

This command only needs to run **once**. `--scope user` means it works from any folder on your computer from now on, and there's no separate approval step to complete — you're ready to sign in immediately after it succeeds.

### 3. Sign in

```
claude mcp login wxcc-cloud-yourname --no-browser
```

(using the name you picked)

This prints a long web address. Then:

1. **Copy that address.**
2. **Open a private/incognito browser window** — do this even if you don't think you're signed in anywhere else. It avoids Claude accidentally reusing a leftover Webex session that isn't yours.
3. **Paste the address into that private window** and press enter.
4. **Sign in with the Webex account** that is a Contact Center administrator for your organization.
5. After you approve, the browser will try to redirect to a `localhost` address and will likely show a **"can't reach this page" / "connection refused"** error. **This is expected** — the important part already happened. Copy the full address from the browser's address bar at that point.
6. **Return to your terminal and paste that address in** when prompted.

If this succeeds, you're connected.

### 4. Verify you're talking to the right organization

Ask Claude, in plain English:

> Run wxcc_whoami on wxcc-cloud-yourname

(using the name you picked). Claude will state your organization's name and whether it's flagged as a production tenant. **Check that this is the organization you expect before asking it to do anything else.** If it isn't, stop and tell whoever gave you the connection details — don't try to fix it yourself.

---

## How this behaves once you're connected

- **Reading is always safe.** Asking "how many," "list," or "find" questions never changes anything.
- **Changes are never immediate.** If you ask Claude to create, update, or delete something, it first shows exactly what it's about to do and waits for you to confirm — nothing is saved until you say so.
- **Claude double-checks its own writes.** After you confirm a change, it reads the object back to prove the change actually took effect, rather than trusting a success message.
- **Deletions that would break something are refused, not attempted.** If another team, queue, or user still depends on what you're trying to delete, Claude tells you exactly what — instead of the delete failing partway through.
- **This connection only ever reaches your one organization.** There's no way to accidentally point a request at a different company's data through this setup.

---

## Example prompts and what to expect

Try these after connecting — they aren't real requests. Swap in your own team, site, or queue names once you've confirmed you're on the right tenant.

| You could ask | What you should get back |
|---|---|
| "Run wxcc_whoami" | Confirms the connection works, and states your organization's name and whether it's a production tenant |
| "How many teams do we have?" | A single number — the total team count |
| "List our sites" | A short list of site names, each marked active or inactive |
| "Find the queue named Sales" | Details about that one queue — its service-level threshold, routing type, and which teams serve it |
| "What wrap-up codes exist?" | A list of wrap-up code names |
| "Create a site called Test Office" | **Nothing is created yet** — a preview of exactly what would be sent, and a request for you to confirm |
| "Yes, go ahead" (right after that preview) | Only now does the site actually get created, followed by a read-back confirming it exists |
| "Delete the team named X" (when something still depends on it) | A refusal, with a list of exactly what's still using it — not a failed attempt |

---

*Questions, or something not matching what you see? Ask whoever manages this connection for your organization.*
