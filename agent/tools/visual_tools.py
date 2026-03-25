"""Visual testing tools using Peekaboo for iOS Simulator interaction."""

import logging
from typing import Any

from langgraph.config import get_config

from ..utils.sandbox_paths import resolve_repo_dir
from ..utils.sandbox_state import get_sandbox_backend_sync

logger = logging.getLogger(__name__)

IOS_REPO_NAME = "amp-ios"


def _get_sandbox_and_repo_dir() -> tuple[Any, str]:
    """Get the sandbox backend and iOS repo directory."""
    config = get_config()
    thread_id = config.get("configurable", {}).get("thread_id")
    if not thread_id:
        raise RuntimeError("Missing thread_id in config")

    sandbox_backend = get_sandbox_backend_sync(thread_id)
    if not sandbox_backend:
        raise RuntimeError("No sandbox found for thread")

    repo_dir = resolve_repo_dir(sandbox_backend, IOS_REPO_NAME)
    return sandbox_backend, repo_dir


def visual_screenshot(
    app: str = "Simulator",
    analyze: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    """Capture a screenshot of the iOS Simulator (or any app) using Peekaboo.

    Optionally analyze the screenshot with AI vision to verify UI state.

    Args:
        app: Application to capture. Default "Simulator".
            Use "frontmost" for the active window, or a specific app name/bundle ID.
        analyze: Optional AI prompt to analyze the screenshot.
            Example: "Is the login screen visible?"
            Example: "What screen is the app showing? Describe the UI elements."
            Example: "Does the workout list show a duration field?"
            If None, just captures the screenshot without analysis.
        path: Optional output path for the screenshot file.
            If None, saves to a default location in the repo directory.

    Returns:
        Dictionary with success status, screenshot path, and optional analysis.
    """
    try:
        sandbox_backend, repo_dir = _get_sandbox_and_repo_dir()

        if not path:
            path = f"{repo_dir}/screenshot.png"

        cmd = f"peekaboo image --app '{app}' --path '{path}' --json"
        if analyze:
            safe_analyze = analyze.replace("'", "'\\''")
            cmd = f"peekaboo image --app '{app}' --path '{path}' --analyze '{safe_analyze}' --json"

        result = sandbox_backend.execute(cmd)
        return {
            "success": result.exit_code == 0,
            "error": None if result.exit_code == 0 else "Screenshot capture failed",
            "output": result.output or "",
            "screenshot_path": path if result.exit_code == 0 else None,
        }
    except Exception as e:
        logger.exception("visual_screenshot failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}


def visual_click(
    app: str = "Simulator",
    text: str | None = None,
    x: int | None = None,
    y: int | None = None,
) -> dict[str, Any]:
    """Click on a UI element in the iOS Simulator using Peekaboo.

    Can click by text content (accessibility label) or by coordinates.

    Args:
        app: Application to interact with. Default "Simulator".
        text: Text/label of the element to click (e.g., "Log In", "Start Workout").
            Peekaboo uses accessibility and OCR to find the element.
        x: X coordinate to click (if not using text).
        y: Y coordinate to click (if not using text).

    Returns:
        Dictionary with success status and output.
    """
    try:
        sandbox_backend, _ = _get_sandbox_and_repo_dir()

        if text:
            safe_text = text.replace("'", "'\\''")
            cmd = f"peekaboo click --app '{app}' --text '{safe_text}' --json"
        elif x is not None and y is not None:
            cmd = f"peekaboo click --app '{app}' --x {x} --y {y} --json"
        else:
            return {"success": False, "error": "Provide either text or x/y coordinates", "output": ""}

        result = sandbox_backend.execute(cmd)
        return {
            "success": result.exit_code == 0,
            "error": None if result.exit_code == 0 else "Click failed",
            "output": result.output or "",
        }
    except Exception as e:
        logger.exception("visual_click failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}


def visual_type(
    text: str,
    app: str = "Simulator",
) -> dict[str, Any]:
    """Type text into the focused field in the iOS Simulator using Peekaboo.

    Args:
        text: Text to type.
        app: Application to interact with. Default "Simulator".

    Returns:
        Dictionary with success status and output.
    """
    try:
        sandbox_backend, _ = _get_sandbox_and_repo_dir()

        safe_text = text.replace("'", "'\\''")
        cmd = f"peekaboo type --app '{app}' --text '{safe_text}' --json"

        result = sandbox_backend.execute(cmd)
        return {
            "success": result.exit_code == 0,
            "error": None if result.exit_code == 0 else "Type failed",
            "output": result.output or "",
        }
    except Exception as e:
        logger.exception("visual_type failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}


def visual_swipe(
    direction: str,
    app: str = "Simulator",
) -> dict[str, Any]:
    """Perform a swipe gesture in the iOS Simulator using Peekaboo.

    Args:
        direction: Swipe direction — "up", "down", "left", or "right".
        app: Application to interact with. Default "Simulator".

    Returns:
        Dictionary with success status and output.
    """
    try:
        sandbox_backend, _ = _get_sandbox_and_repo_dir()
        cmd = f"peekaboo swipe --app '{app}' --direction {direction} --json"
        result = sandbox_backend.execute(cmd)
        return {
            "success": result.exit_code == 0,
            "error": None if result.exit_code == 0 else "Swipe failed",
            "output": result.output or "",
        }
    except Exception as e:
        logger.exception("visual_swipe failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}
