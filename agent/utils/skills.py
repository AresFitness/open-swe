"""Helpers for reading Claude Code skills from repositories."""

from __future__ import annotations

import asyncio
import logging
import shlex

from deepagents.backends.protocol import SandboxBackendProtocol

logger = logging.getLogger(__name__)


async def read_skills_in_sandbox(
    sandbox_backend: SandboxBackendProtocol,
    repo_dir: str | None,
) -> dict[str, dict]:
    """Discover and read Claude Code skills from .claude/skills/ in a repo.

    Each skill lives in its own subdirectory under ``.claude/skills/<name>/``
    and must contain a ``SKILL.md`` file. Optional reference files can be
    placed in a ``references/`` subdirectory as ``.md`` files.

    Returns a dict mapping skill name to
    ``{"content": str, "references": dict[str, str]}``.
    """
    if not repo_dir:
        return {}

    loop = asyncio.get_event_loop()

    # Discover SKILL.md files
    skills_dir = shlex.quote(f"{repo_dir}/.claude/skills")
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

    skill_paths = [p for p in output.splitlines() if p.strip()]
    skills: dict[str, dict] = {}

    for skill_path in skill_paths:
        skill_path = skill_path.strip()
        # Extract skill name from path: <repo_dir>/.claude/skills/<name>/SKILL.md
        skills_base = f"{repo_dir}/.claude/skills/"
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
        skill_dir = f"{repo_dir}/.claude/skills/{skill_name}"
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
            "Loaded skill '%s' from %s (%d references)",
            skill_name, repo_dir, len(references),
        )

    return skills
