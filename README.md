# EasyAI Client

This is the user-side app only. It is not a server.

It includes the original local EasyAI features:

- local chat with the user's own API key or Ollama
- file context
- edit proposals with preview/apply
- validation commands
- software download/install with confirmation
- terminal pet
- web task polling from the central server
- explicit permission modes through `/permission`
- update checking on every startup when installed from Git
- project memory and rule files like `AGENTS.md`, `CLAUDE.md`, `EASYAI.md`
- custom command prompts in `.easyai/commands/*.md`
- status, doctor, planning, compact, and review workflows

Users run:

```powershell
easyai
```

On Windows, `Easyai` also works because command lookup is case-insensitive.

## Install

One-line install after this folder is published to a Git repository:

```powershell
git clone <YOUR_EASYAI_CLIENT_GIT_URL> EasyAI && cd EasyAI && powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

If the repository is published as `https://github.com/<owner>/easyai-client.git`, users install with:

```powershell
git clone https://github.com/<owner>/easyai-client.git EasyAI && cd EasyAI && powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

Local install:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
```

## Configure

Edit `config.yaml` and `.env`, or keep the defaults and fill your own API key.

The server is:

```text
https://xingkongtech.top
```

Each user computer uses its own API key or local Ollama model. Account data, web chat history, computer status, and web task results are stored on the server.

The client only keeps local data required to operate this computer:

- `config.yaml`
- `.env`
- `easyai-data/client_session.json`
- `easyai-data/computer_id`
- files you explicitly download or edit

## Run

```powershell
easyai
```

or:

```powershell
.\Easyai.cmd
```

Log in with the website account. Keep this window open when you want the website to operate this computer.

Use `/help` inside EasyAI to see all local commands.

At first startup, choose `zh` or `en`. The choice is saved locally, so later startups do not ask again. Change it later with:

```text
/language zh
/language en
```

## Updates

When installed with Git, EasyAI checks `origin/main` every time it starts. If a new version is available, it asks before running:

```powershell
git pull --ff-only origin main
python -m pip install -e .
```

If the network is unavailable or the folder is not a Git clone, automatic update is skipped and EasyAI continues starting normally.

## Login

The first login must be verified by the server. After a successful login, EasyAI saves a local session in:

```text
easyai-data/client_session.json
```

Next startup uses the saved local account directly and does not ask for the password again. Server sync still runs in the background when the network is available.

To clear the local saved account:

```text
/logout
```

## Permission Modes

EasyAI starts in safe mode.

```text
/permission
/permission safe
/permission files
/permission downloads
/permission elevated
```

- `safe`: chat and server sync only
- `files`: allow file context, edit preview/apply, and validation commands
- `downloads`: allow files plus download/install flows
- `elevated`: allow admin install prompts after extra confirmation

High-risk actions still ask for confirmation even after switching modes.

## Agent Workflows

EasyAI now includes several Codex/Claude-Code style workflows:

```text
/status
/doctor
/init
/plan <task>
/memory
/memory add <text>
# <text>
/compact
/review [focus]
/commands
/<custom> [args]
```

- `/init` creates `AGENTS.md`, `.easyai/memory.md`, and `.easyai/commands/review.md`.
- `AGENTS.md`, `CLAUDE.md`, `EASYAI.md`, and `.easyai/memory.md` are loaded into the assistant automatically.
- `.easyai/commands/<name>.md` becomes `/<name>`, and `{{args}}` is replaced with command arguments.
- Important local actions are logged to `.easyai/audit.log`.

## Comparison

| Area | Claude Code / Codex style | EasyAI status |
| --- | --- | --- |
| Project rules | `CLAUDE.md` / `AGENTS.md` style instructions | Supports `AGENTS.md`, `CLAUDE.md`, `EASYAI.md` |
| Memory | Persisted project notes | Supports `.easyai/memory.md` and `# <text>` quick memory |
| Safety | Sandbox/approval modes | Supports `/permission safe/files/downloads/elevated` plus confirmations |
| Planning | Plan before edits | Supports `/plan <task>` |
| Review | Code review mode | Supports `/review [focus]` over loaded context |
| Custom commands | Reusable slash commands | Supports `.easyai/commands/*.md` |
| Context compaction | Keep long sessions usable | Supports `/compact` |
