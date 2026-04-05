# Per-Repo Sub-Agent Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-agent-with-all-skills model with an orchestrator + per-repo specialist sub-agents, where each sub-agent has its repo's full skills/conventions/agent-knowledge pre-loaded.

**Architecture:** The orchestrator stays lean (no repo skills) and delegates repo-specific work via Deep Agents' `SubAgentMiddleware` `task` tool. Each sub-agent is auto-configured at startup from the repos in the sandbox. Skills from `.claude/skills/`, `.agents/skills/`, and `.claude/agents/` are loaded into each sub-agent's system prompt.

**Tech Stack:** Python 3.12, Deep Agents (`SubAgentMiddleware`, `create_deep_agent`), LangGraph

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `agent/utils/skills.py` | Modify | Add `.agents/skills/` scanning, `.claude/agents/*.md` loading, deduplication |
| `agent/prompt.py` | Modify | Remove sub-agent prohibition, add orchestrator instructions, add `construct_subagent_prompt()` and `build_subagent_description()` |
| `agent/server.py` | Modify | Build sub-agent configs, add `SubAgentMiddleware`, remove `load_repo_tools()` |
| `agent/tools/repo_tool_loader.py` | Delete | Replaced by skills system |
| `tests/test_skills.py` | Modify | Add tests for new scanning paths and dedup |
| `tests/test_subagent_config.py` | Create | Test sub-agent config generation |

---

### Task 1: Extend skills.py — scan .agents/skills/ and .claude/agents/

**Files:**
- Modify: `agent/utils/skills.py`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Write failing test for `.agents/skills/` discovery**

```python
# Add to tests/test_skills.py

@pytest.mark.asyncio
async def test_discovers_skills_from_agents_dir() -> None:
    """Skills in .agents/skills/ should be discovered."""
    fs = {
        "/repo/.agents/skills/swift-style/SKILL.md": "# Swift Style\nUse explicit self.",
        "/repo/.agents/skills/swift-style/references/rules.md": "Rule details",
    }
    backend = _FakeSandboxBackend(fs=fs)

    result = await read_skills_in_sandbox(backend, "/repo")

    assert "swift-style" in result
    assert result["swift-style"]["content"] == "# Swift Style\nUse explicit self."
    assert result["swift-style"]["references"] == {"rules": "Rule details"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mikechatsky/projects/amp/amp-swe-agent && uv run pytest tests/test_skills.py::test_discovers_skills_from_agents_dir -v --no-header`
Expected: FAIL — current code only scans `.claude/skills/`

- [ ] **Step 3: Write failing test for deduplication (.claude/ wins)**

```python
@pytest.mark.asyncio
async def test_claude_skills_win_over_agents_skills() -> None:
    """When same skill exists in both dirs, .claude/skills/ takes precedence."""
    fs = {
        "/repo/.claude/skills/my-skill/SKILL.md": "Claude version",
        "/repo/.agents/skills/my-skill/SKILL.md": "Agents version",
    }
    backend = _FakeSandboxBackend(fs=fs)

    result = await read_skills_in_sandbox(backend, "/repo")

    assert result["my-skill"]["content"] == "Claude version"
```

- [ ] **Step 4: Write failing test for `.claude/agents/*.md` loading**

```python
from agent.utils.skills import read_agent_knowledge_in_sandbox

@pytest.mark.asyncio
async def test_reads_agent_knowledge_files() -> None:
    """Should discover and read .claude/agents/*.md files."""
    fs = {
        "/repo/.claude/agents/tool_xcode-build.md": "# Xcode Build\nHow to build.",
        "/repo/.claude/agents/analytics-agent.md": "# Analytics\nTrack events.",
    }
    backend = _FakeSandboxBackend(fs=fs)

    result = await read_agent_knowledge_in_sandbox(backend, "/repo")

    assert len(result) == 2
    assert result["tool_xcode-build"] == "# Xcode Build\nHow to build."
    assert result["analytics-agent"] == "# Analytics\nTrack events."


@pytest.mark.asyncio
async def test_agent_knowledge_returns_empty_for_none() -> None:
    backend = _FakeSandboxBackend()
    result = await read_agent_knowledge_in_sandbox(backend, None)
    assert result == {}
```

- [ ] **Step 5: Run all new tests to verify they fail**

Run: `cd /Users/mikechatsky/projects/amp/amp-swe-agent && uv run pytest tests/test_skills.py -v --no-header -k "agents"`
Expected: All new tests FAIL

- [ ] **Step 6: Implement `.agents/skills/` scanning and deduplication in skills.py**

Modify `agent/utils/skills.py` — change `read_skills_in_sandbox` to scan both directories:

```python
async def read_skills_in_sandbox(
    sandbox_backend: SandboxBackendProtocol,
    repo_dir: str | None,
) -> dict[str, dict]:
    """Discover and read skills from .claude/skills/ and .agents/skills/.

    Scans both directories. When the same skill name exists in both,
    .claude/skills/ takes precedence.
    """
    if not repo_dir:
        return {}

    # Scan .claude/skills/ first (higher priority)
    claude_skills = await _scan_skills_dir(sandbox_backend, repo_dir, ".claude/skills")
    # Scan .agents/skills/ second
    agents_skills = await _scan_skills_dir(sandbox_backend, repo_dir, ".agents/skills")

    # Merge: .claude/ wins on name collision
    merged = {**agents_skills, **claude_skills}
    return merged
```

Extract the current scanning logic into `_scan_skills_dir(sandbox_backend, repo_dir, subdir)` — a private async function that takes the subdirectory path (`".claude/skills"` or `".agents/skills"`) and returns `dict[str, dict]`. The body is the existing logic from `read_skills_in_sandbox` with the hardcoded `.claude/skills` replaced by the `subdir` parameter.

- [ ] **Step 7: Implement `read_agent_knowledge_in_sandbox`**

Add to `agent/utils/skills.py`:

```python
async def read_agent_knowledge_in_sandbox(
    sandbox_backend: SandboxBackendProtocol,
    repo_dir: str | None,
) -> dict[str, str]:
    """Read .claude/agents/*.md files from a repo.

    Returns a dict mapping filename (without .md) to content.
    """
    if not repo_dir:
        return {}

    loop = asyncio.get_event_loop()
    agents_dir = shlex.quote(f"{repo_dir}/.claude/agents")
    find_cmd = f"find {agents_dir} -maxdepth 1 -type f -name '*.md' 2>/dev/null"
    result = await loop.run_in_executor(
        None, sandbox_backend.execute, find_cmd,
    )

    output = (result.output or "").strip()
    if not output:
        return {}

    knowledge: dict[str, str] = {}
    for file_path in output.splitlines():
        file_path = file_path.strip()
        if not file_path:
            continue
        safe_path = shlex.quote(file_path)
        read_result = await loop.run_in_executor(
            None, sandbox_backend.execute,
            f"test -f {safe_path} && cat {safe_path}",
        )
        if read_result.exit_code != 0:
            continue
        content = (read_result.output or "").strip()
        if content:
            filename = file_path.rsplit("/", 1)[-1]
            name = filename.removesuffix(".md")
            knowledge[name] = content
            logger.info("Loaded agent knowledge '%s' from %s", name, repo_dir)

    return knowledge
```

- [ ] **Step 8: Run all tests to verify they pass**

Run: `cd /Users/mikechatsky/projects/amp/amp-swe-agent && uv run pytest tests/test_skills.py -v --no-header`
Expected: ALL tests PASS (including existing ones)

- [ ] **Step 9: Commit**

```bash
git add agent/utils/skills.py tests/test_skills.py
git commit -m "feat: extend skills.py to scan .agents/skills/ and .claude/agents/"
```

---

### Task 2: Add orchestrator and sub-agent prompt functions to prompt.py

**Files:**
- Modify: `agent/prompt.py`

- [ ] **Step 1: Remove sub-agent prohibition from TOOL_MAPPING_PREAMBLE**

In `agent/prompt.py`, change line 393:

```python
# OLD:
- Agent → you do not have subagents; perform the work sequentially yourself

# NEW:
- Agent/Task → use the task tool to delegate work to a repo-specialist sub-agent
```

- [ ] **Step 2: Add `construct_subagent_prompt` function**

Add at the bottom of `agent/prompt.py`:

```python
SUBAGENT_BASE_PROMPT = """You are a specialist coding agent for the **{repo_name}** repository.

You have deep expertise in this repo's codebase, conventions, and patterns.
Your full knowledge (skills, conventions, agent guides) is loaded below.

### Rules
- Work only within {repo_name}/ — do not modify files in other repos.
- Follow the coding conventions strictly.
- When done, summarize what you changed and any issues encountered.
- You must ALWAYS call a tool in EVERY SINGLE TURN.

{working_env}
{file_management}
{coding_standards}
{core_behavior}
{dependency}

{conventions_section}
{skills_section}
{agent_knowledge_section}
"""


def construct_subagent_prompt(
    repo_name: str,
    working_dir: str,
    conventions: str,
    agents_md: str,
    skills: dict[str, dict],
    agent_knowledge: dict[str, str],
) -> str:
    """Build a system prompt for a per-repo specialist sub-agent."""
    conventions_section = ""
    if conventions:
        conventions_section = (
            f"### Coding conventions for {repo_name}\n"
            f"<conventions_{repo_name}>\n{conventions}\n</conventions_{repo_name}>\n"
        )
    if agents_md:
        conventions_section += (
            f"\n### AGENTS.md for {repo_name}\n"
            f"<agents_md_{repo_name}>\n{agents_md}\n</agents_md_{repo_name}>\n"
        )

    skills_section = ""
    if skills:
        skills_section = TOOL_MAPPING_PREAMBLE
        skills_section += f"\n<skills_{repo_name}>\n"
        for skill_name, skill_data in skills.items():
            skills_section += f"## Skill: {skill_name}\n"
            skills_section += f"{skill_data['content']}\n\n"
            for ref_name, ref_content in skill_data.get("references", {}).items():
                skills_section += f"### Reference: {ref_name}\n"
                skills_section += f"{ref_content}\n\n"
        skills_section += f"</skills_{repo_name}>\n"

    agent_knowledge_section = ""
    if agent_knowledge:
        agent_knowledge_section = f"\n<agent_knowledge_{repo_name}>\n"
        for name, content in agent_knowledge.items():
            agent_knowledge_section += f"## {name}\n{content}\n\n"
        agent_knowledge_section += f"</agent_knowledge_{repo_name}>\n"

    return SUBAGENT_BASE_PROMPT.format(
        repo_name=repo_name,
        working_env=WORKING_ENV_SECTION.format(working_dir=working_dir),
        file_management=FILE_MANAGEMENT_SECTION.format(working_dir=working_dir),
        coding_standards=CODING_STANDARDS_SECTION,
        core_behavior=CORE_BEHAVIOR_SECTION,
        dependency=DEPENDENCY_SECTION,
        conventions_section=conventions_section,
        skills_section=skills_section,
        agent_knowledge_section=agent_knowledge_section,
    )
```

- [ ] **Step 3: Add `build_subagent_description` function**

Add to `agent/prompt.py`:

```python
def build_subagent_description(
    repo_name: str,
    conventions: str,
    skills: dict[str, dict],
    agent_knowledge: dict[str, str],
) -> str:
    """Build a compact description of a sub-agent for the orchestrator.

    The orchestrator sees this to decide when to delegate.
    """
    # Extract first meaningful line from CLAUDE.md as repo summary
    repo_summary = ""
    for line in conventions.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            repo_summary = line[:120]
            break

    skill_names = sorted(skills.keys())
    knowledge_names = sorted(agent_knowledge.keys())

    parts = [f"Specialist for {repo_name}. {repo_summary}"]

    if skill_names:
        shown = skill_names[:8]
        remaining = len(skill_names) - len(shown)
        parts.append(f"Skills: {', '.join(shown)}" + (f", and {remaining} more" if remaining else ""))

    if knowledge_names:
        shown = knowledge_names[:5]
        remaining = len(knowledge_names) - len(shown)
        parts.append(f"Knows: {', '.join(shown)}" + (f", and {remaining} more" if remaining else ""))

    return " ".join(parts)
```

- [ ] **Step 4: Add orchestrator instructions to the main system prompt**

Add a new section constant in `agent/prompt.py`:

```python
ORCHESTRATOR_SECTION = """---

### Sub-Agent Delegation

You have specialist sub-agents for each repository in your workspace.
Delegate repo-specific coding work to them using the `task` tool.

**When to delegate:** Any task that requires reading, writing, or modifying code in a specific repo.
**When NOT to delegate:** Cross-repo coordination, PR creation, communication (Slack/Linear/GitHub), dashboard updates.

**How to delegate:**
- `task(description="<what to do>", subagent_type="<repo-name>")`
- The sub-agent has full knowledge of that repo's conventions, skills, and patterns.
- It returns a result summary when done.

**Cross-repo tasks:**
1. Delegate to the backend repo sub-agent first (schema changes, API, etc.)
2. Use the result to inform the next delegation
3. Delegate to the iOS/frontend sub-agent second
4. Coordinate the results and create PRs

**Single-repo tasks:** Delegate to the appropriate sub-agent and use its result.
"""
```

Add `ORCHESTRATOR_SECTION` to the `SYSTEM_PROMPT` concatenation, right after `MULTI_REPO_SECTION`:

```python
SYSTEM_PROMPT = (
    WORKING_ENV_SECTION
    + FILE_MANAGEMENT_SECTION
    + TASK_OVERVIEW_SECTION
    + TASK_EXECUTION_SECTION
    + MULTI_REPO_SECTION
    + ORCHESTRATOR_SECTION  # NEW
    + TOOL_USAGE_SECTION
    # ... rest unchanged
)
```

- [ ] **Step 5: Commit**

```bash
git add agent/prompt.py
git commit -m "feat: add orchestrator and sub-agent prompt construction"
```

---

### Task 3: Wire sub-agents in server.py and remove repo_tool_loader

**Files:**
- Modify: `agent/server.py`
- Delete: `agent/tools/repo_tool_loader.py`
- Test: `tests/test_subagent_config.py`

- [ ] **Step 1: Write test for `build_subagent_configs`**

Create `tests/test_subagent_config.py`:

```python
"""Tests for sub-agent configuration generation."""

from __future__ import annotations

import pytest

from agent.server import build_subagent_configs


class _FakeSkillsResult:
    """Mimics the return from read_skills_in_sandbox."""
    pass


def test_builds_config_per_repo() -> None:
    """Each repo should produce one sub-agent config."""
    repo_data = {
        "amp-ios": {
            "conventions": "# iOS conventions",
            "agents_md": "",
            "skills": {"swift-style": {"content": "Style rules", "references": {}}},
            "agent_knowledge": {"tool_xcode-build": "Build guide"},
        },
        "RedefinedFitness": {
            "conventions": "# RF conventions",
            "agents_md": "Agent rules",
            "skills": {"db-schema": {"content": "Schema guide", "references": {}}},
            "agent_knowledge": {},
        },
    }

    configs = build_subagent_configs(repo_data, work_dir="/sandbox")

    assert len(configs) == 2
    names = {c["name"] for c in configs}
    assert names == {"amp-ios", "RedefinedFitness"}

    # Each config has required keys
    for config in configs:
        assert "name" in config
        assert "description" in config
        assert "system_prompt" in config
        assert config["name"] in config["description"]


def test_empty_repo_data_returns_empty() -> None:
    configs = build_subagent_configs({}, work_dir="/sandbox")
    assert configs == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mikechatsky/projects/amp/amp-swe-agent && uv run pytest tests/test_subagent_config.py -v --no-header`
Expected: FAIL — `build_subagent_configs` doesn't exist yet

- [ ] **Step 3: Add `build_subagent_configs` function to server.py**

Add near the top of `agent/server.py` (after imports):

```python
from .prompt import build_subagent_description, construct_subagent_prompt


def build_subagent_configs(
    repo_data: dict[str, dict],
    work_dir: str,
) -> list[dict]:
    """Build SubAgent configs from collected repo data.

    Args:
        repo_data: Dict mapping repo_name to
            {"conventions", "agents_md", "skills", "agent_knowledge"}
        work_dir: Sandbox working directory

    Returns:
        List of SubAgent config dicts for SubAgentMiddleware.
    """
    subagents = []
    for repo_name, data in sorted(repo_data.items()):
        system_prompt = construct_subagent_prompt(
            repo_name=repo_name,
            working_dir=work_dir,
            conventions=data.get("conventions", ""),
            agents_md=data.get("agents_md", ""),
            skills=data.get("skills", {}),
            agent_knowledge=data.get("agent_knowledge", {}),
        )
        description = build_subagent_description(
            repo_name=repo_name,
            conventions=data.get("conventions", ""),
            skills=data.get("skills", {}),
            agent_knowledge=data.get("agent_knowledge", {}),
        )
        subagents.append({
            "name": repo_name,
            "description": description,
            "system_prompt": system_prompt,
        })
    return subagents
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/mikechatsky/projects/amp/amp-swe-agent && uv run pytest tests/test_subagent_config.py -v --no-header`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/server.py tests/test_subagent_config.py
git commit -m "feat: add build_subagent_configs function"
```

- [ ] **Step 6: Wire SubAgentMiddleware into `get_agent()`**

Modify `agent/server.py` `get_agent()` function. Replace the current single-agent setup with orchestrator + sub-agents:

**Import changes** — add at top of file:

```python
from .utils.skills import read_agent_knowledge_in_sandbox, read_skills_in_sandbox
```

Remove this import:

```python
# DELETE this line:
from .tools.repo_tool_loader import load_repo_tools
```

**In `get_agent()`**, after the existing skills/conventions reading block (lines 454-478), add agent knowledge reading and build sub-agent configs:

```python
    # Read agent knowledge (.claude/agents/*.md) from all repos
    repo_agent_knowledge: dict[str, dict[str, str]] = {}
    primary_knowledge = await read_agent_knowledge_in_sandbox(sandbox_backend, repo_dir)
    if primary_knowledge and repo_name:
        repo_agent_knowledge[repo_name] = primary_knowledge
    for extra_repo in additional_repos:
        extra_name = extra_repo.get("name")
        if extra_name and extra_name != repo_name:
            extra_dir = await aresolve_repo_dir(sandbox_backend, extra_name)
            extra_knowledge = await read_agent_knowledge_in_sandbox(sandbox_backend, extra_dir)
            if extra_knowledge:
                repo_agent_knowledge[extra_name] = extra_knowledge

    # Read AGENTS.md from additional repos
    repo_agents_md: dict[str, str] = {}
    if agents_md and repo_name:
        repo_agents_md[repo_name] = agents_md
    for extra_repo in additional_repos:
        extra_name = extra_repo.get("name")
        if extra_name and extra_name != repo_name:
            extra_dir = await aresolve_repo_dir(sandbox_backend, extra_name)
            extra_agents_md = await read_agents_md_in_sandbox(sandbox_backend, extra_dir)
            if extra_agents_md:
                repo_agents_md[extra_name] = extra_agents_md

    # Build per-repo data for sub-agent configuration
    all_repo_names = set()
    if repo_name:
        all_repo_names.add(repo_name)
    for extra_repo in additional_repos:
        extra_name = extra_repo.get("name")
        if extra_name:
            all_repo_names.add(extra_name)

    repo_data: dict[str, dict] = {}
    for rname in sorted(all_repo_names):
        repo_data[rname] = {
            "conventions": repo_conventions.get(rname, ""),
            "agents_md": repo_agents_md.get(rname, ""),
            "skills": repo_skills.get(rname, {}),
            "agent_knowledge": repo_agent_knowledge.get(rname, {}),
        }

    subagent_configs = build_subagent_configs(repo_data, work_dir)
```

**Replace the `create_deep_agent()` call** — remove `repo_skills` from `construct_system_prompt` (orchestrator doesn't get skills), remove `*load_repo_tools(work_dir)` from tools, and pass `subagents`:

```python
    return create_deep_agent(
        model=make_model(
            os.environ.get("LLM_MODEL_ID", DEFAULT_LLM_MODEL_ID),
            temperature=0,
            max_tokens=20_000,
        ),
        system_prompt=construct_system_prompt(
            work_dir,
            linear_project_id=linear_project_id,
            linear_issue_number=linear_issue_number,
            agents_md=agents_md,
            repo_conventions=None,  # Conventions moved to sub-agents
            repo_skills=None,  # Skills moved to sub-agents
            superpowers_prompt=superpowers_prompt,
        ),
        tools=[
            # Cross-repo tools (orchestrator keeps these)
            http_request,
            fetch_url,
            web_search,
            commit_and_open_pr,
            linear_comment,
            linear_create_issue,
            linear_delete_issue,
            linear_get_issue,
            linear_get_issue_comments,
            linear_list_teams,
            linear_update_issue,
            slack_thread_reply,
            github_comment,
            list_pr_reviews,
            get_pr_review,
            create_pr_review,
            update_pr_review,
            dismiss_pr_review,
            submit_pr_review,
            list_pr_review_comments,
            cross_repo_commit_and_open_prs,
            visual_screenshot,
            visual_click,
            visual_type,
            visual_swipe,
            update_dashboard,
            # No more *load_repo_tools(work_dir) — skills replace this
        ],
        subagents=subagent_configs,
        backend=sandbox_backend,
        middleware=[
            ToolErrorMiddleware(),
            check_message_queue_before_model,
            ensure_no_empty_msg,
            open_pr_if_needed,
        ],
    ).with_config(config)
```

- [ ] **Step 7: Delete repo_tool_loader.py**

```bash
rm agent/tools/repo_tool_loader.py
```

- [ ] **Step 8: Run all tests to verify nothing is broken**

Run: `cd /Users/mikechatsky/projects/amp/amp-swe-agent && uv run pytest tests/ -v --no-header`
Expected: ALL tests PASS

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: wire SubAgentMiddleware, remove repo_tool_loader"
```

---

### Task 4: Update construct_system_prompt to handle no-skills orchestrator mode

**Files:**
- Modify: `agent/prompt.py`

- [ ] **Step 1: Update construct_system_prompt to skip skills injection when repo_skills is None**

The existing code at lines 439-450 already handles `if repo_skills:` — when we pass `None`, it simply skips the entire skills block. Verify this is the case by reading the code.

The `TOOL_MAPPING_PREAMBLE` is only added when `repo_skills` is truthy (line 440), so passing `None` cleanly removes all skill content from the orchestrator's prompt. No code change needed here.

- [ ] **Step 2: Verify the orchestrator prompt is lean**

Write a quick verification test:

```python
# tests/test_subagent_config.py — add this

from agent.prompt import construct_system_prompt

def test_orchestrator_prompt_has_no_skills_or_conventions() -> None:
    """Orchestrator prompt should not contain skill or convention content."""
    prompt = construct_system_prompt(
        working_dir="/sandbox",
        repo_conventions=None,
        repo_skills=None,
    )
    assert "<skills_" not in prompt
    assert "TOOL_MAPPING" not in prompt
    assert "Skill:" not in prompt
    assert "<conventions_" not in prompt
    # Base sections should still be there
    assert "Working Environment" in prompt
```

- [ ] **Step 3: Run the test**

Run: `cd /Users/mikechatsky/projects/amp/amp-swe-agent && uv run pytest tests/test_subagent_config.py::test_orchestrator_prompt_has_no_skills -v --no-header`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_subagent_config.py
git commit -m "test: verify orchestrator prompt excludes skills"
```

---

### Task 5: Verify end-to-end and run full test suite

**Files:**
- Test: `tests/`

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/mikechatsky/projects/amp/amp-swe-agent && uv run pytest tests/ -v --no-header`
Expected: ALL tests PASS

- [ ] **Step 2: Verify no references to repo_tool_loader remain**

Run: `cd /Users/mikechatsky/projects/amp/amp-swe-agent && grep -r "repo_tool_loader\|load_repo_tools\|\.swe/tools" agent/ --include="*.py"`
Expected: No output (all references removed)

- [ ] **Step 3: Verify skills.py imports are correct**

Run: `cd /Users/mikechatsky/projects/amp/amp-swe-agent && uv run python -c "from agent.utils.skills import read_skills_in_sandbox, read_agent_knowledge_in_sandbox; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Verify prompt.py imports are correct**

Run: `cd /Users/mikechatsky/projects/amp/amp-swe-agent && uv run python -c "from agent.prompt import construct_subagent_prompt, build_subagent_description; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit final state**

```bash
git add -A
git commit -m "chore: verify end-to-end integration of sub-agent skills"
```
