"""Dynamic tool loader — reads .swe/tools.py from each repo in the sandbox."""

import importlib.util
import logging
import os
import sys
import types
from typing import Any, Callable

from langgraph.config import get_config

from ..utils.sandbox_paths import resolve_repo_dir
from ..utils.sandbox_state import get_sandbox_backend_sync

logger = logging.getLogger(__name__)


def _make_sandbox_helper(repo_name: str) -> Callable[[], tuple[Any, str]]:
    """Create a get_sandbox_and_repo_dir helper bound to a specific repo."""

    def get_sandbox_and_repo_dir() -> tuple[Any, str]:
        config = get_config()
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            raise RuntimeError("Missing thread_id in config")
        sandbox_backend = get_sandbox_backend_sync(thread_id)
        if not sandbox_backend:
            raise RuntimeError("No sandbox found for thread")
        repo_dir = resolve_repo_dir(sandbox_backend, repo_name)
        return sandbox_backend, repo_dir

    return get_sandbox_and_repo_dir


def load_repo_tools(sandbox_root: str) -> list[Callable]:
    """Load tools from .swe/tools.py in each repo under sandbox_root.

    Each repo's .swe/tools.py should define a function:

        def register_tools(get_sandbox_and_repo_dir):
            # get_sandbox_and_repo_dir() returns (sandbox_backend, repo_dir)
            # Return a list of tool functions
            ...
            return [tool_fn_1, tool_fn_2, ...]

    Args:
        sandbox_root: Path to the sandbox directory containing repo clones.

    Returns:
        List of tool functions from all repos.
    """
    all_tools: list[Callable] = []

    if not os.path.isdir(sandbox_root):
        logger.debug("Sandbox root %s does not exist, no repo tools to load", sandbox_root)
        return all_tools

    for entry in sorted(os.listdir(sandbox_root)):
        repo_dir = os.path.join(sandbox_root, entry)
        tools_file = os.path.join(repo_dir, ".swe", "tools.py")

        if not os.path.isfile(tools_file):
            continue

        logger.info("Loading tools from %s/.swe/tools.py", entry)

        try:
            # Load the module dynamically
            spec = importlib.util.spec_from_file_location(
                f"swe_tools_{entry.replace('-', '_')}",
                tools_file,
            )
            if spec is None or spec.loader is None:
                logger.warning("Could not create module spec for %s", tools_file)
                continue

            module = importlib.util.module_from_spec(spec)

            # Inject the helper into the module before executing
            helper = _make_sandbox_helper(entry)
            module.get_sandbox_and_repo_dir = helper  # type: ignore[attr-defined]

            spec.loader.exec_module(module)

            # Call register_tools if it exists
            register_fn = getattr(module, "register_tools", None)
            if callable(register_fn):
                tools = register_fn(helper)
                if isinstance(tools, list):
                    all_tools.extend(tools)
                    logger.info("Loaded %d tools from %s", len(tools), entry)
                else:
                    logger.warning("register_tools in %s did not return a list", entry)
            else:
                # Fallback: collect all public functions that aren't helpers
                for name in dir(module):
                    if name.startswith("_"):
                        continue
                    obj = getattr(module, name)
                    if callable(obj) and name not in ("register_tools", "get_sandbox_and_repo_dir"):
                        all_tools.append(obj)
                logger.info(
                    "Loaded %d tools from %s (auto-discovered, no register_tools function)",
                    len([n for n in dir(module) if not n.startswith("_") and callable(getattr(module, n)) and n not in ("register_tools", "get_sandbox_and_repo_dir")]),
                    entry,
                )

        except Exception:
            logger.warning("Failed to load tools from %s", tools_file, exc_info=True)

    return all_tools
