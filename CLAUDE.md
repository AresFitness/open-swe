# AMP SWE Agent

Fork of [langchain-ai/open-swe](https://github.com/langchain-ai/open-swe) customized for AresFitness multi-repo development.

## What This Is

An autonomous coding agent built on Open SWE (LangGraph + Deep Agents) that can clone repos, modify code, run tests, and create PRs. Currently targets the **RedefinedFitness** backend repo; Sprint 2 adds iOS (amp-ios) support.

## Architecture

```
[Slack / Linear / GitHub webhooks]
        |
        v
[LangGraph Server on Mac] (Python, port 2024)
  ├── FastAPI webhooks (agent/webapp.py)
  ├── Agent orchestration (agent/server.py)
  └── Local sandbox (subprocess on macOS)
        ├── RedefinedFitness/   (backend repo, cloned per task)
        └── amp-ios/            (iOS repo, Sprint 2)
```

Everything runs on a single Mac. The `local` sandbox provider executes commands via subprocess — no Docker/SSH needed. The agent uses Claude Opus 4.6 as the LLM.

## Key Customizations Over Upstream Open SWE

### 1. macOS local sandbox (not Linux containers)
- `SANDBOX_TYPE=local` with `LOCAL_SANDBOX_ROOT_DIR` pointing to a writable directory
- Prompt updated from "remote Linux sandbox" to "local macOS sandbox"
- Enables future Xcode/iOS simulator access on the same machine

### 2. CLAUDE.md convention injection
- **File**: `agent/utils/claude_md.py` — reads `CLAUDE.md` from cloned repos
- **File**: `agent/prompt.py` — `construct_system_prompt()` accepts `repo_conventions` dict, injects under `<conventions_RepoName>` tags
- **File**: `agent/server.py` — calls `read_claude_md_in_sandbox()` and passes to prompt builder
- The agent follows each repo's coding standards (TypeScript rules, logging patterns, DynamoDB utils, etc.)

### 3. Backend-specific tools
- **File**: `agent/tools/backend_tools.py`
  - `backend_test(test_path, package)` — run specific tests via pnpm/jest
  - `backend_typecheck(package)` — TypeScript type checking
  - `backend_lint(files, package)` — ESLint
  - `backend_codegen()` — GraphQL type generation
  - `backend_local(action, component)` — manage `pnpm local` orchestrator (up/down/status/start/stop/restart/logs for all backend services)
- Registered in `agent/tools/__init__.py` and `agent/server.py`

### 4. AresFitness defaults
- **File**: `agent/webapp.py` — `DEFAULT_REPO_OWNER=AresFitness`, `DEFAULT_REPO_NAME=RedefinedFitness`
- `ALLOWED_GITHUB_ORGS=AresFitness`

### 5. Bot-token-only auth mode
- Set `LANGSMITH_API_KEY_PROD` to any value to enable bot-token-only mode
- Uses the GitHub App installation token for all git operations (no per-user OAuth needed)
- Simpler setup for local development

## Project Structure

```
amp-swe-agent/
├── agent/
│   ├── server.py              # Agent factory — sandbox lifecycle, repo clone, tool/prompt setup
│   ├── prompt.py              # System prompt (macOS sandbox, CLAUDE.md injection)
│   ├── webapp.py              # FastAPI webhooks (Slack, Linear, GitHub)
│   ├── tools/
│   │   ├── __init__.py        # Exports all tools
│   │   ├── backend_tools.py   # AMP-specific: test, typecheck, lint, codegen, local
│   │   ├── commit_and_open_pr.py
│   │   ├── fetch_url.py
│   │   ├── github_comment.py
│   │   ├── http_request.py
│   │   ├── linear_comment.py
│   │   └── slack_thread_reply.py
│   ├── utils/
│   │   ├── claude_md.py       # AMP-specific: reads CLAUDE.md from repos
│   │   ├── sandbox.py         # Sandbox factory (local, langsmith, daytona, etc.)
│   │   ├── sandbox_paths.py   # Resolves writable paths in sandbox
│   │   ├── agents_md.py       # Reads AGENTS.md from repos
│   │   ├── auth.py            # GitHub token resolution
│   │   ├── github.py          # Git operations, PR creation
│   │   └── ...
│   ├── integrations/
│   │   ├── local.py           # Local sandbox (subprocess, used on macOS)
│   │   ├── langsmith.py       # LangSmith cloud sandbox
│   │   └── ...
│   └── middleware/             # before_model, after_agent hooks
├── langgraph.json             # LangGraph config (graph + http app entry points)
├── pyproject.toml             # Python deps (deepagents, langgraph, langchain, etc.)
├── .env                       # Secrets (gitignored)
├── .env.example               # Template
└── tests/                     # 85 tests
```

## Setup

### Prerequisites
- Python 3.12 (3.14 not supported due to pyo3/jsonschema-rs)
- [uv](https://docs.astral.sh/uv/) package manager
- A GitHub App installed on AresFitness org

### Install
```bash
uv sync --python 3.12 --all-extras
```

### Configure
```bash
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY,
#          GITHUB_APP_INSTALLATION_ID, GITHUB_WEBHOOK_SECRET, TOKEN_ENCRYPTION_KEY
# Set LANGSMITH_API_KEY_PROD to any value for bot-token-only mode
```

### Run
```bash
# Create sandbox directory
mkdir -p /tmp/amp-swe-sandbox

# Start the server
uv run langgraph dev --no-browser
```

### Test via API
```bash
# Create a thread
THREAD_ID=$(curl -s -X POST http://localhost:2024/threads \
  -H "Content-Type: application/json" -d '{"metadata": {}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['thread_id'])")

# Run a task
curl -s -X POST "http://localhost:2024/threads/${THREAD_ID}/runs" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "agent",
    "input": {"messages": [{"role": "user", "content": "Your task here"}]},
    "config": {"configurable": {"repo": {"owner": "AresFitness", "name": "RedefinedFitness"}, "source": "github"}}
  }'
```

### Webhook triggers
- **Slack**: `@amp-agent <task>` — requires SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET
- **Linear**: Comment `@openswe` on an issue — requires LINEAR_API_KEY, LINEAR_WEBHOOK_SECRET
- **GitHub**: `@openswe` in issues/PR comments — requires GITHUB_WEBHOOK_SECRET
- All webhooks need ngrok or Cloudflare Tunnel to expose port 2024

## How to Add a New Tool

1. Create a function in `agent/tools/` with type hints and a docstring (the docstring is the LLM's tool description)
2. Export it in `agent/tools/__init__.py`
3. Import and add it to the `tools=[...]` list in `agent/server.py` `get_agent()`

## How to Add a New Repo

1. Extend `server.py` to clone multiple repos (modify `_clone_or_pull_repo_in_sandbox`)
2. Read each repo's `CLAUDE.md` and pass all to `construct_system_prompt(repo_conventions=...)`
3. Add repo-specific tools (e.g., iOS tools in `agent/tools/ios_tools.py`)

## Roadmap

- **Sprint 2**: Multi-repo support (RedefinedFitness + amp-ios), iOS tools (xcodebuild, simulator, Peekaboo)
- **Sprint 3**: Cross-repo E2E testing (backend + iOS simulator), linked PR creation
- **Sprint 4**: Webhook triggers, launchd service, production deployment
- **Sprint 5**: Multi-Mac scaling via SSH sandbox provider
