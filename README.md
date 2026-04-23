# EasyAI Client

This is the user-side app only. It is not a server.

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

Each user computer uses its own API key or local Ollama model. Account data, chat history, computer status, and task results are stored on the server.

## Run

```powershell
easyai
```

or:

```powershell
.\Easyai.cmd
```

Log in with the website account. Keep this window open when you want the website to operate this computer.
