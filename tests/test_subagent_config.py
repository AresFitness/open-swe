"""Tests for sub-agent configuration generation."""

from __future__ import annotations

from agent.prompt import construct_system_prompt
from agent.server import build_subagent_configs


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

    for config in configs:
        assert "name" in config
        assert "description" in config
        assert "system_prompt" in config
        assert config["name"] in config["description"]


def test_empty_repo_data_returns_empty() -> None:
    configs = build_subagent_configs({}, work_dir="/sandbox")
    assert configs == []
