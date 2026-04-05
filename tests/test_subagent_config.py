"""Tests for sub-agent configuration generation."""

from __future__ import annotations

from agent.server import build_subagent_configs


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
