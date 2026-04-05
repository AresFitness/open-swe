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
