"""Dashboard progress reporting tool for the kanban UI."""

import logging
from typing import Any

from langgraph.config import get_config
from langgraph.store.base import BaseStore

logger = logging.getLogger(__name__)

VALID_PHASES = ("research", "plan", "build", "test", "iterate", "pr", "review")


def update_dashboard(
    phase: str,
    summary: str = "",
    plan: str = "",
    test_results: str = "",
    screenshots: list[str] | None = None,
    pr_urls: list[str] | None = None,
    title: str = "",
    iteration_count: int | None = None,
) -> dict[str, Any]:
    """Update the dashboard with the current task phase and metadata.

    You MUST call this tool at each phase transition to keep the dashboard in sync.
    The dashboard is a kanban board that shows your progress through development phases.

    Phase transitions:
    1. research → After gathering context from the codebases
    2. plan → After drafting the implementation plan (IMPORTANT: you must STOP after
       this and wait for user approval before proceeding to build)
    3. build → When starting implementation
    4. test → When running tests, typechecks, builds
    5. iterate → When fixing failures and going back to build+test
    6. pr → After creating pull requests
    7. review → When addressing PR review comments

    Args:
        phase: Current phase — one of: research, plan, build, test, iterate, pr, review
        summary: Description of what was done/found in this phase.
            For research: key findings about the codebase.
            For plan: brief overview of the approach.
            For test: test results summary.
            For iterate: what failed and what's being fixed.
        plan: Full implementation plan in markdown (for plan phase).
            Include the test plan: which unit/integration/snapshot tests will be added,
            and which manual E2E checks the agent will perform.
        test_results: Test output or build results (for test phase).
        screenshots: List of screenshot file paths captured during testing.
        pr_urls: List of PR URLs (for pr phase).
        title: Task title (set once during research phase, used as the card title on the board).
        iteration_count: Number of build-test iterations so far (for iterate phase).

    Returns:
        Dictionary with success status.
    """
    if phase not in VALID_PHASES:
        return {
            "success": False,
            "error": f"Invalid phase '{phase}'. Must be one of: {', '.join(VALID_PHASES)}",
        }

    try:
        config = get_config()
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return {"success": False, "error": "Missing thread_id"}

        store: BaseStore | None = config.get("store")
        if store is None:
            # Try to get store from langgraph context
            try:
                from langgraph.store.base import get_store
                store = get_store()
            except Exception:
                pass

        if store is None:
            logger.warning("No store available, dashboard update skipped")
            return {"success": True, "warning": "No store available, update logged but not persisted"}

        namespace = ("dashboard", thread_id)
        key = "task"

        # Get existing data
        existing_items = store.search(namespace)
        existing_value: dict[str, Any] = {}
        for item in existing_items:
            if item.key == key:
                existing_value = item.value or {}
                break

        # Build update
        update: dict[str, Any] = {"phase": phase}
        if summary:
            update["summary"] = summary
            # Accumulate summaries per phase
            phase_summaries = existing_value.get("phase_summaries", {})
            phase_summaries[phase] = summary
            update["phase_summaries"] = phase_summaries
        if plan:
            update["plan"] = plan
        if test_results:
            update["test_results"] = test_results
        if screenshots:
            existing_screenshots = existing_value.get("screenshots", [])
            update["screenshots"] = existing_screenshots + screenshots
        if pr_urls:
            update["pr_urls"] = pr_urls
        if title:
            update["title"] = title
        if iteration_count is not None:
            update["iteration_count"] = iteration_count

        merged = {**existing_value, **update}
        store.put(namespace, key, merged)

        logger.info("Dashboard updated: phase=%s thread=%s", phase, thread_id)
        return {"success": True, "phase": phase}

    except Exception as e:
        logger.exception("update_dashboard failed")
        return {"success": False, "error": f"{type(e).__name__}: {e}"}
