# Per-Repo Sub-Agent Skills Architecture

## Problem

The SWE agent currently loads ALL skills from ALL repos into a single system prompt, consuming ~40K+ tokens. Skills from `.agents/skills/` directories aren't scanned at all. The agent has no way to know when to apply which skill, and context bloat degrades performance.

## Solution

Replace the single-agent-with-all-skills model with an **orchestrator + per-repo specialist sub-agents** architecture. Each sub-agent is a repo expert with that repo's full knowledge pre-loaded. The orchestrator stays lean and delegates repo-specific coding work.

## Architecture

### Orchestrator Agent

- Lean system prompt (~4,500 tokens): base instructions + cross-repo tool schemas + sub-agent descriptions
- **Tools**: `fetch_url`, `github_comment`, `github_review`, `linear_*`, `slack_thread_reply`, `commit_and_open_pr`, `cross_repo_pr`, `web_search`, `dashboard` — plus the auto-created `task` tool from `SubAgentMiddleware`
- **No repo skills, conventions, or agent knowledge** in its context
- **Responsibilities**: understand the task, plan work, delegate to sub-agents, coordinate results, handle PRs and external communication

### Per-Repo Sub-Agents

Auto-generated at startup from repos in the sandbox. Each sub-agent receives:

1. **Conventions** — `CLAUDE.md` + `AGENTS.md` from repo root
2. **Skills** (full content) — from both `.claude/skills/*/SKILL.md` and `.agents/skills/*/SKILL.md`, deduplicated by name (`.claude/` wins)
3. **Agent knowledge** (full content) — from `.claude/agents/*.md`
4. **Common coding tools** — file read/write/edit, bash sandboxed to repo dir, `web_search`, `fetch_url`

Sub-agents are ephemeral — they exist only for the duration of a delegated task and return a result string to the orchestrator.

### Task Flow

```
1. Task arrives (e.g., GitHub issue requiring changes to RF backend + iOS app)
2. Orchestrator analyzes task, plans which repos need changes
3. Orchestrator calls: task("Add validation rule to backend", "RedefinedFitness")
4. RF sub-agent executes with full RF knowledge (conventions + 33 skills + 9 agent docs)
5. RF sub-agent returns result
6. Orchestrator calls: task("Show validation errors in workout view", "amp-ios")
7. amp-ios sub-agent executes with full iOS knowledge (conventions + 8 skills + 15 agent docs)
8. amp-ios sub-agent returns result
9. Orchestrator coordinates PR, posts comments, updates Linear
```

For independent work across repos, the orchestrator can spawn sub-agents sequentially or (if supported by the framework) in parallel.

## Knowledge Sources Per Sub-Agent

For each repo, the following paths are scanned:

```
repo_root/
├── CLAUDE.md                    → conventions
├── AGENTS.md                    → conventions
├── .claude/
│   ├── skills/*/SKILL.md        → skills (full content + references/)
│   └── agents/*.md              → agent knowledge
└── .agents/
    └── skills/*/SKILL.md        → skills (full content + references/)
```

### Skill Deduplication

When the same skill name appears in both `.claude/skills/` and `.agents/skills/`, the `.claude/skills/` version takes precedence.

### Context Budget Estimates

| Sub-agent | Conventions | Skills | Agent Knowledge | Tools | Total |
|-----------|------------|--------|-----------------|-------|-------|
| amp-ios | ~2,000 | ~4,000 (8 skills) | ~6,000 (15 files) | ~1,500 | ~14,500 |
| RedefinedFitness | ~3,000 | ~15,000 (33 skills) | ~4,000 (9 files) | ~1,500 | ~24,500 |
| Orchestrator | ~2,000 | 0 | 0 | ~2,000 | ~4,500 |

**Safety valve**: If a repo's total knowledge exceeds ~30K tokens, fall back to index-only mode for skills (compact summaries in prompt + `lookup_skill` tool for on-demand retrieval) for that sub-agent only.

## Dynamic Configuration

Sub-agents are auto-generated at startup — no hardcoded repo configurations.

```python
def build_subagent_configs(sandbox_root: str) -> list[SubAgent]:
    """Auto-generate one sub-agent config per repo in sandbox."""
    subagents = []
    for repo_dir in sorted(sandbox_root.iterdir()):
        repo_name = repo_dir.name
        conventions = read_conventions(repo_dir)
        skills = load_all_skills(repo_dir)       # .claude/skills/ + .agents/skills/
        agent_knowledge = load_agent_knowledge(repo_dir)  # .claude/agents/*.md

        system_prompt = construct_subagent_prompt(
            repo_name, conventions, skills, agent_knowledge
        )
        description = build_subagent_description(
            repo_name, conventions, skills
        )
        # common_coding_tools = file read/write/edit, bash (sandboxed), web_search, fetch_url
        subagents.append({
            "name": repo_name,
            "description": description,
            "system_prompt": system_prompt,
            "tools": common_coding_tools,
        })
    return subagents
```

### Orchestrator Sub-Agent Descriptions

The orchestrator sees auto-generated summaries per sub-agent (~150-200 tokens each):

```
task("amp-ios"):
  "iOS mobile app specialist. Swift, SwiftUI, Xcode, Tuist.
   Has expertise in: swift-code-style, architecture-patterns,
   testing-guide, swift-concurrency, swiftui-expert, fix-flaky-tests,
   using-tuist-generated-projects, debug-generated-project.
   Also knows: xcode-build, swiftlint, snapshot-tests, amp-motion,
   amp-workout-controllers, and 10 more."
```

These are generated from skill names + first paragraph of CLAUDE.md.

### Adding a New Repo

Zero configuration needed. Add a repo to the sandbox with the standard directory structure and a sub-agent is auto-created. No code changes required.

## Files to Change

### 1. `agent/server.py`
- Add `build_subagent_configs()` function that iterates sandbox repos
- Add `SubAgentMiddleware` to middleware list with generated configs
- Remove `load_repo_tools()` call and `.swe/tools.py` loading — skills replace this mechanism
- Keep cross-repo tools (GitHub, Linear, Slack, PR) on orchestrator

### 2. `agent/prompt.py`
- Remove line 393 sub-agent prohibition ("you do not have subagents; perform the work sequentially yourself")
- Add orchestrator instructions: when to delegate, how to coordinate, how to sequence dependent cross-repo work
- New function `construct_subagent_prompt(repo_name, conventions, skills, agent_knowledge)` — builds per-repo sub-agent system prompt with full knowledge stack
- New function `build_subagent_description(repo_name, conventions, skills)` — builds compact summary for orchestrator

### 3. `agent/utils/skills.py`
- Add `.agents/skills/` scanning (currently only scans `.claude/skills/`)
- Add `.claude/agents/*.md` scanning (new knowledge source)
- Deduplicate skills by name (`.claude/` wins over `.agents/`)
- Keep full-content loading mode (sub-agents get everything, not summaries)

### 4. `agent/tools/repo_tool_loader.py`
- Delete this file — `.swe/tools.py` dynamic loading is replaced by the skills system
- Remove its import and usage from `server.py`

### 5. No new tool files
- `SubAgentMiddleware` auto-creates the `task` tool
- Sub-agents get common coding tools only (no repo-specific tools)

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Repo with no skills or agent knowledge | Sub-agent created with just CLAUDE.md conventions + base tools |
| Repo with no CLAUDE.md | Sub-agent gets skills + agent knowledge, log warning |
| Single-repo task | Orchestrator delegates to one sub-agent |
| Cross-repo dependency | Orchestrator sequences sub-agents, passes context between them |
| Sub-agent context exceeds ~30K tokens | Fall back to index + lookup_skill for that sub-agent's skills |

## Non-Goals

- Parallel sub-agent execution (sequential is fine for v1; can be added later)
- Sub-agent-to-sub-agent direct communication (orchestrator mediates)
- Dynamic skill hot-reloading during a session (skills loaded once at startup)
- Changes to the skill file format (SKILL.md with YAML frontmatter stays as-is)
