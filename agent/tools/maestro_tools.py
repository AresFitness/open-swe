"""Maestro E2E testing tools for iOS simulator testing."""

import logging
import os
import shlex
from typing import Any

from langgraph.config import get_config

from ..utils.sandbox_paths import resolve_repo_dir, resolve_sandbox_work_dir
from ..utils.sandbox_state import get_sandbox_backend_sync

logger = logging.getLogger(__name__)


def _get_sandbox_and_work_dir() -> tuple[Any, str]:
    """Get the sandbox backend and work directory."""
    config = get_config()
    thread_id = config.get("configurable", {}).get("thread_id")
    if not thread_id:
        raise RuntimeError("Missing thread_id in config")
    sandbox_backend = get_sandbox_backend_sync(thread_id)
    if not sandbox_backend:
        raise RuntimeError("No sandbox found for thread")
    work_dir = resolve_sandbox_work_dir(sandbox_backend)
    return sandbox_backend, work_dir


def maestro_test(
    flow_yaml: str,
    flow_name: str = "test_flow",
    app_id: str = "com.amp.fitness.dev",
    env_vars: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run a Maestro E2E test flow on the iOS Simulator.

    Write a YAML flow inline and Maestro will execute it against the running
    iOS Simulator. The flow can launch the app, tap elements, input text,
    scroll, assert visibility, and take screenshots.

    Common YAML commands:
        - launchApp                          # Launch the app (uses appId from config)
        - launchApp:
            clearState: true                 # Launch with fresh state
        - tapOn: "Button Text"               # Tap element by visible text
        - tapOn:
            id: "accessibilityIdentifier"    # Tap by accessibility ID
        - inputText: "Hello"                 # Type text into focused field
        - assertVisible: "Expected Text"     # Assert text is on screen
        - assertNotVisible: "Error"          # Assert text is NOT on screen
        - scrollUntilVisible:
            element: "Target Text"
            direction: DOWN                  # Scroll until element found
        - swipe:
            direction: LEFT                  # Swipe gesture
        - takeScreenshot: screenshot_name    # Capture PNG screenshot
        - startRecording: video_name         # Start MP4 recording
        - stopRecording                      # Stop recording
        - back                               # Navigate back
        - hideKeyboard                       # Dismiss keyboard
        - waitForAnimationToEnd              # Wait for animations

    Args:
        flow_yaml: The YAML flow content. Do NOT include the appId config header —
            it is added automatically. Start directly with the commands list.
            Example:
                "- launchApp\\n- tapOn: 'Log In'\\n- assertVisible: 'Welcome'"
        flow_name: Name for this flow (used for file naming). Default "test_flow".
        app_id: iOS app bundle ID. Default "com.amp.fitness.dev".
        env_vars: Optional environment variables to pass to the flow.

    Returns:
        Dictionary with success status, output, screenshots taken, and flow file path.
    """
    try:
        sandbox_backend, work_dir = _get_sandbox_and_work_dir()

        # Create flows directory
        flows_dir = f"{work_dir}/.maestro-flows"
        sandbox_backend.execute(f"mkdir -p {flows_dir}")

        # Build the complete flow YAML with appId header
        full_yaml = f"appId: {app_id}\n---\n{flow_yaml}"

        # Write the flow file
        flow_path = f"{flows_dir}/{flow_name}.yaml"
        sandbox_backend.write(flow_path, full_yaml)

        # Build the command
        output_dir = f"{work_dir}/.maestro-output/{flow_name}"
        sandbox_backend.execute(f"mkdir -p {output_dir}")

        cmd = f"maestro test --format junit --output {shlex.quote(output_dir)} {shlex.quote(flow_path)}"

        if env_vars:
            for k, v in env_vars.items():
                cmd += f" -e {shlex.quote(k)}={shlex.quote(v)}"

        cmd += " 2>&1"

        result = sandbox_backend.execute(cmd)

        # Collect screenshots
        screenshots = []
        ls_result = sandbox_backend.execute(f"find {output_dir} -name '*.png' 2>/dev/null")
        if ls_result.exit_code == 0 and ls_result.output:
            screenshots = [p.strip() for p in ls_result.output.strip().split("\n") if p.strip()]

        return {
            "success": result.exit_code == 0,
            "error": None if result.exit_code == 0 else "Maestro test failed",
            "output": result.output or "",
            "exit_code": result.exit_code,
            "flow_path": flow_path,
            "screenshots": screenshots,
            "output_dir": output_dir,
        }
    except Exception as e:
        logger.exception("maestro_test failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}


def maestro_record(
    flow_yaml: str,
    flow_name: str = "test_flow",
    app_id: str = "com.amp.fitness.dev",
) -> dict[str, Any]:
    """Run a Maestro flow and record the screen as MP4 video.

    Same as maestro_test but captures a video recording of the entire flow execution.
    Videos are limited to 2 minutes max. The recording is saved as an MP4 file.

    Use this for:
    - Visual proof of feature implementation in PR descriptions
    - Debugging UI issues
    - Documenting user flows

    Args:
        flow_yaml: The YAML flow content (same format as maestro_test).
        flow_name: Name for this recording. Default "test_flow".
        app_id: iOS app bundle ID. Default "com.amp.fitness.dev".

    Returns:
        Dictionary with success status, video path, and output.
    """
    try:
        sandbox_backend, work_dir = _get_sandbox_and_work_dir()

        flows_dir = f"{work_dir}/.maestro-flows"
        sandbox_backend.execute(f"mkdir -p {flows_dir}")

        full_yaml = f"appId: {app_id}\n---\n{flow_yaml}"
        flow_path = f"{flows_dir}/{flow_name}.yaml"
        sandbox_backend.write(flow_path, full_yaml)

        output_dir = f"{work_dir}/.maestro-output"
        sandbox_backend.execute(f"mkdir -p {output_dir}")

        video_path = f"{output_dir}/{flow_name}.mp4"
        cmd = f"maestro record --local --output {shlex.quote(video_path)} {shlex.quote(flow_path)} 2>&1"

        result = sandbox_backend.execute(cmd)

        video_exists = sandbox_backend.execute(f"test -f {shlex.quote(video_path)}").exit_code == 0

        return {
            "success": result.exit_code == 0 and video_exists,
            "error": None if result.exit_code == 0 else "Maestro recording failed",
            "output": result.output or "",
            "video_path": video_path if video_exists else None,
        }
    except Exception as e:
        logger.exception("maestro_record failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}


def maestro_screenshot(
    app_id: str = "com.amp.fitness.dev",
    name: str = "screen",
) -> dict[str, Any]:
    """Take a screenshot of the current simulator screen using Maestro.

    Simpler than maestro_test — just captures the current state without running a flow.

    Args:
        app_id: iOS app bundle ID (not used, but kept for consistency).
        name: Screenshot file name (without extension).

    Returns:
        Dictionary with success status and screenshot path.
    """
    try:
        sandbox_backend, work_dir = _get_sandbox_and_work_dir()

        output_dir = f"{work_dir}/.maestro-output/screenshots"
        sandbox_backend.execute(f"mkdir -p {output_dir}")

        # Use a minimal flow that just takes a screenshot
        flow_yaml = f"appId: {app_id}\n---\n- takeScreenshot: {name}"
        flow_path = f"{work_dir}/.maestro-flows/_screenshot.yaml"
        sandbox_backend.execute(f"mkdir -p {work_dir}/.maestro-flows")
        sandbox_backend.write(flow_path, flow_yaml)

        cmd = f"maestro test --output {shlex.quote(output_dir)} {shlex.quote(flow_path)} 2>&1"
        result = sandbox_backend.execute(cmd)

        screenshot_path = f"{output_dir}/{name}.png"
        exists = sandbox_backend.execute(f"test -f {shlex.quote(screenshot_path)}").exit_code == 0

        return {
            "success": exists,
            "error": None if exists else "Screenshot not captured",
            "output": result.output or "",
            "screenshot_path": screenshot_path if exists else None,
        }
    except Exception as e:
        logger.exception("maestro_screenshot failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}
