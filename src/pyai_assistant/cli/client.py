from __future__ import annotations

import json
import shlex
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table

from pyai_assistant.agent.session import AssistantAgent
from pyai_assistant.cli.model_setup import ensure_model_connection
from pyai_assistant.cli.pet import TerminalPet
from pyai_assistant.cli.secret_input import prompt_secret
from pyai_assistant.config import load_config, load_local_config_files, write_local_config
from pyai_assistant.providers.factory import build_provider
from pyai_assistant.providers.server_api import (
    ServerApiClient,
    clear_client_session,
    load_client_session,
    save_client_session,
    utc_now,
)
from pyai_assistant.runtime.computer import load_computer_identity
from pyai_assistant.runtime.downloader import SoftwareDownloader, looks_like_download_request, parse_download_request
from pyai_assistant.runtime.executor import PythonRunner
from pyai_assistant.runtime.updater import GitUpdater
from pyai_assistant.types import AssistantResult, Message, RunRequest, SessionState, WorkspaceChange
from pyai_assistant.workspace.manager import WorkspaceManager


PERMISSION_LEVELS = {"safe", "files", "downloads", "elevated"}
LANGUAGES = {"zh", "en"}

TEXT = {
    "zh": {
        "first_login": "首次登录必须通过服务器验证。",
        "saved_account": "使用本地保存账号:",
        "username": "用户名",
        "password": "密码",
        "login_failed": "服务器登录失败:",
        "login_hint": "如果包含 Cloudflare 1010/403，请确认客户端已更新，或在 Cloudflare 放行 /api/*。",
        "login_saved": "服务器登录验证成功。本地账号已保存，下次启动不需要再次输入密码。",
        "client_stopped": "客户端已停止。",
        "sync_error": "服务端同步错误:",
        "task_received": "收到网页任务",
        "task_completed": "网页任务完成",
        "task_failed": "网页任务失败:",
        "preparing": "正在准备回答。",
        "request_failed": "请求失败。",
        "ready": "已就绪。",
        "command_failed": "命令执行失败:",
        "logout_cleared": "本地保存账号已清除。下次启动需要重新通过服务器登录。",
        "stopped": "客户端已停止。",
        "unknown": "未知命令。输入 /help 查看帮助。",
        "provider_set": "Provider 已设置为",
        "model_set": "模型已设置为",
        "mode_set": "模式已设置为",
        "session_reset": "会话已重置。",
        "permission_current": "当前权限:",
        "permission_confirm": "确认启用高权限模式？管理员操作仍会再次确认。",
        "permission_set": "权限已设置为",
        "permission_error": "当前权限是 {current}。请先运行 /permission {required}。",
        "pet_enabled": "宠物已开启。",
        "pet_disabled": "宠物已关闭。",
        "download_empty": "请指定软件名或 URL。",
        "download_url": "确认下载 URL 到当前工作区 downloads/？",
        "downloaded": "下载完成:",
        "install_confirm": "确认使用 winget 安装 {query}？",
        "admin_confirm": "确认对 {query} 使用管理员权限？",
        "search_confirm": "确认用 winget 搜索 {query}？",
        "no_pending": "没有待应用修改。",
        "no_run": "没有建议运行的验证命令。可用 /run demo.py 或 /run pytest tests。",
        "language_set": "语言已切换为中文。",
        "server": "服务器",
        "user": "用户",
        "computer": "电脑",
        "provider": "模型来源",
        "model": "模型",
        "mode": "模式",
        "permission": "权限",
        "help": "帮助",
        "client_title": "EasyAI 客户端",
        "help_title": "帮助",
        "help_topics_line": "可用主题: files, run, pet, download, account, permission, agent",
        "help_examples_title": "常用示例",
        "help_unknown_topic": "未知帮助主题: {topic}",
        "update_check": "正在检查更新...",
        "update_unavailable": "无法自动检查更新:",
        "update_available": "发现新版本 {local} -> {remote}，是否现在更新？",
        "update_done": "更新完成。请重新打开 EasyAI。",
        "update_failed": "更新失败:",
        "update_none": "已是最新版本。",
        "help_short": """\
帮助
  /help files       文件与上下文
  /help run         运行与验证
  /help pet         宠物功能
  /help download    下载与安装
  /help account     账号、模型、语言
  /help permission  权限模式
  /help agent       状态、记忆、计划、审查

可用主题: files, run, pet, download, account, permission, agent

常用示例
  /permission files
  /open app.py
  /mode edit
  /apply
  下载 VS Code
""",
        "help_files": """\
文件和上下文
  /files                  列出当前工作区可读取文件
  /open <file>            打开文件并加入上下文
  /context add <file>     手动加入上下文
  /context remove <file>  从上下文移除
  /reset                  清空会话、上下文、待应用修改
""",
        "help_run": """\
验证命令
  /run demo.py
  /run python demo.py arg
  /run pytest tests
  /run node index.js
  /run npm test

说明
  只允许受控运行，不执行任意 shell
  包管理器默认阻止 install/add/remove/publish/exec 等高风险动作
""",
        "help_pet": """\
宠物
  /pet         查看宠物卡片
  /pet status  查看状态
  /pet on      开启宠物
  /pet off     关闭宠物
""",
        "help_download": """\
下载/安装
  /download chrome
  /download 微信
  /download chrome --install
  /download chrome --install --admin
  下载 VS Code
  安装 Python

说明
  普通下载默认保存到当前工作区 downloads/
  软件名会优先走 winget 搜索/安装流程
  安装和管理员权限都会再次确认
""",
        "help_account": """\
账号/模型
  /language zh|en
  /provider openai_compatible
  /provider ollama
  /model <name>
  /mode chat|code|edit
  /logout
  /quit

说明
  语言、模型连接、权限都会保留旧配置
  下次启动会优先询问是否继续使用旧配置
  首次登录必须通过服务端验证
""",
        "help_permission": """\
权限模式
  /permission            查看当前模式
  /permission safe       仅聊天与服务端同步
  /permission files      允许读写文件、应用修改、验证
  /permission downloads  允许下载与安装流程
  /permission elevated   允许管理员安装提示

说明
  权限设置会保存，下次启动自动沿用
  高风险操作即使已提权仍会再次确认
""",
        "help_agent": """\
Agent 工作区能力
  /status         查看账号、模型、权限、上下文、服务器
  /doctor         检查 Git、配置、API Key、Ollama、可见文件
  /init           初始化 AGENTS.md 和 .easyai 工作区文件
  /plan <task>    先生成计划，不直接改文件
  /memory         查看项目记忆
  /memory add ... 追加项目记忆
  /compact        压缩旧对话
  /review [focus] 审查已加载上下文
  /commands       列出自定义命令

说明
  # <text> 等同于快速追加记忆
  /<custom> [args] 可执行 .easyai/commands/<custom>.md
  会自动读取 AGENTS.md、CLAUDE.md、EASYAI.md、.easyai/memory.md
""",
        "permission_title": "权限",
        "loaded_context": "已加载上下文",
        "added_context": "已添加上下文:",
        "removed_context": "已移除上下文:",
        "apply_confirm": "是否应用修改到 {path}？",
        "run_suggested_now": "现在运行建议的验证命令？",
        "run_suggested": "运行建议的验证命令？",
        "workspace_files": "工作区文件",
        "status_title": "EasyAI 状态",
        "doctor_title": "EasyAI 诊断",
        "install_root": "安装目录",
        "workspace": "工作区",
        "language": "语言",
        "context_files": "上下文文件",
        "pending_changes": "待应用修改",
        "project_memory": "项目记忆",
        "yes": "是",
        "no": "否",
        "config_file": "配置文件",
        "api_key": "API Key",
        "ollama": "Ollama",
        "files_visible": "可见文件",
        "rule_files": "规则文件",
        "initialized": "EasyAI 工作区文件已初始化。",
        "plan_empty": "计划任务为空。",
        "memory_empty": "记忆内容为空。",
        "clear_memory": "清空项目记忆？",
        "memory_saved": "记忆已保存。",
        "not_enough_compact": "会话太短，不需要压缩。",
        "conversation_compacted": "会话已压缩。",
        "load_context_first": "请先用 /open 或 /context add 加载上下文。",
        "custom_commands": "自定义命令",
        "file": "文件",
        "none": "无",
    },
    "en": {
        "first_login": "First login requires server verification.",
        "saved_account": "Using saved local account:",
        "username": "Username",
        "password": "Password",
        "login_failed": "Server login failed:",
        "login_hint": "If it contains Cloudflare 1010/403, make sure the client is updated or allow /api/* in Cloudflare.",
        "login_saved": "Server login verified. Local account saved for next startup.",
        "client_stopped": "Client stopped.",
        "sync_error": "Server sync error:",
        "task_received": "Web task received",
        "task_completed": "Web task completed",
        "task_failed": "Web task failed:",
        "preparing": "Preparing answer.",
        "request_failed": "Request failed.",
        "ready": "Ready.",
        "command_failed": "Command failed:",
        "logout_cleared": "Local saved account cleared. Next startup will require server login.",
        "stopped": "Client stopped.",
        "unknown": "Unknown command. Type /help.",
        "provider_set": "Provider set to",
        "model_set": "Model set to",
        "mode_set": "Mode set to",
        "session_reset": "Session reset.",
        "permission_current": "Current permission:",
        "permission_confirm": "Enable elevated mode? Admin actions will still ask again.",
        "permission_set": "Permission set to",
        "permission_error": "Current permission is {current}. Run /permission {required} first.",
        "pet_enabled": "Pet enabled.",
        "pet_disabled": "Pet disabled.",
        "download_empty": "Specify software name or URL.",
        "download_url": "Download URL into workspace downloads/?",
        "downloaded": "Downloaded:",
        "install_confirm": "Install {query} with winget?",
        "admin_confirm": "Use administrator permission for {query}?",
        "search_confirm": "Search {query} with winget?",
        "no_pending": "No pending changes.",
        "no_run": "No suggested run. Use /run demo.py or /run pytest tests.",
        "language_set": "Language switched to English.",
        "server": "Server",
        "user": "User",
        "computer": "Computer",
        "provider": "Provider",
        "model": "Model",
        "mode": "Mode",
        "permission": "Permission",
        "help": "Help",
        "client_title": "EasyAI Client",
        "help_title": "Help",
        "help_topics_line": "Topics: files, run, pet, download, account, permission, agent",
        "help_examples_title": "Common examples",
        "help_unknown_topic": "Unknown help topic: {topic}",
        "session_restored": "Restored saved workspace state from .easyai/runtime-state.json.",
        "update_check": "Checking for updates...",
        "update_unavailable": "Automatic update check unavailable:",
        "update_available": "Update available {local} -> {remote}. Update now?",
        "update_done": "Update complete. Please restart EasyAI.",
        "update_failed": "Update failed:",
        "update_none": "Already up to date.",
        "help_short": """\
Help
  /help files       Files and context
  /help run         Run and validation
  /help pet         Pet features
  /help download    Download and install
  /help account     Account, model, language
  /help permission  Permission modes
  /help agent       Status, memory, plan, review

Topics: files, run, pet, download, account, permission, agent

Common examples
  /permission files
  /open app.py
  /mode edit
  /apply
  download VS Code
""",
        "help_files": """\
Files and context
  /files                  List readable files in the current workspace
  /open <file>            Open a file and load it into context
  /context add <file>     Add context manually
  /context remove <file>  Remove a context file
  /reset                  Clear session, context, and pending changes
""",
        "help_run": """\
Validation commands
  /run demo.py
  /run python demo.py arg
  /run pytest tests
  /run node index.js
  /run npm test

Notes
  Controlled execution only, no arbitrary shell
  Package managers block risky install/add/remove/publish/exec by default
""",
        "help_pet": """\
Pet
  /pet         Show the pet card
  /pet status  Show current state
  /pet on      Enable the pet
  /pet off     Disable the pet
""",
        "help_download": """\
Download/install
  /download chrome
  /download wechat
  /download chrome --install
  /download chrome --install --admin
  download VS Code
  install Python

Notes
  Plain downloads go into workspace downloads/
  Software names use winget search/install flows
  Install and admin actions always ask for confirmation
""",
        "help_account": """\
Account/model
  /language zh|en
  /provider openai_compatible
  /provider ollama
  /model <name>
  /mode chat|code|edit
  /logout
  /quit

Notes
  Language, model connection, and permission keep the last saved config
  Startup asks whether to keep the previous model config
  First login must be verified by the server
""",
        "help_permission": """\
Permission modes
  /permission            Show current mode
  /permission safe       Chat and server sync only
  /permission files      Allow file read/edit/apply and validation
  /permission downloads  Allow download and install flows
  /permission elevated   Allow admin install prompts

Notes
  Permission mode is saved and reused on next startup
  High-risk actions still ask for confirmation
""",
        "help_agent": """\
Agent workspace features
  /status         Show account, model, permission, context, server
  /doctor         Check Git, config, API key, Ollama, visible files
  /init           Create AGENTS.md and .easyai workspace files
  /plan <task>    Generate a plan first
  /memory         Show project memory
  /memory add ... Append project memory
  /compact        Compact older chat turns
  /review [focus] Review loaded context
  /commands       List custom commands

Notes
  # <text> is a quick memory shortcut
  /<custom> [args] runs .easyai/commands/<custom>.md
  Rule files are auto-loaded from AGENTS.md, CLAUDE.md, EASYAI.md, .easyai/memory.md
""",
        "permission_title": "Permission",
        "loaded_context": "Loaded Context",
        "added_context": "Added context:",
        "removed_context": "Removed context:",
        "apply_confirm": "Apply changes to {path}?",
        "run_suggested_now": "Run suggested validation now?",
        "run_suggested": "Run suggested validation command?",
        "workspace_files": "Workspace Files",
        "status_title": "EasyAI Status",
        "doctor_title": "EasyAI Doctor",
        "install_root": "Install root",
        "workspace": "Workspace",
        "language": "Language",
        "context_files": "Context files",
        "pending_changes": "Pending changes",
        "project_memory": "Project memory",
        "yes": "yes",
        "no": "no",
        "config_file": "Config file",
        "api_key": "API key",
        "ollama": "Ollama",
        "files_visible": "Files visible",
        "rule_files": "Rule files",
        "initialized": "Initialized EasyAI workspace files.",
        "plan_empty": "Plan task is empty.",
        "memory_empty": "Memory text is empty.",
        "clear_memory": "Clear project memory?",
        "memory_saved": "Memory saved.",
        "not_enough_compact": "Not enough conversation to compact.",
        "conversation_compacted": "Conversation compacted.",
        "load_context_first": "Load context first with /open or /context add.",
        "custom_commands": "Custom Commands",
        "file": "File",
        "none": "none",
    },
}

HELP_SHORT = """\
Help topics
  /help files       Files/context: list, open, add/remove context, reset
  /help run         Validation: Python, pytest, Node, npm/pnpm/yarn/bun test
  /help pet         Pet: status, on, off
  /help download    Download/install: URL, winget search, confirmed install
  /help account     Server account, provider, model, mode, logout
  /help permission  Permission modes and switching
  /help agent       Status, doctor, init, memory, compact, review, custom commands
  /language zh|en   Switch CLI language

Common flow
  /open <file>
  /mode edit
  /apply
"""

HELP_TOPICS: Dict[str, str] = {
    "files": """\
Files and context
  /files                         List readable code/text files
  /open <file>                   Open and add file context
  /context add <file>            Add context file
  /context remove <file>         Remove context file
  /reset                         Clear session, context, pending changes
""",
    "run": """\
Validation commands
  /run demo.py
  /run python demo.py arg
  /run pytest tests
  /run node index.js
  /run npm test

Safety: no arbitrary shell. Package managers block risky install/add/remove/publish/exec by default.
""",
    "pet": """\
Pet
  /pet
  /pet status
  /pet on
  /pet off
""",
    "download": """\
Download/install
  download Chrome
  install VS Code
  /download chrome
  /download https://example.com/file.exe
  /download chrome --install
  /download chrome --install --admin

Default only downloads into workspace downloads/ or searches winget. Install and admin require confirmation.
""",
    "account": """\
Account/model
  /language zh|en                Switch CLI language
  /permission                    Show current permission mode
  /permission safe               Safe mode: chat + server sync only
  /permission files              Allow file context/edit after confirmation
  /permission downloads          Allow files + downloads/install after confirmation
  /permission elevated           Allow downloads + admin actions after extra confirmation
  /provider openai_compatible
  /provider ollama
  /model <name>
  /mode chat|code|edit
  /logout
  /quit
""",
    "permission": """\
Permission modes
  /permission                    Show current mode
  /permission safe               Chat and server sync only
  /permission files              Allow file read/edit/apply and validation
  /permission downloads          Allow files plus download/install flows
  /permission elevated           Allow admin install prompts after extra confirmation

Default mode is safe. High-risk actions still ask for confirmation.
""",
    "agent": """\
Agent workspace features
  /status                        Show session, context, account, permission, and server state
  /doctor                        Check Git, config, API key, Ollama hint, and workspace files
  /init                          Create AGENTS.md, .easyai/memory.md, and example custom commands
  /plan <task>                   Ask for an implementation plan without applying changes
  /memory                        Show project memory
  /memory add <text>             Append project memory
  # <text>                       Quick memory append, same as /memory add
  /compact                       Summarize old chat turns and keep recent context
  /review [focus]                Ask for a code-review style pass over loaded context
  /commands                      List .easyai/commands/*.md custom commands
  /<custom> [args]               Run a custom command prompt from .easyai/commands/<custom>.md

Project rule files loaded automatically: AGENTS.md, CLAUDE.md, EASYAI.md, .easyai/memory.md.
""",
}

HELP_PAGES: Dict[str, Dict[str, str]] = {
    "zh": {
        "": """\
帮助总览
作用
  /help 用来查看命令的用途、适合什么场景、以及具体怎么输入。

使用方法
  /help files
  /help run
  /help pet
  /help download
  /help account
  /help permission
  /help agent

主题说明
  files        文件浏览、打开文件、管理上下文、重置会话
  run          运行 Python/pytest/node 等验证命令
  pet          查看或切换宠物状态
  download     下载软件、搜索 winget、确认安装
  account      语言、模型来源、模型名、模式、登录退出
  permission   查看和切换权限级别
  agent        状态、诊断、初始化、记忆、压缩、审查、自定义命令

常见流程
  1. /permission files
  2. /open app.py
  3. /mode edit
  4. 直接描述你要改什么
  5. /apply
  6. /run pytest tests
""",
        "files": """\
文件与上下文
作用
  让 EasyAI 读取当前项目文件，并把这些文件作为后续对话上下文。

使用方法
  /files
  /open <文件路径>
  /context add <文件路径>
  /context remove <文件路径>
  /reset

示例
  /open src/app.py
  /context add tests/test_app.py
  /context remove tests/test_app.py

说明
  /open 会同时打开并加入上下文。
  /context add/remove 只管理上下文，不显示文件内容。
  /reset 会清空当前会话、上下文和待应用修改。
""",
        "run": """\
运行与验证
作用
  在受控环境里运行验证命令，检查修改是否真的可用。

使用方法
  /run demo.py
  /run python demo.py arg1
  /run pytest tests
  /run node index.js
  /run npm test

示例
  /run pytest tests/test_login.py
  /run python scripts/demo.py

说明
  这里只允许受控命令，不执行任意 shell。
  npm/pnpm/yarn/bun 默认会拦截 install/add/remove/publish/exec 这类高风险动作。
""",
        "pet": """\
宠物功能
作用
  显示 EasyAI 的终端宠物状态，辅助观察当前是否在思考、空闲或报错。

使用方法
  /pet
  /pet status
  /pet on
  /pet off

示例
  /pet off
  /pet on
""",
        "download": """\
下载与安装
作用
  下载文件，或通过 winget 搜索并安装软件。

使用方法
  /download <软件名>
  /download <URL>
  /download <软件名> --install
  /download <软件名> --install --admin
  也可以直接输入自然语言，例如：下载 VS Code

示例
  /download chrome
  /download https://example.com/file.exe
  /download python --install
  下载微信

说明
  普通下载默认保存到当前工作区 downloads/。
  软件名会优先走 winget 搜索/安装流程。
  安装和管理员权限操作都会再次确认。
""",
        "account": """\
账号与模型
作用
  管理语言、模型连接、模型名、会话模式，以及登录状态。

使用方法
  /language zh
  /language en
  /provider openai_compatible
  /provider ollama
  /model <模型名>
  /mode chat|code|edit
  /logout
  /quit

示例
  /provider ollama
  /model deepseek-v4-flash
  /mode edit

说明
  语言、模型连接和权限都会保留上次配置。
  启动时会先询问是否继续使用旧的模型连接配置。
  首次登录必须通过服务端验证。
""",
        "permission": """\
权限管理
作用
  决定 EasyAI 当前允许做到哪一步。

使用方法
  /permission
  /permission safe
  /permission files
  /permission downloads
  /permission elevated

权限说明
  safe        只聊天和服务端同步
  files       允许读写文件、应用修改、运行验证
  downloads   在 files 基础上允许下载和安装流程
  elevated    在 downloads 基础上允许管理员安装提示

说明
  权限会保存，下次启动自动沿用。
  即使已经提权，高风险操作仍然会再次确认。
""",
        "agent": """\
Agent 工作区能力
作用
  查看状态、做诊断、初始化规则文件、保存记忆、压缩会话、做代码审查。

使用方法
  /status
  /doctor
  /init
  /plan <任务>
  /memory
  /memory add <内容>
  /compact
  /review [重点]
  /commands
  /<自定义命令> [参数]

示例
  /plan 给登录流程补充错误处理
  /memory add 这个项目优先兼容 Windows
  /review 安全问题

说明
  # <内容> 等同于快速执行 /memory add <内容>。
  会自动读取 AGENTS.md、CLAUDE.md、EASYAI.md、.easyai/memory.md。
  对话和当前进度会实时保存到 .easyai/runtime-state.json，突然退出后下次会恢复。
""",
    },
    "en": {
        "": """\
Help overview
Purpose
  /help explains what a command does, when to use it, and the exact input format.

How to use
  /help files
  /help run
  /help pet
  /help download
  /help account
  /help permission
  /help agent

Topics
  files        Browse files, open files, manage context, reset session
  run          Run Python, pytest, Node, and test commands
  pet          Show or toggle the pet state
  download     Download software, search winget, confirm installs
  account      Language, provider, model, mode, login/logout
  permission   Show and switch permission levels
  agent        Status, doctor, init, memory, compact, review, custom commands

Common flow
  1. /permission files
  2. /open app.py
  3. /mode edit
  4. describe the change you want
  5. /apply
  6. /run pytest tests
""",
        "files": """\
Files and context
Purpose
  Let EasyAI read project files and use them as context for the next turns.

How to use
  /files
  /open <path>
  /context add <path>
  /context remove <path>
  /reset

Examples
  /open src/app.py
  /context add tests/test_app.py
  /context remove tests/test_app.py

Notes
  /open both shows the file and adds it to context.
  /context add/remove only manages context.
  /reset clears the active session, context, and pending changes.
""",
        "run": """\
Run and validation
Purpose
  Run controlled validation commands so we can confirm the change actually works.

How to use
  /run demo.py
  /run python demo.py arg1
  /run pytest tests
  /run node index.js
  /run npm test

Examples
  /run pytest tests/test_login.py
  /run python scripts/demo.py

Notes
  This only allows controlled commands, not arbitrary shell.
  npm/pnpm/yarn/bun block risky install/add/remove/publish/exec actions by default.
""",
        "pet": """\
Pet
Purpose
  Show EasyAI's terminal pet so you can see whether it is idle, thinking, or in an error state.

How to use
  /pet
  /pet status
  /pet on
  /pet off
""",
        "download": """\
Download and install
Purpose
  Download files or search/install software with winget.

How to use
  /download <software name>
  /download <URL>
  /download <software name> --install
  /download <software name> --install --admin
  You can also use natural language, for example: download VS Code

Examples
  /download chrome
  /download https://example.com/file.exe
  /download python --install
  download WeChat

Notes
  Plain downloads go into the current workspace downloads/ folder.
  Software names use winget search/install flows first.
  Install and admin actions always ask for confirmation.
""",
        "account": """\
Account and model
Purpose
  Manage language, model connection, model name, chat mode, and login state.

How to use
  /language zh
  /language en
  /provider openai_compatible
  /provider ollama
  /model <model name>
  /mode chat|code|edit
  /logout
  /quit

Examples
  /provider ollama
  /model deepseek-v4-flash
  /mode edit

Notes
  Language, model connection, and permission reuse the last saved config.
  Startup asks whether to keep the previous model connection.
  The first login must be verified by the server.
""",
        "permission": """\
Permission
Purpose
  Decide how far EasyAI is allowed to go in the current session.

How to use
  /permission
  /permission safe
  /permission files
  /permission downloads
  /permission elevated

Levels
  safe        Chat and server sync only
  files       File read/write, apply changes, run validation
  downloads   files plus download and install flows
  elevated    downloads plus admin install prompts

Notes
  Permission is saved and reused on next startup.
  High-risk actions still ask for confirmation.
""",
        "agent": """\
Agent workspace features
Purpose
  Inspect status, run diagnostics, initialize rule files, keep project memory, compact chat, and review code.

How to use
  /status
  /doctor
  /init
  /plan <task>
  /memory
  /memory add <text>
  /compact
  /review [focus]
  /commands
  /<custom> [args]

Examples
  /plan add better error handling to login
  /memory add This project should stay Windows-friendly
  /review security issues

Notes
  # <text> is a shortcut for /memory add <text>.
  EasyAI auto-loads AGENTS.md, CLAUDE.md, EASYAI.md, and .easyai/memory.md.
  Conversation and progress are saved live in .easyai/runtime-state.json and restored after abrupt exits.
""",
    },
}


class EasyAIClient:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.app_root = GitUpdater.discover_root(Path(__file__))
        self.console = Console()
        self.config = load_config(self.app_root)
        self.computer = load_computer_identity(self.app_root)
        self.session = load_client_session(self.app_root)
        self.api = ServerApiClient(self.config.app_base_url, self.session.get("token"))
        self.workspace = WorkspaceManager(self.root)
        self.easyai_dir = self.root / ".easyai"
        self.memory_path = self.easyai_dir / "memory.md"
        self.commands_dir = self.easyai_dir / "commands"
        self.audit_path = self.easyai_dir / "audit.log"
        self.runtime_state_path = self.easyai_dir / "runtime-state.json"
        restored_state = self._load_runtime_state()
        self.restored_runtime_state = self._has_runtime_state_data(restored_state)
        self.agent = AssistantAgent(build_provider(self.config.provider), self.config, self.workspace, state=restored_state)
        self.runner = PythonRunner(self.workspace)
        self.downloader = SoftwareDownloader(self.root)
        self.updater = GitUpdater(self.app_root)
        self.pet = TerminalPet()
        self.stop_event = threading.Event()
        self.poller: Optional[threading.Thread] = None
        self.permission = self._load_saved_permission()
        self.language = "zh"

    def run(self) -> None:
        self._choose_language()
        self._check_update()
        self._ensure_model_connection()
        self._ensure_login()
        self._start_background_client()
        self._render_header()
        if self.restored_runtime_state:
            restored_message = (
                "已恢复 .easyai/runtime-state.json 中保存的工作区状态。"
                if self.language == "zh"
                else self._t("session_restored")
            )
            self.console.print("[green]%s[/]" % restored_message)
        while True:
            try:
                user_input = Prompt.ask("[bold cyan]%s@easyai[/] " % self.session.get("username", "user"))
            except (EOFError, KeyboardInterrupt):
                self.stop_event.set()
                self.console.print("\n%s" % self._t("client_stopped"))
                return

            if not user_input.strip():
                continue
            if user_input.lstrip().startswith("#"):
                self._quick_memory(user_input.lstrip()[1:].strip())
                self._save_runtime_state()
                continue
            if user_input.startswith("/"):
                try:
                    should_exit = self._handle_command(user_input)
                    if should_exit:
                        self.stop_event.set()
                        return
                except Exception as exc:
                    self.console.print("[red]%s[/] %s" % (self._t("command_failed"), exc))
                else:
                    self._save_runtime_state()
                continue
            if looks_like_download_request(user_input):
                self._handle_download_text(user_input)
                self._save_runtime_state()
                continue
            self._ask_local_ai(user_input)
            self._save_runtime_state()

    def _choose_language(self) -> None:
        saved = str(self.session.get("language", "")).lower()
        if saved in LANGUAGES:
            self.language = saved
            return
        choice = Prompt.ask("Language / 语言", choices=["zh", "en"], default="zh")
        self.language = choice
        self.session["language"] = choice
        save_client_session(self.app_root, self.session)

    def _t(self, key: str, **kwargs: object) -> str:
        value = TEXT[self.language][key]
        return value.format(**kwargs) if kwargs else value

    def _check_update(self) -> None:
        self.console.print(self._t("update_check"))
        try:
            status = self.updater.check()
        except Exception as exc:
            self.console.print("[yellow]%s[/] %s" % (self._t("update_unavailable"), exc))
            return
        if status.offline:
            return
        if status.message:
            self.console.print("[yellow]%s[/] %s" % (self._t("update_unavailable"), status.message))
            return
        if not status.available:
            self.console.print("[green]%s[/]" % self._t("update_none"))
            return
        if Confirm.ask(self._t("update_available", local=status.local_revision, remote=status.remote_revision), default=True):
            try:
                self.updater.update()
            except Exception as exc:
                self.console.print("[red]%s[/] %s" % (self._t("update_failed"), exc))
                return
            self.console.print("[green]%s[/]" % self._t("update_done"))
            raise SystemExit(0)

    def _ensure_model_connection(self) -> None:
        self.config = ensure_model_connection(self.app_root, self.console, self.language)
        self.agent.config = self.config
        self.agent.provider = build_provider(self.config.provider)

    def _ensure_login(self) -> None:
        if self.session.get("token"):
            self.api.token = self.session["token"]
            self.console.print("[green]%s[/] %s" % (self._t("saved_account"), self.session.get("username", "user")))
            return
        self.console.print(self._t("first_login"))
        username = Prompt.ask(self._t("username"))
        password = prompt_secret(self.console, self._t("password"))
        try:
            payload = self.api.login(username, password, self.computer.name)
        except Exception as exc:
            self.console.print("[red]%s[/] %s" % (self._t("login_failed"), exc))
            self.console.print("[yellow]%s[/]" % self._t("login_hint"))
            raise SystemExit(1)
        self.session = {
            "token": payload["token"],
            "username": username,
            "verified_at": utc_now(),
            "server": self.config.app_base_url,
            "language": self.language,
        }
        save_client_session(self.app_root, self.session)
        self.api.token = payload["token"]
        self.console.print("[green]%s[/]" % self._t("login_saved"))

    def _start_background_client(self) -> None:
        self.poller = threading.Thread(target=self._poll_server_tasks, daemon=True)
        self.poller.start()

    def _poll_server_tasks(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.api.heartbeat(self.computer.uid, self.computer.name)
                payload = self.api.next_task(self.computer.uid)
                task = payload.get("task")
                if task:
                    self._handle_server_task(task)
            except Exception as exc:
                self.console.print("[red]%s[/] %s" % (self._t("sync_error"), exc))
            self.stop_event.wait(5)

    def _handle_server_task(self, task: dict) -> None:
        prompt = str(task["prompt"])
        task_id = int(task["id"])
        self.console.print("[cyan]%s %s.[/] %s" % (self._t("task_received"), task_id, prompt))
        try:
            result = self.agent.ask(prompt)
            self._save_runtime_state()
            self.api.complete_task(task_id, response=result.message)
            self.console.print("[green]%s %s.[/]" % (self._t("task_completed"), task_id))
        except Exception as exc:
            self.api.complete_task(task_id, error=str(exc))
            self.console.print("[red]%s[/] %s" % (self._t("task_failed"), exc))

    def _render_header(self) -> None:
        summary = (
            "{server_label}: {server}\n{user_label}: {user}\n{computer_label}: {computer}\n"
            "{provider_label}: {provider}\n{model_label}: {model}\n{mode_label}: {mode}\n"
            "{permission_label}: {permission}\n{help_label}: /help"
        ).format(
            server_label=self._t("server"),
            server=self.config.app_base_url,
            user_label=self._t("user"),
            user=self.session.get("username", "-"),
            computer_label=self._t("computer"),
            computer=self.computer.name,
            provider_label=self._t("provider"),
            provider=self.config.provider,
            model_label=self._t("model"),
            model=self.config.model,
            mode_label=self._t("mode"),
            mode=self.agent.state.mode,
            permission_label=self._t("permission"),
            permission=self.permission,
            help_label=self._t("help"),
        )
        panel = Panel(summary, title=self._t("client_title"), border_style="blue")
        self.console.print(Columns([panel, self.pet.render()], equal=False, expand=False) if self.pet.enabled else panel)

    def _ask_local_ai(self, prompt: str) -> None:
        try:
            self.pet.set_state("thinking", self._t("preparing"))
            self._render_pet()
            result = self.agent.ask(prompt)
            self._save_runtime_state()
        except Exception as exc:
            self.pet.set_state("error", self._t("request_failed"))
            self._render_pet()
            self.console.print("[red]Error:[/] %s" % exc)
            return
        self._render_result(result)

    def _render_pet(self) -> None:
        if self.pet.enabled:
            self.console.print(self.pet.render())

    def _render_result(self, result: AssistantResult) -> None:
        self.pet.set_state("waiting" if result.proposed_changes else "success", self._t("ready"))
        self._render_pet()
        self.console.print(Panel(result.message or "(no message)", title="Assistant", border_style="green"))
        for change in result.proposed_changes:
            self.console.print(Panel(change.intent or "Proposed change", title=change.path, border_style="yellow"))
            self.console.print(Syntax(change.diff_text or "(no diff)", "diff", theme="ansi_dark"))
        if result.suggested_run:
            self.console.print(
                "[cyan]Suggested run:[/] %s %s %s"
                % (result.suggested_run.command_type, result.suggested_run.target, " ".join(result.suggested_run.args))
            )

    def _handle_command(self, raw_command: str) -> bool:
        parts = shlex.split(raw_command)
        command = parts[0].lower()
        if command in {"/quit", "/exit", "/logout"}:
            if command == "/logout":
                clear_client_session(self.root)
                clear_client_session(self.app_root)
                self.console.print(self._t("logout_cleared"))
            else:
                self.console.print(self._t("stopped"))
            return True
        if command == "/help":
            self._show_help(parts[1] if len(parts) > 1 else "")
            return False
        if command == "/permission":
            self._handle_permission(parts[1:])
            return False
        if command == "/status":
            self._show_status()
            return False
        if command == "/doctor":
            self._show_doctor()
            return False
        if command == "/init":
            self._init_workspace()
            return False
        if command == "/plan":
            self._plan_task(" ".join(parts[1:]).strip())
            return False
        if command == "/memory":
            self._handle_memory(parts[1:])
            return False
        if command == "/compact":
            self._compact_conversation()
            return False
        if command == "/review":
            self._review_context(" ".join(parts[1:]).strip())
            return False
        if command == "/commands":
            self._list_custom_commands()
            return False
        if command == "/language" and len(parts) == 2:
            requested = parts[1].lower()
            if requested not in LANGUAGES:
                raise ValueError("Unsupported language: %s" % requested)
            self.language = requested
            self.session["language"] = requested
            save_client_session(self.app_root, self.session)
            self.console.print("[green]%s[/]" % self._t("language_set"))
            return False
        if command == "/download":
            self._handle_download_parts(parts[1:])
            return False
        if command == "/pet":
            self._handle_pet(parts[1:])
            return False
        if command == "/provider" and len(parts) == 2:
            self.config.provider = parts[1]  # type: ignore[assignment]
            self.agent.provider = build_provider(self.config.provider)
            self._save_model_config({"provider": self.config.provider})
            self.console.print("[green]%s[/] %s" % (self._t("provider_set"), self.config.provider))
            return False
        if command == "/model" and len(parts) >= 2:
            self.config.model = " ".join(parts[1:])
            self._save_model_config({"model": self.config.model})
            self.console.print("[green]%s[/] %s" % (self._t("model_set"), self.config.model))
            return False
        if command == "/mode" and len(parts) == 2:
            self.agent.set_mode(parts[1])  # type: ignore[arg-type]
            self.console.print("[green]%s[/] %s" % (self._t("mode_set"), self.agent.state.mode))
            return False
        if command == "/open" and len(parts) == 2:
            self._require_permission("files")
            self._open_file(parts[1])
            return False
        if command == "/context" and len(parts) >= 3:
            self._require_permission("files")
            self._handle_context(parts[1], parts[2])
            return False
        if command == "/apply":
            self._require_permission("files")
            self._apply_pending()
            return False
        if command == "/run":
            self._require_permission("files")
            self._run_command(parts[1:])
            return False
        if command == "/reset":
            self.agent.reset()
            self.console.print("[green]%s[/]" % self._t("session_reset"))
            return False
        if command == "/files":
            self._require_permission("files")
            self._list_files()
            return False
        if self._handle_custom_command(command, parts[1:]):
            return False
        self.console.print("[yellow]%s[/]" % self._t("unknown"))
        return False

    def _show_help(self, topic: str = "") -> None:
        topic_key = topic.lower().strip()
        pages = HELP_PAGES.get(self.language, HELP_PAGES["en"])
        if topic_key in pages:
            text = pages[topic_key]
        elif topic_key == "":
            text = pages[""]
        else:
            text = "%s\n\n%s\n%s" % (
                self._t("help_unknown_topic", topic=topic_key),
                self._t("help_topics_line"),
                pages[""],
            )
        self.console.print(Panel(text.rstrip(), title=self._t("help_title"), border_style="cyan"))

    def _handle_permission(self, args: List[str]) -> None:
        if not args:
            self.console.print(
                Panel(
                    "%s %s" % (self._t("permission_current"), self.permission),
                    title=self._t("permission_title"),
                    border_style="cyan",
                )
            )
            return
        requested = args[0].lower()
        if requested not in PERMISSION_LEVELS:
            raise ValueError("Unsupported permission mode: %s" % requested)
        if requested == "elevated" and not Confirm.ask(self._t("permission_confirm"), default=False):
            return
        self.permission = requested
        self._save_permission(requested)
        self._audit("permission", {"mode": self.permission})
        self.console.print("[green]%s[/] %s" % (self._t("permission_set"), self.permission))

    def _save_model_config(self, updates: Dict[str, object]) -> None:
        file_config, _ = load_local_config_files(self.app_root)
        file_config.update(updates)
        file_config["model_connection_configured"] = True
        write_local_config(self.app_root, file_config)

    def _load_saved_permission(self) -> str:
        file_config, _ = load_local_config_files(self.app_root)
        permission = str(file_config.get("permission", "safe"))
        return permission if permission in PERMISSION_LEVELS else "safe"

    def _save_permission(self, permission: str) -> None:
        file_config, _ = load_local_config_files(self.app_root)
        file_config["permission"] = permission
        write_local_config(self.app_root, file_config)

    def _require_permission(self, required: str) -> None:
        order = {"safe": 0, "files": 1, "downloads": 2, "elevated": 3}
        if order[self.permission] < order[required]:
            raise PermissionError(self._t("permission_error", current=self.permission, required=required))

    def _handle_pet(self, args: List[str]) -> None:
        if not args or args[0] == "status":
            self._render_pet()
            return
        if args[0] == "on":
            self.pet.enabled = True
            self.pet.set_state("idle", self._t("pet_enabled"))
            self._render_pet()
            return
        if args[0] == "off":
            self.pet.enabled = False
            self.console.print("[yellow]%s[/]" % self._t("pet_disabled"))
            return
        raise ValueError("Unsupported pet command: %s" % args[0])

    def _handle_download_text(self, text: str) -> None:
        self._require_permission("downloads")
        request = parse_download_request(text)
        self._perform_download(request.query, request.install, request.elevated)

    def _handle_download_parts(self, args: List[str]) -> None:
        self._require_permission("downloads")
        install = "--install" in args
        elevated = "--admin" in args or "--elevated" in args
        query = " ".join(item for item in args if item not in {"--install", "--admin", "--elevated"}).strip()
        self._perform_download(query, install, elevated)

    def _perform_download(self, query: str, install: bool, elevated: bool) -> None:
        if not query:
            raise ValueError(self._t("download_empty"))
        if self.downloader.is_url(query):
            if Confirm.ask(self._t("download_url"), default=False):
                result = self.downloader.download_url(query)
                self._audit("download", {"query": query, "path": str(result.path)})
                self.console.print("[green]%s[/] %s" % (self._t("downloaded"), result.path))
            return
        if install:
            if elevated:
                self._require_permission("elevated")
            if not Confirm.ask(self._t("install_confirm", query=query), default=False):
                return
            if elevated and not Confirm.ask(self._t("admin_confirm", query=query), default=False):
                return
            result = self.downloader.winget_install(query, elevated=elevated)
            self._audit("install", {"query": query, "elevated": elevated})
            self.console.print(Panel(result.message, title="Install", border_style="green"))
            return
        if Confirm.ask(self._t("search_confirm", query=query), default=True):
            result = self.downloader.winget_search(query)
            self.console.print(Panel(result.message, title="winget Search", border_style="cyan"))

    def _open_file(self, raw_path: str) -> None:
        path = self.agent.add_context_file(raw_path)
        content = path.read_text(encoding="utf-8")
        self.console.print(Panel(str(path.relative_to(self.root)), title=self._t("loaded_context"), border_style="cyan"))
        self.console.print(Syntax(content, self.workspace.language_hint(path), theme="ansi_dark", line_numbers=True))

    def _handle_context(self, action: str, raw_path: str) -> None:
        if action == "add":
            path = self.agent.add_context_file(raw_path)
            self.console.print("[green]%s[/] %s" % (self._t("added_context"), path.relative_to(self.root)))
            return
        if action == "remove":
            self.agent.remove_context_file(raw_path)
            self.console.print("[green]%s[/] %s" % (self._t("removed_context"), raw_path))
            return
        raise ValueError("Unsupported context action: %s" % action)

    def _apply_pending(self) -> None:
        pending = self.agent.state.pending_result
        if not pending or not pending.proposed_changes:
            self.console.print("[yellow]%s[/]" % self._t("no_pending"))
            return
        for change in pending.proposed_changes:
            self.console.print(Syntax(change.diff_text, "diff", theme="ansi_dark"))
            if Confirm.ask(self._t("apply_confirm", path=change.path), default=False):
                self.workspace.apply_change(change)
                self.agent.state.applied_changes.append(change)
                self._audit("apply", {"path": change.path})
                self.console.print("[green]Applied[/] %s" % change.path)
        if pending.suggested_run and Confirm.ask(self._t("run_suggested_now"), default=False):
            self._execute_run(pending.suggested_run)

    def _run_command(self, args: List[str]) -> None:
        if args:
            self._execute_run(self._parse_run_args(args))
            return
        pending = self.agent.state.pending_result
        if pending and pending.suggested_run and Confirm.ask(self._t("run_suggested"), default=False):
            self._execute_run(pending.suggested_run)
            return
        self.console.print("[yellow]%s[/]" % self._t("no_run"))

    def _parse_run_args(self, args: List[str]) -> RunRequest:
        command = args[0].lower()
        if command in {"python", "py"}:
            return RunRequest(command_type="python", target=args[1], args=args[2:])
        if command == "pytest":
            target = args[1] if len(args) >= 2 and not args[1].startswith("-") else ""
            remaining = args[2:] if target else args[1:]
            return RunRequest(command_type="pytest", target=target, args=remaining)
        if command == "node":
            return RunRequest(command_type="node", target=args[1], args=args[2:])
        if command in {"npm", "pnpm", "yarn", "bun"}:
            return RunRequest(command_type=command, target=args[1], args=args[2:])  # type: ignore[arg-type]
        return RunRequest(command_type="python", target=args[0], args=args[1:])

    def _execute_run(self, request: RunRequest) -> None:
        result = self.runner.run(request)
        self._audit("run", {"command": result.command, "exit_code": result.exit_code})
        summary = "Exit code: %s\nCommand: %s" % (result.exit_code, " ".join(result.command))
        self.console.print(Panel(summary, title="Run Result", border_style="magenta"))
        if result.stdout:
            self.console.print(Panel(result.stdout, title="stdout", border_style="green"))
        if result.stderr:
            self.console.print(Panel(result.stderr, title="stderr", border_style="red"))

    def _list_files(self) -> None:
        table = Table(title=self._t("workspace_files"))
        table.add_column("Path")
        for path in self.workspace.list_code_files():
            table.add_row(path.relative_to(self.root).as_posix())
        self.console.print(table)

    def _show_status(self) -> None:
        table = Table(title=self._t("status_title"))
        table.add_column("Item")
        table.add_column("Value")
        table.add_row(self._t("install_root"), str(self.app_root))
        table.add_row(self._t("workspace"), str(self.root))
        table.add_row(self._t("server"), self.config.app_base_url)
        table.add_row(self._t("user"), str(self.session.get("username", "")))
        table.add_row(self._t("computer"), self.computer.name)
        table.add_row(self._t("provider"), self.config.provider)
        table.add_row(self._t("model"), self.config.model)
        table.add_row(self._t("mode"), self.agent.state.mode)
        table.add_row(self._t("permission"), self.permission)
        table.add_row(self._t("language"), self.language)
        table.add_row(self._t("context_files"), str(len(self.agent.state.context_files)))
        table.add_row(
            self._t("pending_changes"),
            str(len(self.agent.state.pending_result.proposed_changes) if self.agent.state.pending_result else 0),
        )
        table.add_row(self._t("project_memory"), self._t("yes") if self.memory_path.exists() else self._t("no"))
        self.console.print(table)

    def _show_doctor(self) -> None:
        table = Table(title=self._t("doctor_title"))
        table.add_column("Check")
        table.add_column("Result")
        table.add_row(self._t("workspace"), str(self.root))
        table.add_row("Git install", "yes" if self.updater.is_git_install() else "no")
        table.add_row(self._t("config_file"), self._t("yes") if (self.app_root / "config.yaml").exists() else self._t("no"))
        table.add_row("Server URL", self.config.app_base_url)
        table.add_row(self._t("api_key"), "set" if self.config.api_key or self.config.provider == "ollama" else "missing")
        table.add_row(self._t("ollama"), self.config.ollama_base_url)
        table.add_row(self._t("files_visible"), str(len(self.workspace.list_code_files())))
        table.add_row(self._t("rule_files"), ", ".join(self._existing_rule_files()) or self._t("none"))
        self.console.print(table)

    def _init_workspace(self) -> None:
        self.easyai_dir.mkdir(parents=True, exist_ok=True)
        self.commands_dir.mkdir(parents=True, exist_ok=True)
        agents_path = self.root / "AGENTS.md"
        if not agents_path.exists():
            agents_path.write_text(
                "# Project Instructions\n\n"
                "- Prefer small, maintainable changes.\n"
                "- Explain tradeoffs briefly.\n"
                "- Ask before destructive operations.\n"
                "- Run focused validation after edits when possible.\n",
                encoding="utf-8",
            )
        if not self.memory_path.exists():
            self.memory_path.write_text("# EasyAI Memory\n\n", encoding="utf-8")
        review_command = self.commands_dir / "review.md"
        if not review_command.exists():
            review_command.write_text(
                "Review the loaded context like a senior engineer. Focus on bugs, security, regressions, and missing tests. Args: {{args}}\n",
                encoding="utf-8",
            )
        self._audit("init", {"path": str(self.easyai_dir)})
        self.console.print("[green]%s[/]" % self._t("initialized"))

    def _plan_task(self, task: str) -> None:
        if not task:
            raise ValueError(self._t("plan_empty"))
        prompt = (
            "Create a concise implementation plan for this task. "
            "Do not propose file writes yet. Include risks, validation, and required context. Task: %s" % task
        )
        self._ask_local_ai(prompt)

    def _handle_memory(self, args: List[str]) -> None:
        if not args:
            text = self.memory_path.read_text(encoding="utf-8") if self.memory_path.exists() else "(empty)"
            self.console.print(Panel(text.strip() or "(empty)", title=self._t("project_memory"), border_style="cyan"))
            return
        action = args[0].lower()
        if action == "add":
            self._append_memory(" ".join(args[1:]).strip())
            return
        if action == "clear":
            if Confirm.ask(self._t("clear_memory"), default=False):
                self.easyai_dir.mkdir(parents=True, exist_ok=True)
                self.memory_path.write_text("# EasyAI Memory\n\n", encoding="utf-8")
                self._audit("memory.clear", {})
            return
        raise ValueError("Unsupported memory command.")

    def _quick_memory(self, text: str) -> None:
        if not text:
            self.console.print("[yellow]%s[/]" % self._t("memory_empty"))
            return
        self._append_memory(text)

    def _append_memory(self, text: str) -> None:
        if not text:
            raise ValueError(self._t("memory_empty"))
        self.easyai_dir.mkdir(parents=True, exist_ok=True)
        if not self.memory_path.exists():
            self.memory_path.write_text("# EasyAI Memory\n\n", encoding="utf-8")
        timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        with self.memory_path.open("a", encoding="utf-8") as handle:
            handle.write("- %s %s\n" % (timestamp, text))
        self._audit("memory.add", {"text": text})
        self.console.print("[green]%s[/]" % self._t("memory_saved"))

    def _compact_conversation(self) -> None:
        messages = self.agent.state.messages
        if len(messages) <= 6:
            self.console.print("[yellow]%s[/]" % self._t("not_enough_compact"))
            return
        old_messages = messages[:-4]
        summary_lines = []
        for message in old_messages[-12:]:
            content = message.content.replace("\n", " ").strip()
            summary_lines.append("%s: %s" % (message.role, content[:220]))
        previous = str(self.agent.state.metadata.get("conversation_summary", "")).strip()
        combined = (previous + "\n" if previous else "") + "\n".join(summary_lines)
        self.agent.state.metadata["conversation_summary"] = combined[-5000:]
        self.agent.state.messages = messages[-4:]
        self._audit("compact", {"remaining_messages": len(self.agent.state.messages)})
        self.console.print("[green]%s[/]" % self._t("conversation_compacted"))

    def _review_context(self, focus: str) -> None:
        self._require_permission("files")
        if not self.agent.state.context_files:
            raise ValueError(self._t("load_context_first"))
        prompt = (
            "Review the loaded context. Prioritize concrete bugs, security risks, regressions, and missing tests. "
            "Give file/line references when possible. Focus: %s" % (focus or "general")
        )
        self._ask_local_ai(prompt)

    def _list_custom_commands(self) -> None:
        table = Table(title=self._t("custom_commands"))
        table.add_column("Command")
        table.add_column(self._t("file"))
        for path in sorted(self.commands_dir.glob("*.md")) if self.commands_dir.exists() else []:
            table.add_row("/" + path.stem, path.relative_to(self.root).as_posix())
        if not table.rows:
            table.add_row("(none)", ".easyai/commands/*.md")
        self.console.print(table)

    def _handle_custom_command(self, command: str, args: List[str]) -> bool:
        name = command.lstrip("/")
        if not name or name in {"help", "quit", "exit"}:
            return False
        path = self.commands_dir / ("%s.md" % name)
        if not path.exists():
            return False
        prompt = path.read_text(encoding="utf-8")
        prompt = prompt.replace("{{args}}", " ".join(args))
        self._ask_local_ai(prompt)
        return True

    def _existing_rule_files(self) -> List[str]:
        return [name for name in ("AGENTS.md", "CLAUDE.md", "EASYAI.md", ".easyai/memory.md") if (self.root / name).exists()]

    def _audit(self, action: str, payload: dict) -> None:
        self.easyai_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "action": action,
            "payload": payload,
        }
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _load_runtime_state(self) -> SessionState:
        if not self.runtime_state_path.exists():
            return SessionState(mode=self.config.default_mode)
        try:
            payload = json.loads(self.runtime_state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return SessionState(mode=self.config.default_mode)
        if not isinstance(payload, dict):
            return SessionState(mode=self.config.default_mode)

        mode = str(payload.get("mode", self.config.default_mode))
        if mode not in {"chat", "code", "edit"}:
            mode = self.config.default_mode

        context_files: List[Path] = []
        for raw_path in payload.get("context_files", []):
            if not isinstance(raw_path, str):
                continue
            path = Path(raw_path)
            if not path.is_absolute():
                path = self.root / raw_path
            try:
                path = path.resolve()
            except OSError:
                pass
            if path.exists():
                context_files.append(path)

        messages: List[Message] = []
        for item in payload.get("messages", []):
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role in {"system", "user", "assistant"} and isinstance(content, str):
                messages.append(Message(role=role, content=content))

        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        return SessionState(
            mode=mode,
            context_files=context_files,
            messages=messages,
            pending_result=self._deserialize_result(payload.get("pending_result")),
            applied_changes=self._deserialize_changes(payload.get("applied_changes", [])),
            metadata={str(key): str(value) for key, value in metadata.items()},
        )

    def _save_runtime_state(self) -> None:
        self.easyai_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": self.agent.state.mode,
            "context_files": [self._serialize_path(path) for path in self.agent.state.context_files],
            "messages": [{"role": message.role, "content": message.content} for message in self.agent.state.messages],
            "pending_result": self._serialize_result(self.agent.state.pending_result),
            "applied_changes": [self._serialize_change(change) for change in self.agent.state.applied_changes],
            "metadata": dict(self.agent.state.metadata),
        }
        temp_path = self.runtime_state_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.runtime_state_path)

    def _serialize_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return str(path.resolve())

    def _serialize_result(self, result: Optional[AssistantResult]) -> Optional[dict]:
        if result is None:
            return None
        return {
            "message": result.message,
            "proposed_changes": [self._serialize_change(change) for change in result.proposed_changes],
            "suggested_run": self._serialize_run_request(result.suggested_run),
            "raw_response": result.raw_response,
        }

    def _deserialize_result(self, payload: object) -> Optional[AssistantResult]:
        if not isinstance(payload, dict):
            return None
        message = payload.get("message")
        if not isinstance(message, str):
            return None
        raw_response = payload.get("raw_response")
        return AssistantResult(
            message=message,
            proposed_changes=self._deserialize_changes(payload.get("proposed_changes", [])),
            suggested_run=self._deserialize_run_request(payload.get("suggested_run")),
            raw_response=raw_response if isinstance(raw_response, str) else None,
        )

    def _serialize_change(self, change: WorkspaceChange) -> dict:
        return {
            "path": change.path,
            "original_text": change.original_text,
            "updated_text": change.updated_text,
            "diff_text": change.diff_text,
            "intent": change.intent,
        }

    def _deserialize_changes(self, payload: object) -> List[WorkspaceChange]:
        if not isinstance(payload, list):
            return []
        changes: List[WorkspaceChange] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            original_text = item.get("original_text")
            updated_text = item.get("updated_text")
            diff_text = item.get("diff_text")
            intent = item.get("intent", "")
            if not all(isinstance(value, str) for value in (path, original_text, updated_text, diff_text)):
                continue
            changes.append(
                WorkspaceChange(
                    path=path,
                    original_text=original_text,
                    updated_text=updated_text,
                    diff_text=diff_text,
                    intent=intent if isinstance(intent, str) else "",
                )
            )
        return changes

    def _serialize_run_request(self, request: Optional[RunRequest]) -> Optional[dict]:
        if request is None:
            return None
        return {
            "command_type": request.command_type,
            "target": request.target,
            "args": list(request.args),
        }

    def _deserialize_run_request(self, payload: object) -> Optional[RunRequest]:
        if not isinstance(payload, dict):
            return None
        command_type = payload.get("command_type")
        target = payload.get("target")
        args = payload.get("args", [])
        if not isinstance(command_type, str) or not isinstance(target, str) or not isinstance(args, list):
            return None
        if not all(isinstance(arg, str) for arg in args):
            return None
        return RunRequest(command_type=command_type, target=target, args=args)  # type: ignore[arg-type]

    def _has_runtime_state_data(self, state: SessionState) -> bool:
        return bool(
            state.context_files
            or state.messages
            or state.pending_result
            or state.applied_changes
            or state.metadata
        )


def run_self_test(workspace_root: Path) -> int:
    client = EasyAIClient(workspace_root)
    checks = [
        ("workspace", client.root.exists(), str(client.root)),
        ("install_root", client.app_root.exists(), str(client.app_root)),
        ("config", client.config.app_base_url == "https://xingkongtech.top", client.config.app_base_url),
        ("updater_root", client.updater.root == client.app_root, str(client.updater.root)),
        ("server_api", bool(client.api.base_url), client.api.base_url),
    ]
    failed = False
    for name, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        print("%s %s: %s" % (status, name, detail))
        failed = failed or not ok
    return 1 if failed else 0


def main() -> None:
    if "--self-test" in sys.argv:
        raise SystemExit(run_self_test(Path.cwd()))
    EasyAIClient(Path.cwd()).run()


if __name__ == "__main__":
    main()
