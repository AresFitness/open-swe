"""Backend development tools for the RedefinedFitness pnpm monorepo."""

import logging
from typing import Any

from langgraph.config import get_config

from ..utils.sandbox_paths import resolve_repo_dir
from ..utils.sandbox_state import get_sandbox_backend_sync

logger = logging.getLogger(__name__)

BACKEND_REPO_NAME = "RedefinedFitness"


def _get_sandbox_and_repo_dir() -> tuple[Any, str]:
    """Get the sandbox backend and backend repo directory."""
    config = get_config()
    thread_id = config.get("configurable", {}).get("thread_id")
    if not thread_id:
        raise RuntimeError("Missing thread_id in config")

    sandbox_backend = get_sandbox_backend_sync(thread_id)
    if not sandbox_backend:
        raise RuntimeError("No sandbox found for thread")

    repo_dir = resolve_repo_dir(sandbox_backend, BACKEND_REPO_NAME)
    return sandbox_backend, repo_dir


def backend_test(
    test_path: str | None = None,
    package: str | None = None,
) -> dict[str, Any]:
    """Run backend tests using pnpm.

    Only run tests directly related to the files you changed.
    Never run the full test suite — CI handles that.

    Args:
        test_path: Specific test file path relative to the repo root.
            Example: "packages/api/src/__tests__/myFile.test.ts"
        package: Specific pnpm workspace package to test.
            Example: "@amp/api" or "api"

    Returns:
        Dictionary with success status, output, and exit_code.
    """
    try:
        sandbox_backend, repo_dir = _get_sandbox_and_repo_dir()

        if test_path:
            cmd = f"cd {repo_dir} && pnpm jest --no-colors {test_path}"
        elif package:
            cmd = f"cd {repo_dir} && pnpm --filter {package} test --no-colors"
        else:
            return {
                "success": False,
                "error": "Provide either test_path or package. Never run the full test suite.",
                "output": "",
            }

        result = sandbox_backend.execute(cmd)
        return {
            "success": result.exit_code == 0,
            "error": None if result.exit_code == 0 else "Tests failed",
            "output": result.output or "",
            "exit_code": result.exit_code,
        }
    except Exception as e:
        logger.exception("backend_test failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}


def backend_typecheck(
    package: str | None = None,
) -> dict[str, Any]:
    """Run TypeScript type checking on the backend.

    Args:
        package: Specific pnpm workspace package to typecheck.
            If None, runs typecheck across the whole monorepo.

    Returns:
        Dictionary with success status, output, and exit_code.
    """
    try:
        sandbox_backend, repo_dir = _get_sandbox_and_repo_dir()

        if package:
            cmd = f"cd {repo_dir} && pnpm --filter {package} typecheck --no-colors 2>&1"
        else:
            cmd = f"cd {repo_dir} && pnpm typecheck --no-colors 2>&1"

        result = sandbox_backend.execute(cmd)
        return {
            "success": result.exit_code == 0,
            "error": None if result.exit_code == 0 else "Type errors found",
            "output": result.output or "",
            "exit_code": result.exit_code,
        }
    except Exception as e:
        logger.exception("backend_typecheck failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}


def backend_lint(
    files: str | None = None,
    package: str | None = None,
) -> dict[str, Any]:
    """Run ESLint on the backend code.

    Args:
        files: Space-separated file paths to lint (relative to repo root).
        package: Specific pnpm workspace package to lint.

    Returns:
        Dictionary with success status, output, and exit_code.
    """
    try:
        sandbox_backend, repo_dir = _get_sandbox_and_repo_dir()

        if files:
            cmd = f"cd {repo_dir} && pnpm eslint --no-color {files} 2>&1"
        elif package:
            cmd = f"cd {repo_dir} && pnpm --filter {package} lint --no-colors 2>&1"
        else:
            cmd = f"cd {repo_dir} && pnpm lint --no-colors 2>&1"

        result = sandbox_backend.execute(cmd)
        return {
            "success": result.exit_code == 0,
            "error": None if result.exit_code == 0 else "Lint errors found",
            "output": result.output or "",
            "exit_code": result.exit_code,
        }
    except Exception as e:
        logger.exception("backend_lint failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}


def backend_local(
    action: str = "up",
    component: str | None = None,
) -> dict[str, Any]:
    """Manage the local backend development environment via `pnpm local`.

    This is a unified orchestrator that manages all backend services:
    apollo-router, coprocessor, apollo-server, ai-coach-server,
    program-builder, livekit-server, voice-agent, backoffice, redis, etc.

    It runs a local server on port 9000 with an HTTP API and a dashboard on port 9001.

    Actions:
        up      - Start the orchestrator (runs `pnpm local` in background).
                  This checks prerequisites, installs missing deps, and boots services.
        down    - Stop the orchestrator and all components.
        status  - Get status of all components (queries the orchestrator API).
        start   - Start a specific component (requires `component` arg).
        stop    - Stop a specific component (requires `component` arg).
        restart - Restart a specific component (requires `component` arg).
        logs    - Get recent logs for a component (requires `component` arg).

    Args:
        action: One of "up", "down", "status", "start", "stop", "restart", "logs".
        component: Component name for start/stop/restart/logs actions.
            Valid components: apollo-router, coprocessor, apollo-server,
            ai-coach-server, program-builder, livekit-server, voice-agent,
            backoffice, ai-coach-demo, ai-coach-demo-server, mcp-server, redis.

    Returns:
        Dictionary with success status and output.
    """
    LOCAL_SERVER_PORT = 9000

    try:
        sandbox_backend, repo_dir = _get_sandbox_and_repo_dir()

        if action == "up":
            # Check if already running
            check = sandbox_backend.execute(
                f"curl -s http://localhost:{LOCAL_SERVER_PORT}/api/status 2>/dev/null"
            )
            if check.exit_code == 0 and check.output and check.output.strip().startswith("["):
                return {
                    "success": True,
                    "error": None,
                    "output": "Local dev orchestrator is already running.\n" + check.output,
                }

            # Start pnpm local in background
            log_file = f"{repo_dir}/.pnpm-local.log"
            cmd = (
                f"cd {repo_dir} && "
                f"nohup pnpm local > {log_file} 2>&1 & "
                f"echo $!"
            )
            result = sandbox_backend.execute(cmd)
            pid = result.output.strip().split("\n")[-1] if result.output else ""
            if result.exit_code == 0 and pid:
                sandbox_backend.execute(f"echo {pid} > {repo_dir}/.pnpm-local.pid")
                # Wait for the server to become available
                import time
                for _ in range(30):
                    time.sleep(2)
                    health = sandbox_backend.execute(
                        f"curl -s http://localhost:{LOCAL_SERVER_PORT}/api/status 2>/dev/null"
                    )
                    if health.exit_code == 0 and health.output and health.output.strip().startswith("["):
                        return {
                            "success": True,
                            "error": None,
                            "output": f"Local dev orchestrator started (PID {pid}).\n"
                                      f"API: http://localhost:{LOCAL_SERVER_PORT}\n"
                                      f"Dashboard: http://localhost:9001\n"
                                      f"Status:\n{health.output}",
                        }
                # Didn't come up in time — return log tail
                log_result = sandbox_backend.execute(f"tail -30 {log_file}")
                return {
                    "success": False,
                    "error": "Orchestrator started but API not responding after 60s",
                    "output": f"PID {pid}. Recent log:\n{log_result.output or ''}",
                }
            return {
                "success": False,
                "error": f"Failed to start orchestrator: {result.output}",
                "output": result.output or "",
            }

        elif action == "down":
            pid_result = sandbox_backend.execute(f"cat {repo_dir}/.pnpm-local.pid 2>/dev/null")
            pid = pid_result.output.strip() if pid_result.exit_code == 0 else ""
            # Stop all components first via API
            sandbox_backend.execute(
                f"curl -s -X POST http://localhost:{LOCAL_SERVER_PORT}/api/stop-all 2>/dev/null"
            )
            if pid:
                sandbox_backend.execute(f"kill {pid} 2>/dev/null; sleep 2; kill -9 {pid} 2>/dev/null")
                sandbox_backend.execute(f"rm -f {repo_dir}/.pnpm-local.pid")
                return {"success": True, "error": None, "output": f"Orchestrator stopped (PID {pid})"}
            sandbox_backend.execute("pkill -f '@amp/local-dev' 2>/dev/null || true")
            return {"success": True, "error": None, "output": "Orchestrator stopped"}

        elif action == "status":
            result = sandbox_backend.execute(
                f"curl -s http://localhost:{LOCAL_SERVER_PORT}/api/status 2>/dev/null"
            )
            if result.exit_code != 0 or not result.output:
                return {
                    "success": True,
                    "error": None,
                    "output": "Local dev orchestrator is not running. Use action='up' to start it.",
                }
            return {"success": True, "error": None, "output": result.output}

        elif action in ("start", "stop", "restart"):
            if not component:
                return {
                    "success": False,
                    "error": f"component is required for action '{action}'",
                    "output": "",
                }
            result = sandbox_backend.execute(
                f"curl -s -X POST http://localhost:{LOCAL_SERVER_PORT}/api/{action}/{component}"
            )
            return {
                "success": result.exit_code == 0,
                "error": None if result.exit_code == 0 else f"{action} failed",
                "output": result.output or f"{action} {component} done",
            }

        elif action == "logs":
            if not component:
                return {"success": False, "error": "component is required for action 'logs'", "output": ""}
            result = sandbox_backend.execute(
                f"curl -s http://localhost:{LOCAL_SERVER_PORT}/api/logs/{component} 2>/dev/null"
            )
            return {
                "success": result.exit_code == 0,
                "error": None if result.exit_code == 0 else "Failed to fetch logs",
                "output": result.output or "No logs available",
            }

        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}. Use up, down, status, start, stop, restart, or logs.",
                "output": "",
            }

    except Exception as e:
        logger.exception("backend_local failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}


def backend_generate() -> dict[str, Any]:
    """Run the full backend generation pipeline after schema changes.

    Runs `pnpm generate` which executes:
    gql-compile → cf2tf → codegen → generate:deeplinks

    This is the correct command after modifying the GraphQL schema.
    Use this instead of running codegen alone.

    Returns:
        Dictionary with success status, output, and exit_code.
    """
    try:
        sandbox_backend, repo_dir = _get_sandbox_and_repo_dir()
        cmd = f"cd {repo_dir} && pnpm generate 2>&1"
        result = sandbox_backend.execute(cmd)
        return {
            "success": result.exit_code == 0,
            "error": None if result.exit_code == 0 else "Generate failed",
            "output": result.output or "",
            "exit_code": result.exit_code,
        }
    except Exception as e:
        logger.exception("backend_generate failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}
