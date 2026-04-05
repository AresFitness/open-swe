# Repo Skill Consumption: Design Spec

**Date:** 2026-04-05
**Status:** Approved
**Scope:** Prototype — iOS `test-on-simulator` skill as first case. General pattern to be extracted later.

## Problem

The SWE agent maintains hard-coded Maestro testing tools (`maestro_tools.py`) that duplicate knowledge the iOS team already maintains as a Claude Code skill (`test-on-simulator`). These tools rot because they live in a different project from the team that evolves them. The iOS team's skill is the single source of truth for how to test on simulator — it includes retry patterns, self-improving learnings, reusable subflows, reference docs, and known limitations that the hard-coded tools lack entirely.

## Solution

Consume Claude Code skills directly from cloned repos by injecting their content into the agent's system prompt, with a tool mapping preamble that translates Claude Code tool references to the agent's equivalents. Remove the hard-coded Maestro tools — the skill teaches the agent to use `execute()` for all Maestro commands.

## Approach: Skill-as-Prompt Injection

Skills are prompt-level knowledge (instructions for the LLM), not callable tool functions. The agent loads them the same way it already loads CLAUDE.md and AGENTS.md — read from the repo, inject into the system prompt.

### Skill Discovery & Loading

After cloning a repo into the sandbox, the agent scans for `.claude/skills/*/SKILL.md`. For each discovered skill:

1. Parse YAML frontmatter (`name`, `description`, `allowed-tools`)
2. Read `SKILL.md` body
3. Read all files in `references/` subdirectory

New utility: `agent/utils/skills.py` with `read_skills_in_sandbox(sandbox_backend, repo_dir)`. Returns `dict[str, dict]` mapping `skill_name` to `{content: str, references: dict[str, str]}` for a single repo. Called per repo, same as `read_claude_md_in_sandbox()`. The caller in `server.py` aggregates results across repos into `{repo_name: {skill_name: ...}}` before passing to the prompt builder.

### Prompt Injection

`construct_system_prompt()` gets a new `repo_skills` parameter. When non-empty, it injects:

1. A tool mapping preamble (see below)
2. Each skill's content wrapped in `<skills_reponame>` tags with references inlined:

```
<skills_amp-ios>
## Skill: test-on-simulator
[SKILL.md content]

### Reference: maestro-reference
[maestro-reference.md content]

### Reference: app-navigation
[app-navigation.md content]

### Reference: analytics-capture
[analytics-capture.md content]
</skills_amp-ios>
```

### Tool Mapping Preamble

Injected before skills content. Translates Claude Code tool names and behavioral patterns to the agent's environment:

```
<tool_mapping>
Skills loaded from repos are written for Claude Code and reference its tool names.
When following skill instructions, use these equivalents:

- Bash -> execute (run shell commands in the sandbox)
- Read -> execute with `cat`
- Write -> execute with file write commands
- Grep -> execute with `grep` or `rg`
- Glob -> execute with `find` or `ls`
- Edit -> execute with `sed` or write the full file
- AskUserQuestion -> use your communication channel (slack_thread_reply, linear_comment, or github_comment depending on the task source)
- Agent -> you do not have subagents; perform the work sequentially yourself

When a skill says to "present to the user" or "wait for approval", send the message via your communication channel and STOP. The user will respond as a follow-up message in your thread. Do not proceed past approval gates until you receive a response.

When a skill says to "take a screenshot", "read a screenshot", or present visual results:
1. Capture the screenshot via execute
2. Analyze it yourself (describe what you see)
3. Share it with the user -- call update_dashboard(screenshots=[path]) AND include a description in your communication message
Always share screenshots after each test step, when asking for help, and in the final results summary.
</tool_mapping>
```

### Interactive Flow

The skill has several human-in-the-loop points. All map to existing agent infrastructure:

- **Test plan approval (Phase 2):** Agent sends plan via communication channel, stops. User responds, `check_message_queue_before_model` middleware injects response, agent continues.
- **Verification code (Phase 4):** Agent sends "paste your code" message, stops. User responds with code, agent continues sign-in flow.
- **Retry + ask for help:** Agent sends screenshot + failure description, asks how to proceed. Waits for queued response.
- **Screenshot sharing:** Handled by the tool mapping preamble — agent captures, analyzes, and shares via `update_dashboard` + communication channel.

No new middleware or message handling needed. The existing message queue pattern handles all interactive phases.

### Removing Hard-Coded Maestro Tools

- Delete `agent/tools/maestro_tools.py`
- Remove `maestro_test`, `maestro_record`, `maestro_screenshot` from `agent/tools/__init__.py`
- Remove the 3 maestro entries from the `tools=[...]` list in `agent/server.py`

The agent runs Maestro commands through `execute()`, guided by the skill's instructions.

`visual_tools.py` (Peekaboo) remains — it serves a different purpose (direct UI interaction outside of Maestro flows).

## Changes Summary

### New files
- `agent/utils/skills.py` — skill discovery and reading

### Modified files
- `agent/server.py` — call `read_skills_in_sandbox()`, pass to prompt builder
- `agent/prompt.py` — new `repo_skills` param, tool mapping preamble, skill injection logic

### Deleted files
- `agent/tools/maestro_tools.py`

### Modified (removals)
- `agent/tools/__init__.py` — remove maestro exports

### Unchanged
- iOS repo (amp-ios) — zero changes required
- `agent/middleware/` — existing patterns handle interactive flow
- `agent/tools/visual_tools.py` — stays
- `agent/utils/claude_md.py`, `agents_md.py` — stay as-is

## Future Generalization

This prototype covers the iOS `test-on-simulator` skill. Once validated, the pattern generalizes naturally:

- Any repo can add `.claude/skills/` and the agent picks them up
- The tool mapping preamble is repo-agnostic — works for any Claude Code skill
- Backend repo could move its testing knowledge from `.swe/tools.py` functions into skills
- The discovery mechanism scales to multiple skills per repo

The generalization phase should be a separate design cycle after learning from this prototype.
