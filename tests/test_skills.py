"""Tests for agent.utils.skills — skill discovery and reading."""

from __future__ import annotations

import fnmatch
import shlex

import pytest
from deepagents.backends.protocol import ExecuteResponse

from agent.utils.skills import read_skills_in_sandbox


class _FakeSandboxBackend:
    """Simulates sandbox filesystem for skill discovery tests."""

    def __init__(self, fs: dict[str, str] | None = None) -> None:
        self.fs = fs or {}

    @property
    def id(self) -> str:
        return "fake-sandbox"

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        del timeout

        # Handle find commands for skill discovery
        if command.startswith("find "):
            # Extract the base directory from the find command
            # Use shlex.split to handle quoted paths
            parts = shlex.split(command.split("2>/dev/null")[0].strip())
            base_dir = parts[1]
            # Check for -name filter
            name_filter = None
            if "-name" in parts:
                name_idx = parts.index("-name")
                name_filter = parts[name_idx + 1].strip("'\"")

            matches = []
            for path in sorted(self.fs.keys()):
                if not path.startswith(base_dir):
                    continue
                filename = path.rsplit("/", 1)[-1]
                if name_filter and not fnmatch.fnmatch(filename, name_filter):
                    continue
                # Rough maxdepth check: count path segments after base_dir
                relative = path[len(base_dir) :].lstrip("/")
                depth = len(relative.split("/"))
                if "-maxdepth" in parts:
                    md_idx = parts.index("-maxdepth")
                    max_depth = int(parts[md_idx + 1])
                    if depth > max_depth:
                        continue
                matches.append(path)

            if matches:
                return ExecuteResponse(
                    output="\n".join(matches), exit_code=0, truncated=False
                )
            return ExecuteResponse(output="", exit_code=0, truncated=False)

        # Handle test -f && cat commands
        if "test -f" in command and "cat" in command:
            # Extract the path from "test -f <path> && cat <path>"
            # The path may be shell-quoted
            for key in self.fs:
                quoted = shlex.quote(key)
                if quoted in command or key in command:
                    return ExecuteResponse(
                        output=self.fs[key], exit_code=0, truncated=False
                    )
            return ExecuteResponse(output="", exit_code=1, truncated=False)

        return ExecuteResponse(output="", exit_code=1, truncated=False)


@pytest.mark.asyncio
async def test_returns_empty_for_none_repo_dir() -> None:
    backend = _FakeSandboxBackend()
    result = await read_skills_in_sandbox(backend, None)
    assert result == {}


@pytest.mark.asyncio
async def test_returns_empty_when_no_skills_dir() -> None:
    backend = _FakeSandboxBackend(fs={})
    result = await read_skills_in_sandbox(backend, "/repo")
    assert result == {}


@pytest.mark.asyncio
async def test_discovers_skill_with_references() -> None:
    fs = {
        "/repo/.claude/skills/my-skill/SKILL.md": "# My Skill\nDo the thing.",
        "/repo/.claude/skills/my-skill/references/api.md": "API ref content",
        "/repo/.claude/skills/my-skill/references/config.md": "Config ref content",
    }
    backend = _FakeSandboxBackend(fs=fs)

    result = await read_skills_in_sandbox(backend, "/repo")

    assert "my-skill" in result
    assert result["my-skill"]["content"] == "# My Skill\nDo the thing."
    assert result["my-skill"]["references"] == {
        "api": "API ref content",
        "config": "Config ref content",
    }


@pytest.mark.asyncio
async def test_multiple_skills_discovered() -> None:
    fs = {
        "/repo/.claude/skills/alpha/SKILL.md": "Alpha skill content",
        "/repo/.claude/skills/beta/SKILL.md": "Beta skill content",
        "/repo/.claude/skills/beta/references/notes.md": "Beta notes",
    }
    backend = _FakeSandboxBackend(fs=fs)

    result = await read_skills_in_sandbox(backend, "/repo")

    assert len(result) == 2
    assert result["alpha"]["content"] == "Alpha skill content"
    assert result["alpha"]["references"] == {}
    assert result["beta"]["content"] == "Beta skill content"
    assert result["beta"]["references"] == {"notes": "Beta notes"}
