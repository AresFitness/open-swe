"""Helpers for reading CLAUDE.md conventions from repositories."""

from __future__ import annotations

import asyncio
import logging
import shlex

from deepagents.backends.protocol import SandboxBackendProtocol

logger = logging.getLogger(__name__)


async def read_claude_md_in_sandbox(
    sandbox_backend: SandboxBackendProtocol,
    repo_dir: str | None,
) -> str | None:
    """Read CLAUDE.md from the repo root if it exists."""
    if not repo_dir:
        return None

    safe_path = shlex.quote(f"{repo_dir}/CLAUDE.md")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        sandbox_backend.execute,
        f"test -f {safe_path} && cat {safe_path}",
    )
    if result.exit_code != 0:
        logger.debug("CLAUDE.md not found at %s", safe_path)
        return None
    content = result.output or ""
    content = content.strip()
    return content or None
