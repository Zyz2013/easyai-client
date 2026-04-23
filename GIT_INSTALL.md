# One-Line Git Install

Git alone cannot safely run install scripts during `git clone`. That is intentional: Git does not execute repository code on clone.

Use this one-line PowerShell command after publishing this `easyai-client` folder to a Git repository:

```powershell
git clone <YOUR_EASYAI_CLIENT_GIT_URL> EasyAI && cd EasyAI && powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

Example after replacing the URL:

```powershell
git clone https://github.com/your-name/easyai-client.git EasyAI && cd EasyAI && powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

After install, users run:

```powershell
.\Easyai.cmd
```

or, inside the activated environment:

```powershell
easyai
```
