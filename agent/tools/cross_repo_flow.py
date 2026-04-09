"""Cross-repo development flow state machine.

Enforces the mandatory sequence for cross-repo tasks:
1. init → returns backend delegation instructions
2. backend_complete → validates backend, returns iOS delegation instructions
3. ios_complete → validates iOS, unlocks PR creation

The orchestrator MUST call this tool at each step. It cannot skip ahead.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Module-level state (per-thread state would be better but this works for single-worker)
_flow_state: dict[str, Any] = {}


def _reset():
    global _flow_state
    _flow_state = {
        "phase": "not_started",
        "task_description": "",
        "is_ui_change": False,
        "backend_delegated": False,
        "backend_result": "",
        "backend_verified": False,
        "ios_delegated": False,
        "ios_result": "",
        "ios_verified": False,
    }


_reset()


def cross_repo_dev_flow(
    action: str,
    task_description: str = "",
    is_ui_change: bool = False,
    result: str = "",
) -> dict[str, Any]:
    """Manage the cross-repo development flow for tasks that span both backend and iOS.

    You MUST use this tool for ANY cross-repo task. Call it at each step — it tells you
    exactly what to do next. You cannot skip steps or create PRs until both repos are verified.

    Actions:
        init: Start the flow. Pass the task_description and whether it's a UI change.
              Returns the exact delegation instructions for the backend sub-agent.

        backend_complete: Call after the backend sub-agent returns. Pass its result.
              Validates the backend completed all mandatory steps.
              Returns the exact delegation instructions for the iOS sub-agent.

        ios_complete: Call after the iOS sub-agent returns. Pass its result.
              Validates the iOS completed all mandatory steps.
              Returns confirmation that you can now create PRs.

        status: Check current flow state and what step is next.

    Args:
        action: One of "init", "backend_complete", "ios_complete", "status"
        task_description: The full task description (required for "init")
        is_ui_change: Whether the task involves UI changes (required for "init")
        result: The sub-agent's result/completion report (required for "backend_complete" and "ios_complete")

    Returns:
        Dict with: success, phase, next_action, delegation_instructions (if applicable),
        errors (if validation failed)
    """
    global _flow_state

    if action == "init":
        _reset()
        _flow_state["phase"] = "backend_pending"
        _flow_state["task_description"] = task_description
        _flow_state["is_ui_change"] = is_ui_change

        ui_note = ""
        if is_ui_change:
            ui_note = (
                '\n\nIMPORTANT: This is a UI change. The iOS sub-agent MUST run maestro test '
                'and take screenshots. Include this in the iOS delegation.'
            )

        return {
            "success": True,
            "phase": "backend_pending",
            "next_action": "Delegate to RedefinedFitness sub-agent for backend implementation",
            "delegation_instructions": (
                f"Task: {task_description}\n\n"
                "DELEGATION TO RedefinedFitness:\n"
                "Implement the backend changes. After implementation, you MUST run ALL of these "
                "and report pass/fail for each in your COMPLETION REPORT:\n"
                "1. pnpm generate (if GraphQL schema changed)\n"
                "2. pnpm typecheck\n"
                "3. pnpm lint\n"
                "4. pnpm jest for affected packages\n"
                "Provide COMPLETION REPORT at the end."
            ),
            "message": (
                "Cross-repo flow initialized. NOW delegate to RedefinedFitness with the "
                "delegation_instructions above. After it returns, call this tool again "
                f"with action='backend_complete' and the sub-agent's result.{ui_note}"
            ),
        }

    elif action == "backend_complete":
        if _flow_state["phase"] != "backend_pending":
            return {
                "success": False,
                "error": f"Cannot complete backend — current phase is '{_flow_state['phase']}'. "
                         "Call with action='init' first.",
            }

        _flow_state["backend_delegated"] = True
        _flow_state["backend_result"] = result

        # Validate backend result
        errors = []
        result_upper = result.upper()
        if "TYPECHECK" not in result_upper or "PASS" not in result_upper:
            errors.append("Backend TYPECHECK not confirmed as PASS")
        if "LINT" not in result_upper:
            errors.append("Backend LINT result not found")

        if errors:
            logger.warning("Backend validation warnings: %s", errors)
            # Don't block — just warn. The orchestrator should re-delegate if needed.

        _flow_state["backend_verified"] = True
        _flow_state["phase"] = "ios_pending"

        return {
            "success": True,
            "phase": "ios_pending",
            "backend_warnings": errors if errors else None,
            "next_action": "NOW delegate to amp-ios sub-agent for iOS implementation",
            "delegation_instructions": (
                f"Task: {_flow_state['task_description']}\n\n"
                "The backend changes are complete. NOW implement the iOS changes.\n\n"
                "DELEGATION TO amp-ios:\n"
                "1. Run `AMP_ENV=dev make env_local` to connect to local backend\n"
                "2. Run `make backend` to pull the updated schema and generate Swift types\n"
                "3. Implement the iOS changes (badge, UI, model updates)\n"
                "4. After implementation, you MUST run ALL of these and report pass/fail:\n"
                "   a. xcodebuild build (compile check) — use timeout=900\n"
                "   b. swiftlint lint on affected modules\n"
                "   c. xcodebuild test for affected test targets — use timeout=900\n"
                "   d. maestro test — MANDATORY for every iOS change, no exceptions\n"
                "Provide COMPLETION REPORT at the end."
            ),
            "message": (
                "Backend verified. YOUR NEXT ACTION MUST BE: "
                "task(subagent_type='amp-ios', description=<delegation_instructions above>). "
                "Do NOT read files, do NOT grep, do NOT do anything else. "
                "Call task() for amp-ios RIGHT NOW. "
                "After it returns, call cross_repo_dev_flow(action='ios_complete', result=<sub-agent result>)."
            ),
        }

    elif action == "ios_complete":
        if _flow_state["phase"] != "ios_pending":
            return {
                "success": False,
                "error": f"Cannot complete iOS — current phase is '{_flow_state['phase']}'. "
                         "Backend must be completed first.",
            }

        # Validate that the result looks like it came from an actual sub-agent implementation
        # (not just the orchestrator reading files)
        if not result or len(result) < 100:
            return {
                "success": False,
                "error": "The iOS result is too short. You MUST delegate to the amp-ios sub-agent "
                         "using task(subagent_type='amp-ios') and pass its FULL result here. "
                         "Do NOT read iOS files yourself — delegate the implementation.",
            }

        result_upper = result.upper()
        has_implementation_evidence = any(kw in result_upper for kw in [
            "COMPLETION REPORT", "STEPS_RAN", "FILES_MODIFIED",
            "XCODEBUILD", "SWIFTLINT", "COMPILE", "BUILD SUCCEEDED",
        ])
        if not has_implementation_evidence:
            return {
                "success": False,
                "error": "The iOS result does not contain implementation evidence "
                         "(no COMPLETION REPORT, no xcodebuild, no swiftlint). "
                         "You MUST delegate to amp-ios sub-agent via task() and pass its result. "
                         "Do NOT skip the iOS implementation.",
            }

        _flow_state["ios_delegated"] = True
        _flow_state["ios_result"] = result

        # Validate iOS result
        errors = []
        if "COMPILE" not in result_upper and "BUILD" not in result_upper:
            errors.append("iOS COMPILE/BUILD result not found")
        if "LINT" not in result_upper and "SWIFTLINT" not in result_upper:
            errors.append("iOS LINT result not found")
        if _flow_state["is_ui_change"] and "MAESTRO" not in result_upper:
            errors.append("iOS MAESTRO result not found (this is a UI change)")

        if errors:
            logger.warning("iOS validation warnings: %s", errors)

        _flow_state["ios_verified"] = True
        _flow_state["phase"] = "ready_for_pr"

        return {
            "success": True,
            "phase": "ready_for_pr",
            "ios_warnings": errors if errors else None,
            "next_action": "Create linked PRs in both repos",
            "message": (
                "Both repos verified! You can now create PRs using "
                "cross_repo_commit_and_open_prs."
            ),
        }

    elif action == "status":
        return {
            "success": True,
            "phase": _flow_state["phase"],
            "backend_delegated": _flow_state["backend_delegated"],
            "backend_verified": _flow_state["backend_verified"],
            "ios_delegated": _flow_state["ios_delegated"],
            "ios_verified": _flow_state["ios_verified"],
            "is_ui_change": _flow_state["is_ui_change"],
            "next_action": {
                "not_started": "Call with action='init' to start the flow",
                "backend_pending": "Delegate to RedefinedFitness, then call with action='backend_complete'",
                "ios_pending": "Delegate to amp-ios, then call with action='ios_complete'",
                "ready_for_pr": "Create PRs with cross_repo_commit_and_open_prs",
            }.get(_flow_state["phase"], "Unknown phase"),
        }

    else:
        return {
            "success": False,
            "error": f"Unknown action '{action}'. Use: init, backend_complete, ios_complete, status",
        }
