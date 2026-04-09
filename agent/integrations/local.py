import os

from deepagents.backends import LocalShellBackend


def create_local_sandbox(sandbox_id: str | None = None):
    """Create a local shell sandbox with no isolation.

    WARNING: This runs commands directly on the host machine with no sandboxing.
    Only use for local development with human-in-the-loop enabled.

    The root directory defaults to the current working directory and can be
    overridden via the LOCAL_SANDBOX_ROOT_DIR environment variable.

    When ``sandbox_id`` is provided **and** LOCAL_SANDBOX_ROOT_DIR is set,
    the sandbox is created in a per-task subdirectory:
    ``LOCAL_SANDBOX_ROOT_DIR/<sandbox_id>/``.  This gives each task its own
    isolated clone directory and prevents stale state from bleeding between
    tasks.  Without a ``sandbox_id`` the original shared-directory behaviour
    is preserved for backward compatibility.

    Args:
        sandbox_id: Optional task/thread identifier used to create a
            per-task subdirectory under the sandbox root.

    Returns:
        LocalShellBackend instance implementing SandboxBackendProtocol.
    """
    base_dir = os.getenv("LOCAL_SANDBOX_ROOT_DIR", "")
    if base_dir and sandbox_id:
        root_dir = os.path.join(base_dir, sandbox_id)
        os.makedirs(root_dir, exist_ok=True)
    elif base_dir:
        root_dir = base_dir
    else:
        root_dir = os.getcwd()

    return LocalShellBackend(
        root_dir=root_dir,
        inherit_env=True,
    )
