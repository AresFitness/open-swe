# Repo Skill Consumption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consume Claude Code skills from cloned repos (starting with iOS `test-on-simulator`) by injecting them into the system prompt with a tool mapping preamble, replacing the hard-coded Maestro tools.

**Architecture:** New `agent/utils/skills.py` discovers `.claude/skills/*/SKILL.md` + references in cloned repos. `prompt.py` gets a tool mapping preamble and skill injection block. Hard-coded `maestro_tools.py` is deleted.

**Tech Stack:** Python 3.12, deepagents SandboxBackendProtocol, pytest

---

### Task 1: Create `agent/utils/skills.py` — Skill Discovery & Reading

**Files:**
- Create: `agent/utils/skills.py`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Write the failing test for skill discovery**

```python
# tests/test_skills.py
from __future__ import annotations

import shlex

from deepagents.backends.protocol import ExecuteResponse

from agent.utils.skills import read_skills_in_sandbox


class _FakeSandboxBackend:
    """Minimal sandbox backend that returns pre-configured shell responses."""

    def __init__(self, fs: dict[str, str] | None = None) -> None:
        self.fs = fs or {}

    @property
    def id(self) -> str:
        return "fake-sandbox"

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        del timeout
        # Handle `find` for skill discovery — filter to the base dir in the command
        if command.startswith("find "):
            parts = shlex.split(command)
            base_dir = parts[1] if len(parts) > 1 else ""
            matches = []
            for path in self.fs:
                if path.startswith(base_dir) and path.endswith("/SKILL.md"):
                    matches.append(path)
            return ExecuteResponse(
                output="\n".join(sorted(matches)) if matches else "",
                exit_code=0 if matches else 1,
                truncated=False,
            )
        # Handle `test -f <path> && cat <path>`
        for path, content in self.fs.items():
            if shlex.quote(path) in command and "cat" in command:
                return ExecuteResponse(output=content, exit_code=0, truncated=False)
        # Handle `ls` for references directory
        if "ls " in command:
            # Extract the directory path from the ls command
            for path in self.fs:
                dir_part = command.split("ls ")[-1].strip().strip("'\"")
                if path.startswith(dir_part):
                    filename = path[len(dir_part):].lstrip("/")
                    if "/" not in filename:
                        return ExecuteResponse(output=filename, exit_code=0, truncated=False)
            return ExecuteResponse(output="", exit_code=1, truncated=False)
        return ExecuteResponse(output="", exit_code=1, truncated=False)


async def test_discovers_skill_with_references():
    """Skills with SKILL.md and references/ are fully loaded."""
    sandbox = _FakeSandboxBackend(fs={
        "/work/amp-ios/.claude/skills/test-on-simulator/SKILL.md": (
            "---\nname: test-on-simulator\n"
            "description: Test on iOS Simulator\n---\n"
            "# Test on Simulator\nRun maestro tests."
        ),
        "/work/amp-ios/.claude/skills/test-on-simulator/references/maestro-ref.md": (
            "# Maestro Reference\nSome maestro docs."
        ),
    })
    result = await read_skills_in_sandbox(sandbox, "/work/amp-ios")
    assert "test-on-simulator" in result
    skill = result["test-on-simulator"]
    assert "Run maestro tests" in skill["content"]
    assert "maestro-ref" in skill["references"]
    assert "Some maestro docs" in skill["references"]["maestro-ref"]


async def test_returns_empty_when_no_skills_dir():
    """Repos without .claude/skills/ return empty dict."""
    sandbox = _FakeSandboxBackend(fs={})
    result = await read_skills_in_sandbox(sandbox, "/work/backend")
    assert result == {}


async def test_returns_empty_for_none_repo_dir():
    """None repo_dir returns empty dict."""
    sandbox = _FakeSandboxBackend(fs={})
    result = await read_skills_in_sandbox(sandbox, None)
    assert result == {}


async def test_multiple_skills_discovered():
    """Multiple skills in the same repo are all loaded."""
    sandbox = _FakeSandboxBackend(fs={
        "/work/repo/.claude/skills/skill-a/SKILL.md": (
            "---\nname: skill-a\ndescription: A\n---\nSkill A content."
        ),
        "/work/repo/.claude/skills/skill-b/SKILL.md": (
            "---\nname: skill-b\ndescription: B\n---\nSkill B content."
        ),
    })
    result = await read_skills_in_sandbox(sandbox, "/work/repo")
    assert "skill-a" in result
    assert "skill-b" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/sapirm/open-swe && uv run pytest tests/test_skills.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.utils.skills'`

- [ ] **Step 3: Write the implementation**

```python
# agent/utils/skills.py
"""Helpers for reading Claude Code skills from repositories."""

from __future__ import annotations

import asyncio
import logging
import os
import shlex

from deepagents.backends.protocol import SandboxBackendProtocol

logger = logging.getLogger(__name__)


async def read_skills_in_sandbox(
    sandbox_backend: SandboxBackendProtocol,
    repo_dir: str | None,
) -> dict[str, dict]:
    """Discover and read Claude Code skills from a repo's .claude/skills/ directory.

    Scans for .claude/skills/*/SKILL.md and reads each skill's content
    plus any files in its references/ subdirectory.

    Args:
        sandbox_backend: The sandbox backend to execute commands in.
        repo_dir: Path to the repo root in the sandbox.

    Returns:
        Dict mapping skill_name to {"content": str, "references": dict[str, str]}.
        Returns empty dict if no skills found or repo_dir is None.
    """
    if not repo_dir:
        return {}

    loop = asyncio.get_event_loop()
    skills_base = f"{repo_dir}/.claude/skills"
    safe_skills_base = shlex.quote(skills_base)

    # Discover all SKILL.md files
    find_result = await loop.run_in_executor(
        None,
        sandbox_backend.execute,
        f"find {safe_skills_base} -name 'SKILL.md' -maxdepth 2 -type f 2>/dev/null",
    )
    if find_result.exit_code != 0 or not find_result.output or not find_result.output.strip():
        logger.debug("No skills found at %s", skills_base)
        return {}

    skill_paths = [p.strip() for p in find_result.output.strip().split("\n") if p.strip()]
    skills: dict[str, dict] = {}

    for skill_path in skill_paths:
        # Extract skill name from path: .claude/skills/<name>/SKILL.md
        skill_dir = os.path.dirname(skill_path)
        skill_name = os.path.basename(skill_dir)

        # Read SKILL.md
        safe_skill_path = shlex.quote(skill_path)
        content_result = await loop.run_in_executor(
            None,
            sandbox_backend.execute,
            f"test -f {safe_skill_path} && cat {safe_skill_path}",
        )
        if content_result.exit_code != 0 or not content_result.output:
            logger.warning("Failed to read skill at %s", skill_path)
            continue

        # Read references/ directory
        references: dict[str, str] = {}
        refs_dir = f"{skill_dir}/references"
        safe_refs_dir = shlex.quote(refs_dir)
        ls_result = await loop.run_in_executor(
            None,
            sandbox_backend.execute,
            f"find {safe_refs_dir} -maxdepth 1 -type f -name '*.md' 2>/dev/null",
        )
        if ls_result.exit_code == 0 and ls_result.output and ls_result.output.strip():
            ref_paths = [p.strip() for p in ls_result.output.strip().split("\n") if p.strip()]
            for ref_path in ref_paths:
                ref_name = os.path.splitext(os.path.basename(ref_path))[0]
                safe_ref_path = shlex.quote(ref_path)
                ref_result = await loop.run_in_executor(
                    None,
                    sandbox_backend.execute,
                    f"cat {safe_ref_path}",
                )
                if ref_result.exit_code == 0 and ref_result.output:
                    references[ref_name] = ref_result.output.strip()

        skills[skill_name] = {
            "content": content_result.output.strip(),
            "references": references,
        }
        logger.info(
            "Loaded skill '%s' from %s (%d references)",
            skill_name, repo_dir, len(references),
        )

    return skills
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/sapirm/open-swe && uv run pytest tests/test_skills.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/sapirm/open-swe
git add agent/utils/skills.py tests/test_skills.py
git commit -m "feat: add skill discovery and reading from cloned repos

Reads .claude/skills/*/SKILL.md and references/ from repos in the
sandbox. Returns structured dict for prompt injection."
```

---

### Task 2: Add Tool Mapping Preamble and Skill Injection to `prompt.py`

**Files:**
- Modify: `agent/prompt.py:421-484`
- Test: `tests/test_skill_prompt_injection.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_skill_prompt_injection.py
from __future__ import annotations

from agent.prompt import construct_system_prompt


def test_skills_injected_into_prompt():
    """Skills content and references appear in the system prompt."""
    repo_skills = {
        "amp-ios": {
            "test-on-simulator": {
                "content": "---\nname: test-on-simulator\n---\n# Test on Simulator\nRun tests.",
                "references": {
                    "maestro-ref": "# Maestro Reference\nDocs here.",
                },
            },
        },
    }
    prompt = construct_system_prompt("/work", repo_skills=repo_skills)
    assert "<skills_amp-ios>" in prompt
    assert "Run tests." in prompt
    assert "### Reference: maestro-ref" in prompt
    assert "Docs here." in prompt
    assert "</skills_amp-ios>" in prompt


def test_tool_mapping_preamble_injected_when_skills_present():
    """Tool mapping preamble appears when skills are provided."""
    repo_skills = {
        "repo": {
            "some-skill": {
                "content": "# Skill\nContent.",
                "references": {},
            },
        },
    }
    prompt = construct_system_prompt("/work", repo_skills=repo_skills)
    assert "<tool_mapping>" in prompt
    assert "Bash" in prompt
    assert "execute" in prompt
    assert "AskUserQuestion" in prompt
    assert "slack_thread_reply" in prompt
    assert "</tool_mapping>" in prompt


def test_no_tool_mapping_when_no_skills():
    """Tool mapping preamble is NOT injected when no skills are provided."""
    prompt = construct_system_prompt("/work")
    assert "<tool_mapping>" not in prompt


def test_multiple_repos_skills_injected():
    """Skills from multiple repos each get their own section."""
    repo_skills = {
        "amp-ios": {
            "skill-a": {"content": "Skill A content.", "references": {}},
        },
        "backend": {
            "skill-b": {"content": "Skill B content.", "references": {}},
        },
    }
    prompt = construct_system_prompt("/work", repo_skills=repo_skills)
    assert "<skills_amp-ios>" in prompt
    assert "<skills_backend>" in prompt
    assert "Skill A content." in prompt
    assert "Skill B content." in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/sapirm/open-swe && uv run pytest tests/test_skill_prompt_injection.py -v`
Expected: FAIL — `construct_system_prompt()` does not accept `repo_skills` parameter

- [ ] **Step 3: Add the tool mapping constant and update `construct_system_prompt`**

Add the `TOOL_MAPPING_PREAMBLE` constant before `construct_system_prompt` in `agent/prompt.py`:

```python
TOOL_MAPPING_PREAMBLE = """
<tool_mapping>
Skills loaded from repos are written for Claude Code and reference its tool names.
When following skill instructions, use these equivalents:

- Bash → execute (run shell commands in the sandbox)
- Read → execute with `cat`
- Write → execute with file write commands
- Grep → execute with `grep` or `rg`
- Glob → execute with `find` or `ls`
- Edit → execute with `sed` or write the full file
- AskUserQuestion → use your communication channel (slack_thread_reply, linear_comment, or github_comment depending on the task source)
- Agent → you do not have subagents; perform the work sequentially yourself

When a skill says to "present to the user" or "wait for approval", send the message via your communication channel and STOP. The user will respond as a follow-up message in your thread. Do not proceed past approval gates until you receive a response.

When a skill says to "take a screenshot", "read a screenshot", or present visual results:
1. Capture the screenshot via execute
2. Analyze it yourself (describe what you see)
3. Share it with the user — call update_dashboard(screenshots=[path]) AND include a description in your communication message
Always share screenshots after each test step, when asking for help, and in the final results summary.
</tool_mapping>
"""
```

Update the `construct_system_prompt` function signature and body at `agent/prompt.py:421`:

```python
def construct_system_prompt(
    working_dir: str,
    linear_project_id: str = "",
    linear_issue_number: str = "",
    agents_md: str = "",
    repo_conventions: dict[str, str] | None = None,
    repo_skills: dict[str, dict] | None = None,
    superpowers_prompt: str = "",
) -> str:
```

Add skill injection logic after the `repo_conventions` block (after line 448) and before the `superpowers_prompt` block:

```python
    if repo_skills:
        agents_md_section += TOOL_MAPPING_PREAMBLE
        for repo_name, skills in repo_skills.items():
            if skills:
                agents_md_section += f"\n<skills_{repo_name}>\n"
                for skill_name, skill_data in skills.items():
                    agents_md_section += f"## Skill: {skill_name}\n"
                    agents_md_section += f"{skill_data['content']}\n\n"
                    for ref_name, ref_content in skill_data.get("references", {}).items():
                        agents_md_section += f"### Reference: {ref_name}\n"
                        agents_md_section += f"{ref_content}\n\n"
                agents_md_section += f"</skills_{repo_name}>\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/sapirm/open-swe && uv run pytest tests/test_skill_prompt_injection.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/sapirm/open-swe
git add agent/prompt.py tests/test_skill_prompt_injection.py
git commit -m "feat: add tool mapping preamble and skill injection to system prompt

Skills from repos are injected in <skills_reponame> tags with references.
Tool mapping preamble translates Claude Code tool names to agent equivalents."
```

---

### Task 3: Wire Skill Loading into `server.py`

**Files:**
- Modify: `agent/server.py:37-67` (imports)
- Modify: `agent/server.py:451-496` (skill reading + prompt construction)

- [ ] **Step 1: Add the import**

Add after line 80 in `agent/server.py` (after the `read_agents_md_in_sandbox` import):

```python
from .utils.skills import read_skills_in_sandbox
```

- [ ] **Step 2: Add skill reading after CLAUDE.md reading**

Insert after the `repo_conventions` block (after line 467) and before the superpowers block (line 469):

```python
    # Read skills from all repos
    repo_skills: dict[str, dict] = {}
    primary_skills = await read_skills_in_sandbox(sandbox_backend, repo_dir)
    if primary_skills and repo_name:
        repo_skills[repo_name] = primary_skills
    for extra_repo in additional_repos:
        extra_name = extra_repo.get("name")
        if extra_name and extra_name != repo_name:
            extra_dir = await aresolve_repo_dir(sandbox_backend, extra_name)
            extra_skills = await read_skills_in_sandbox(sandbox_backend, extra_dir)
            if extra_skills:
                repo_skills[extra_name] = extra_skills
```

- [ ] **Step 3: Pass `repo_skills` to `construct_system_prompt`**

Update the `construct_system_prompt` call at line 490 to include the new parameter:

```python
        system_prompt=construct_system_prompt(
            work_dir,
            linear_project_id=linear_project_id,
            linear_issue_number=linear_issue_number,
            agents_md=agents_md,
            repo_conventions=repo_conventions,
            repo_skills=repo_skills,
            superpowers_prompt=superpowers_prompt,
        ),
```

- [ ] **Step 4: Run existing tests to verify nothing broke**

Run: `cd /Users/sapirm/open-swe && uv run pytest tests/ -v`
Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/sapirm/open-swe
git add agent/server.py
git commit -m "feat: wire skill loading into agent initialization

Reads skills from all cloned repos and passes them to the prompt builder
for injection into the system prompt."
```

---

### Task 4: Remove Hard-Coded Maestro Tools

**Files:**
- Delete: `agent/tools/maestro_tools.py`
- Modify: `agent/tools/__init__.py:17,38-40`
- Modify: `agent/server.py:55-57,525-527`

- [ ] **Step 1: Remove maestro imports from `agent/tools/__init__.py`**

Delete line 17:
```python
from .maestro_tools import maestro_record, maestro_screenshot, maestro_test
```

Remove from `__all__` list (lines 38-40):
```python
    "maestro_record",
    "maestro_screenshot",
    "maestro_test",
```

- [ ] **Step 2: Remove maestro imports and tool registrations from `agent/server.py`**

Delete from the imports block (lines 55-57):
```python
    maestro_record,
    maestro_screenshot,
    maestro_test,
```

Delete from the `tools=[...]` list (lines 525-527):
```python
            maestro_test,
            maestro_record,
            maestro_screenshot,
```

- [ ] **Step 3: Delete `agent/tools/maestro_tools.py`**

```bash
cd /Users/sapirm/open-swe
rm agent/tools/maestro_tools.py
```

- [ ] **Step 4: Run all tests to verify nothing broke**

Run: `cd /Users/sapirm/open-swe && uv run pytest tests/ -v`
Expected: All tests PASS. No test imports maestro_tools directly.

- [ ] **Step 5: Commit**

```bash
cd /Users/sapirm/open-swe
git add -u agent/tools/maestro_tools.py agent/tools/__init__.py agent/server.py
git commit -m "refactor: remove hard-coded Maestro tools

Maestro testing is now driven by the iOS repo's test-on-simulator skill
injected into the system prompt, using execute() for all commands."
```

---

### Task 5: End-to-End Verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run the full test suite**

```bash
cd /Users/sapirm/open-swe && uv run pytest tests/ -v
```

Expected: All tests PASS including new tests from Tasks 1-2.

- [ ] **Step 2: Verify the agent graph loads without errors**

```bash
cd /Users/sapirm/open-swe && uv run python -c "
from agent.prompt import construct_system_prompt
# Simulate skill injection
skills = {
    'amp-ios': {
        'test-on-simulator': {
            'content': '# Test on Simulator\nRun maestro tests.',
            'references': {'maestro-ref': '# Maestro Ref\nDocs.'},
        },
    },
}
prompt = construct_system_prompt('/work', repo_skills=skills)
assert '<tool_mapping>' in prompt
assert '<skills_amp-ios>' in prompt
assert 'maestro' not in prompt.lower().split('<tool_mapping>')[0]  # No maestro in core prompt
print(f'Prompt generated successfully ({len(prompt)} chars)')
print('Skills section preview:')
idx = prompt.find('<skills_amp-ios>')
print(prompt[idx:idx+300])
"
```

Expected: Prints prompt length and skills section preview without errors.

- [ ] **Step 3: Verify maestro_tools is fully removed**

```bash
cd /Users/sapirm/open-swe && grep -r "maestro_test\|maestro_record\|maestro_screenshot\|maestro_tools" agent/ --include="*.py"
```

Expected: No matches. All references to the old Maestro tools are gone.

- [ ] **Step 4: Verify imports are clean**

```bash
cd /Users/sapirm/open-swe && uv run python -c "from agent.tools import *; print('All tool imports OK')"
```

Expected: Prints "All tool imports OK" without ImportError.
