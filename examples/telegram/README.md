# Paper Plane

A working Telegram-inspired chat and notes application, used to develop and test
our Python-to-Rust subset. All application logic and dynamic HTML rendering are
Python. The application contains **no handwritten Rust files**. General HTTP,
JSON and filesystem operations come from the reusable transpiler runtime.

## Run the web app

From the `py2rust` checkout:

```bash
python examples/telegram/tools/run.py
```

Open **http://127.0.0.1:8765**. This command transpiles the entire Python project,
builds it with Cargo, and starts the generated Rust binary. Subsequent builds are
incremental. The existing whole-project CLI also works:

```bash
py2rust-project run examples/telegram --offline
```

Create a profile and keep its access key. Use that key to sign in from another
browser or device. The account menu shows the key again. The app creates two
private notebooks; use **+ → Saved notebook** for more. **+ → Shared chat** creates
a room visible to everyone signed in to this server. Profiles with the same
server can exchange messages. There is no Telegram service integration.

- **Bold** and *italic*, including combined formatting; toolbar buttons and
  Ctrl+B / Ctrl+I insert the Markdown markers. Enter sends, Shift+Enter adds a line.
- Paste a screenshot with Ctrl+V, drop files into the conversation, or use the
  paperclip. PNG, JPEG, GIF and WebP show previews. All file types can be attached.
- Up to 10 attachments per message, each up to 32 MiB; messages up to 16,000 characters.
- Search message text and filenames across visible conversations. The header's
  search button narrows results to the current conversation. Click a result to jump.
- Rename your notebooks/rooms, edit or delete your own messages, and keep unsent
  text drafts locally. Updates from other clients arrive approximately every 1.5 seconds.
- Private notebooks and their files are checked on the server, including search
  and direct download URLs. Sharing an attachment in a shared room makes it
  available to members of that room.

## Linux x64 desktop

Build the portable package with `npm ci` followed by `npm run package` in this directory.
The generated package is placed in `dist/paper-plane-linux-x64/`. Then launch:

```bash
./examples/telegram/dist/paper-plane-linux-x64/paper-plane
```

The archive `dist/paper-plane-linux-x64.tar.gz` can be extracted on another Linux
x64 desktop. It bundles Electron, the generated Rust server, and the web assets;
Python, Node and Cargo are not needed to run it. Normal Linux desktop libraries
(GTK, NSS, etc.) are required, as with other Electron applications.

For development, from this directory:

```bash
npm ci
npm run desktop
npm run package
```

The desktop launcher automatically rebuilds the Python project. It starts a local
Rust server on a free port and closes that server when the window closes.
The desktop uses the same UI and application code as the web version.
The current locked Electron release requires Node 22.12 or newer for development.

To use the desktop as a client of the already running web server:

```bash
PAPER_PLANE_URL=http://127.0.0.1:8765 ./dist/paper-plane-linux-x64/paper-plane
```

For other computers on your LAN, start the server with
`PAPER_PLANE_HOST=0.0.0.0`, then use that computer's address in browsers or
`PAPER_PLANE_URL`. Default startup binds to loopback. For an Internet deployment,
put an HTTPS reverse proxy in front of the server; the built-in app endpoint is HTTP.

## Data and source layout

Web data defaults to `examples/telegram/data/`; desktop data goes in its standard
user application directory. `PAPER_PLANE_DATA` selects a different directory.
Back up the **whole directory**: `state.json` contains accounts, rooms and messages,
and `uploads/` contains attachments. Profile access keys in this directory are
credentials. Stop the server before restoring a backup. Do not run two server
processes against the same data directory.

| Source | Responsibility |
| --- | --- |
| `main.py` | Startup and HTTP entry |
| `app/api.py` | Request routing, accounts, messages, uploads/downloads |
| `app/model.py` | Permissions, search matching, conversation rules |
| `app/store.py` | Readable JSON persistence, atomic replacement |
| `app/render.py` | Escaped HTML, formatting, messages and search results |
| `web/index.html`, `web/app.css` | Static shell and appearance |
| `web/app.js` | DOM events, clipboard/file picker, polling and local drafts |
| `desktop/main.cjs` | Electron window and server lifecycle |
| `tools/` | Development/build tooling, outside the transpiled application |

Read the generated code at `.py2rust/rust/src/main.rs`. Names such as
`py__app__model__find_chat` identify their Python module and function. Function
docstrings and source locations are retained. The `.py2rust-project.json` symbol
map links every generated name to its original source. Edit Python, then rebuild;
the transpiler protects generated files from accidental overwrite of hand edits.

This application also runs directly with the Python reference runtime:

```bash
cd examples/telegram
../../python main.py
```

The Rust binary runs independently of Python. UI rendering, validation,
authorization, search, MIME recognition and storage orchestration are transpiled.
JavaScript is limited to browser/desktop integration; Rust is limited to reusable
runtime adapters. Calls, voice messages and end-to-end encryption are out of scope.

## Transpiler changes exercised here

- General `WebRequest` / `WebResponse` and long-running `web_serve` with binary bodies.
- JSON array extraction, defaulted object lookup, type checks and fallible parsing.
- Atomic file replacement, environment lookup, random tokens and URL quoting.
- Unicode string slices, byte prefix/suffix checks, mutable loop variables,
  safe evaluation order for JSON updates that read the same object.
- Clearer generated names, retained function documentation, and copying only
  the requested HTTP field instead of cloning an entire uploaded request.

The prototype uses an inspectable JSON store and renders the full conversation.
It is intended for small personal/team deployments; indexing, pagination and a
transactional database are sensible next work for very large histories.
Markdown support is intentionally limited to bold/italic; arbitrary HTML is escaped.
Regular chats are shared rooms, rather than one-to-one contact conversations.

## Verification

From the repository root:

```bash
python -m pytest tests/test_telegram.py -q
```

The same end-to-end workflow runs against CPython and generated Rust: two users,
private notebooks, shared messages, formatting and HTML escaping, image/file
uploads, exact-byte downloads, text/filename search, edits/deletions, permissions,
concurrent writes, and recovery after a process restart. The renamed package passed the project/chat regression checks recorded in
[the migration verification note](../../doc/VERIFICATION.md). Run the browser and
packaged desktop checks again after rebuilding; old screenshots and reports do
not verify a new package.
