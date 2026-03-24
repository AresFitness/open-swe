"""iOS development tools for the amp-ios Tuist/Xcode project."""

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


def ios_make(
    target: str,
) -> dict[str, Any]:
    """Run a Makefile target in the iOS project.

    Common targets:
        ready           - Install Tuist deps + convert secrets
        project         - Generate Xcode project (external cache)
        project_nc      - Generate Xcode project (no cache)
        dev_app         - Switch to dev environment + full rebuild
        staging_app     - Switch to staging + full rebuild
        backend         - Pull Apollo GraphQL schema + generate Swift code
        backend_generate - Generate Swift code only (no schema pull)
        assets          - Generate SwiftGen strings
        strings         - Download localized strings from Lokalise
        install         - Install Homebrew dependencies

    Args:
        target: Makefile target to run (e.g., "ready", "project", "dev_app", "backend").

    Returns:
        Dictionary with success status, output, and exit_code.
    """
    try:
        sandbox_backend, repo_dir = _get_sandbox_and_repo_dir()
        cmd = f"cd {repo_dir} && make {target} 2>&1"
        result = sandbox_backend.execute(cmd)
        return {
            "success": result.exit_code == 0,
            "error": None if result.exit_code == 0 else f"make {target} failed",
            "output": result.output or "",
            "exit_code": result.exit_code,
        }
    except Exception as e:
        logger.exception("ios_make failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}


def xcode_build(
    scheme: str = "Amp",
    configuration: str = "Debug",
    destination: str = "platform=iOS Simulator,name=iPhone 16",
) -> dict[str, Any]:
    """Build the iOS project using xcodebuild.

    This builds the Xcode project for the given scheme and destination.
    Use timeout=900 for full builds (they can take 10+ minutes).

    Args:
        scheme: Xcode scheme to build. Default "Amp". Other options:
            "AmpSnapshotTestPlan", "AmpWatch", "AmpWidgets".
        configuration: Build configuration — "Debug" or "Release".
        destination: Build destination string. Examples:
            "platform=iOS Simulator,name=iPhone 16"
            "platform=iOS Simulator,name=iPhone 16,OS=18.6"
            "generic/platform=iOS" (for device builds)

    Returns:
        Dictionary with success status, output, and exit_code.
    """
    try:
        sandbox_backend, repo_dir = _get_sandbox_and_repo_dir()
        cmd = (
            f"cd {repo_dir} && xcodebuild"
            f" -scheme {scheme}"
            f" -configuration {configuration}"
            f" -destination '{destination}'"
            f" -quiet"
            f" 2>&1"
        )
        result = sandbox_backend.execute(cmd)
        return {
            "success": result.exit_code == 0,
            "error": None if result.exit_code == 0 else "Build failed",
            "output": result.output or "",
            "exit_code": result.exit_code,
        }
    except Exception as e:
        logger.exception("xcode_build failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}


def xcode_test(
    scheme: str = "Amp",
    test_target: str | None = None,
    destination: str = "platform=iOS Simulator,name=iPhone 16,OS=18.6",
) -> dict[str, Any]:
    """Run Xcode tests.

    Only run tests directly related to the files you changed.
    Never run the full test suite — CI handles that.

    Args:
        scheme: Xcode scheme. Default "Amp".
            Use "AmpSnapshotTestPlan" for snapshot tests.
        test_target: Specific test target or test class to run.
            Examples:
                "AmpTests/TestClassName"
                "AmpTests/TestClassName/testMethodName"
                "AmpTrophyRoomSnapshotTests"
            If None, runs all tests for the scheme (avoid this).
        destination: Simulator destination.
            Use "platform=iOS Simulator,name=iPhone 16,OS=18.6" for snapshots.

    Returns:
        Dictionary with success status, output, and exit_code.
    """
    try:
        sandbox_backend, repo_dir = _get_sandbox_and_repo_dir()

        only_testing = f" -only-testing '{test_target}'" if test_target else ""
        cmd = (
            f"cd {repo_dir} && xcodebuild test"
            f" -scheme {scheme}"
            f"{only_testing}"
            f" -destination '{destination}'"
            f" 2>&1 | tail -100"
        )
        result = sandbox_backend.execute(cmd)
        return {
            "success": result.exit_code == 0,
            "error": None if result.exit_code == 0 else "Tests failed",
            "output": result.output or "",
            "exit_code": result.exit_code,
        }
    except Exception as e:
        logger.exception("xcode_test failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}


def simulator_control(
    action: str,
    device_name: str = "iPhone 16",
    bundle_id: str = "com.amp.fitness.dev",
    app_path: str | None = None,
) -> dict[str, Any]:
    """Control the iOS Simulator via xcrun simctl.

    Actions:
        boot        - Boot the simulator device.
        shutdown    - Shut down the simulator device.
        list        - List all available simulator devices.
        install     - Install an app (requires app_path).
        launch      - Launch an app by bundle ID.
        terminate   - Terminate a running app by bundle ID.
        screenshot  - Capture a screenshot of the simulator.
        openurl     - Open a URL in the simulator (pass URL as app_path arg).
        erase       - Erase simulator content and settings.

    Args:
        action: Simulator action to perform.
        device_name: Simulator device name. Default "iPhone 16".
        bundle_id: App bundle identifier. Default "com.amp.fitness.dev".
        app_path: Path to .app bundle (for install) or URL (for openurl).

    Returns:
        Dictionary with success status and output.
    """
    try:
        sandbox_backend, repo_dir = _get_sandbox_and_repo_dir()

        if action == "boot":
            cmd = f"xcrun simctl boot '{device_name}' 2>&1 || echo 'Already booted'"
        elif action == "shutdown":
            cmd = f"xcrun simctl shutdown '{device_name}' 2>&1"
        elif action == "list":
            cmd = "xcrun simctl list devices available 2>&1"
        elif action == "install":
            if not app_path:
                return {"success": False, "error": "app_path is required for install action", "output": ""}
            cmd = f"xcrun simctl install '{device_name}' '{app_path}' 2>&1"
        elif action == "launch":
            cmd = f"xcrun simctl launch '{device_name}' {bundle_id} 2>&1"
        elif action == "terminate":
            cmd = f"xcrun simctl terminate '{device_name}' {bundle_id} 2>&1"
        elif action == "screenshot":
            screenshot_path = f"{repo_dir}/simulator_screenshot.png"
            cmd = f"xcrun simctl io '{device_name}' screenshot '{screenshot_path}' 2>&1 && echo 'Screenshot saved to {screenshot_path}'"
        elif action == "openurl":
            if not app_path:
                return {"success": False, "error": "Pass the URL via app_path for openurl action", "output": ""}
            cmd = f"xcrun simctl openurl '{device_name}' '{app_path}' 2>&1"
        elif action == "erase":
            cmd = f"xcrun simctl erase '{device_name}' 2>&1"
        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}. Use boot, shutdown, list, install, launch, terminate, screenshot, openurl, or erase.",
                "output": "",
            }

        result = sandbox_backend.execute(cmd)
        return {
            "success": result.exit_code == 0,
            "error": None if result.exit_code == 0 else f"simctl {action} failed",
            "output": result.output or "",
            "exit_code": result.exit_code,
        }
    except Exception as e:
        logger.exception("simulator_control failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}", "output": ""}
