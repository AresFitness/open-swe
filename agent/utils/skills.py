"""Helpers for reading Claude Code skills from repositories."""

from __future__ import annotations

import asyncio
import logging
import shlex

from deepagents.backends.protocol import SandboxBackendProtocol

logger = logging.getLogger(__name__)


async def _scan_skills_dir(
    sandbox_backend: SandboxBackendProtocol,
    repo_dir: str,
    subdir: str,
) -> dict[str, dict]:
    """Scan a single skills directory and return discovered skills.

    Parameters
    ----------
    sandbox_backend:
        The sandbox backend to execute commands in.
    repo_dir:
        Root of the repository (e.g. ``/repo``).
    subdir:
        The relative directory under *repo_dir* containing skills
        (e.g. ``.claude/skills`` or ``.agents/skills``).

    Returns a dict mapping skill name to
    ``{"content": str, "references": dict[str, str]}``.
    """
    loop = asyncio.get_event_loop()

    skills_dir = shlex.quote(f"{repo_dir}/{subdir}")
    find_cmd = f"find {skills_dir} -name 'SKILL.md' -maxdepth 2 -type f 2>/dev/null"
    result = await loop.run_in_executor(
        None,
        sandbox_backend.execute,
        find_cmd,
    )

    output = (result.output or "").strip()
    if not output:
        logger.debug("No skills found under %s", skills_dir)
        return {}

    skill_paths = [p for p in output.splitlines() if p.strip() and p.strip().startswith("/")]
    skills: dict[str, dict] = {}

    skills_base = f"{repo_dir}/{subdir}/"

    for skill_path in skill_paths:
        skill_path = skill_path.strip()
        # Extract skill name from path: <repo_dir>/<subdir>/<name>/SKILL.md
        if not skill_path.startswith(skills_base):
            logger.warning("Could not extract skill name from path: %s", skill_path)
            continue
        remainder = skill_path[len(skills_base):]  # "<name>/SKILL.md"
        skill_name = remainder.split("/")[0]

        # Read SKILL.md content
        safe_skill_path = shlex.quote(skill_path)
        read_result = await loop.run_in_executor(
            None,
            sandbox_backend.execute,
            f"test -f {safe_skill_path} && cat {safe_skill_path}",
        )
        if read_result.exit_code != 0:
            logger.debug("Could not read skill file: %s", skill_path)
            continue

        content = (read_result.output or "").strip()
        if not content:
            continue

        # Discover reference files
        skill_dir = f"{repo_dir}/{subdir}/{skill_name}"
        refs_dir = shlex.quote(f"{skill_dir}/references")
        refs_find_cmd = (
            f"find {refs_dir} -maxdepth 1 -type f -name '*.md' 2>/dev/null"
        )
        refs_result = await loop.run_in_executor(
            None,
            sandbox_backend.execute,
            refs_find_cmd,
        )

        references: dict[str, str] = {}
        refs_output = (refs_result.output or "").strip()
        if refs_output:
            for ref_path in refs_output.splitlines():
                ref_path = ref_path.strip()
                if not ref_path:
                    continue
                # Read reference file
                safe_ref_path = shlex.quote(ref_path)
                ref_result = await loop.run_in_executor(
                    None,
                    sandbox_backend.execute,
                    f"test -f {safe_ref_path} && cat {safe_ref_path}",
                )
                if ref_result.exit_code != 0:
                    continue
                ref_content = (ref_result.output or "").strip()
                if ref_content:
                    # Extract reference name (filename without .md extension)
                    ref_filename = ref_path.rsplit("/", 1)[-1]
                    ref_name = ref_filename.removesuffix(".md")
                    references[ref_name] = ref_content

        skills[skill_name] = {"content": content, "references": references}
        logger.info(
            "Loaded skill '%s' from %s/%s (%d references)",
            skill_name, repo_dir, subdir, len(references),
        )

    return skills


async def read_skills_in_sandbox(
    sandbox_backend: SandboxBackendProtocol,
    repo_dir: str | None,
) -> dict[str, dict]:
    """Discover and read Claude Code skills from a repo.

    Skills are scanned from two directories:

    * ``.claude/skills/`` — primary (takes precedence on name collision)
    * ``.agents/skills/`` — secondary

    Each skill lives in its own subdirectory under the skills dir
    (e.g. ``.claude/skills/<name>/``) and must contain a ``SKILL.md`` file.
    Optional reference files can be placed in a ``references/`` subdirectory
    as ``.md`` files.

    Returns a dict mapping skill name to
    ``{"content": str, "references": dict[str, str]}``.
    """
    if not repo_dir:
        return {}

    agents_skills = await _scan_skills_dir(sandbox_backend, repo_dir, ".agents/skills")
    claude_skills = await _scan_skills_dir(sandbox_backend, repo_dir, ".claude/skills")

    # .claude/skills/ wins on name collision
    merged = {**agents_skills, **claude_skills}
    return merged


async def read_agent_knowledge_in_sandbox(
    sandbox_backend: SandboxBackendProtocol,
    repo_dir: str | None,
) -> dict[str, str]:
    """Discover and read agent knowledge files from ``.claude/agents/*.md``.

    Returns a dict mapping filename (without ``.md`` extension) to file content.
    """
    if not repo_dir:
        return {}

    loop = asyncio.get_event_loop()

    agents_dir = shlex.quote(f"{repo_dir}/.claude/agents")
    find_cmd = f"find {agents_dir} -maxdepth 1 -type f -name '*.md' 2>/dev/null"
    result = await loop.run_in_executor(
        None,
        sandbox_backend.execute,
        find_cmd,
    )

    output = (result.output or "").strip()
    if not output:
        logger.debug("No agent knowledge files found under %s", agents_dir)
        return {}

    knowledge: dict[str, str] = {}
    for file_path in output.splitlines():
        file_path = file_path.strip()
        if not file_path:
            continue

        # Read file content
        safe_path = shlex.quote(file_path)
        read_result = await loop.run_in_executor(
            None,
            sandbox_backend.execute,
            f"test -f {safe_path} && cat {safe_path}",
        )
        if read_result.exit_code != 0:
            logger.debug("Could not read agent knowledge file: %s", file_path)
            continue

        content = (read_result.output or "").strip()
        if not content:
            continue

        # Extract name from filename (without .md extension)
        filename = file_path.rsplit("/", 1)[-1]
        name = filename.removesuffix(".md")
        knowledge[name] = content
        logger.info("Loaded agent knowledge '%s' from %s", name, file_path)

    return knowledge
