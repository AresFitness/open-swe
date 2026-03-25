"""Cross-repo PR creation for multi-repo features spanning backend and iOS."""

import asyncio
import logging
from typing import Any

from langgraph.config import get_config

from ..utils.github import (
    create_github_pr,
    get_github_default_branch,
    git_add_all,
    git_checkout_branch,
    git_commit,
    git_config_user,
    git_current_branch,
    git_fetch_origin,
    git_has_uncommitted_changes,
    git_has_unpushed_commits,
    git_push,
)
from ..utils.github_token import get_github_token
from ..utils.sandbox_paths import resolve_repo_dir
from ..utils.sandbox_state import get_sandbox_backend_sync

logger = logging.getLogger(__name__)

REPO_OWNER = "AresFitness"
REPOS = {
    "backend": "RedefinedFitness",
    "ios": "amp-ios",
}


def _commit_and_push_repo(
    sandbox_backend: Any,
    repo_name: str,
    branch_name: str,
    commit_message: str,
    github_token: str,
) -> dict[str, Any]:
    """Commit and push changes in a single repo. Returns status dict."""
    repo_dir = resolve_repo_dir(sandbox_backend, repo_name)

    has_uncommitted = git_has_uncommitted_changes(sandbox_backend, repo_dir)
    git_fetch_origin(sandbox_backend, repo_dir)
    has_unpushed = git_has_unpushed_commits(sandbox_backend, repo_dir)

    if not (has_uncommitted or has_unpushed):
        return {"repo": repo_name, "skipped": True, "reason": "No changes detected"}

    current = git_current_branch(sandbox_backend, repo_dir)
    if current != branch_name:
        if not git_checkout_branch(sandbox_backend, repo_dir, branch_name):
            return {"repo": repo_name, "error": f"Failed to checkout branch {branch_name}"}

    git_config_user(sandbox_backend, repo_dir, "open-swe[bot]", "open-swe@users.noreply.github.com")
    git_add_all(sandbox_backend, repo_dir)

    if has_uncommitted:
        result = git_commit(sandbox_backend, repo_dir, commit_message)
        if result.exit_code != 0:
            return {"repo": repo_name, "error": f"Commit failed: {result.output.strip()}"}

    push_result = git_push(sandbox_backend, repo_dir, branch_name, github_token)
    if push_result.exit_code != 0:
        return {"repo": repo_name, "error": f"Push failed: {push_result.output.strip()}"}

    return {"repo": repo_name, "pushed": True, "branch": branch_name}


def cross_repo_commit_and_open_prs(
    title: str,
    body: str,
    backend_commit_message: str | None = None,
    ios_commit_message: str | None = None,
    linear_ticket: str | None = None,
) -> dict[str, Any]:
    """Commit changes and create linked PRs in both backend and iOS repos.

    Use this tool when you have made changes to BOTH RedefinedFitness and amp-ios
    as part of a cross-repo feature (e.g., adding a GraphQL field + consuming it in iOS).

    This tool:
    1. Commits and pushes changes in RedefinedFitness (if any)
    2. Commits and pushes changes in amp-ios (if any)
    3. Creates a PR in each repo, cross-referencing the other

    If only one repo has changes, it creates a PR only in that repo.

    ## Title Format
    Same as commit_and_open_pr:
        <type>: <short lowercase description> [closes <PROJECT_ID>-<ISSUE_NUMBER>]

    The iOS PR title will be adjusted to match iOS conventions if needed.

    ## Body Format
    Same as commit_and_open_pr with ## Description and ## Test Plan.
    Cross-repo links are added automatically.

    Args:
        title: PR title (e.g., "feat: add workout duration field [closes SW-1234]")
        body: PR description with ## Description and ## Test Plan
        backend_commit_message: Commit message for backend changes. Defaults to title.
        ios_commit_message: Commit message for iOS changes. Defaults to title.
        linear_ticket: Optional Linear ticket ID (e.g., "SW-1234") to link in both PRs.

    Returns:
        Dictionary with results for each repo:
        - backend_pr_url: URL of the backend PR (or None)
        - ios_pr_url: URL of the iOS PR (or None)
        - success: True if at least one PR was created
        - errors: List of any errors encountered
    """
    try:
        config = get_config()
        configurable = config.get("configurable", {})
        thread_id = configurable.get("thread_id")

        if not thread_id:
            return {"success": False, "errors": ["Missing thread_id"], "backend_pr_url": None, "ios_pr_url": None}

        sandbox_backend = get_sandbox_backend_sync(thread_id)
        if not sandbox_backend:
            return {"success": False, "errors": ["No sandbox found"], "backend_pr_url": None, "ios_pr_url": None}

        github_token = get_github_token()
        if not github_token:
            return {"success": False, "errors": ["Missing GitHub token"], "backend_pr_url": None, "ios_pr_url": None}

        branch_name = f"open-swe/{thread_id}"
        errors: list[str] = []
        backend_pr_url = None
        ios_pr_url = None

        # Step 1: Commit and push both repos
        push_results = {}
        for key, repo_name in REPOS.items():
            commit_msg = (backend_commit_message if key == "backend" else ios_commit_message) or title
            result = _commit_and_push_repo(sandbox_backend, repo_name, branch_name, commit_msg, github_token)
            push_results[key] = result
            if "error" in result:
                errors.append(f"{repo_name}: {result['error']}")

        backend_pushed = push_results.get("backend", {}).get("pushed", False)
        ios_pushed = push_results.get("ios", {}).get("pushed", False)

        if not backend_pushed and not ios_pushed:
            skipped = [r.get("reason", "unknown") for r in push_results.values() if r.get("skipped")]
            return {
                "success": False,
                "errors": errors or [f"No changes in either repo. {'; '.join(skipped)}"],
                "backend_pr_url": None,
                "ios_pr_url": None,
            }

        # Step 2: Create PRs with cross-references
        ticket_ref = f"\n\nResolves {linear_ticket}" if linear_ticket else ""

        if backend_pushed:
            backend_body = body + ticket_ref
            if ios_pushed:
                backend_body += f"\n\n**iOS PR**: Created in AresFitness/amp-ios (same branch `{branch_name}`)"

            try:
                base = asyncio.run(get_github_default_branch(REPO_OWNER, REPOS["backend"], github_token))
                url, _num, _existing = asyncio.run(create_github_pr(
                    repo_owner=REPO_OWNER,
                    repo_name=REPOS["backend"],
                    github_token=github_token,
                    title=title,
                    head_branch=branch_name,
                    base_branch=base,
                    body=backend_body,
                ))
                backend_pr_url = url
            except Exception as e:
                errors.append(f"Backend PR creation failed: {e}")

        if ios_pushed:
            ios_body = body + ticket_ref
            if backend_pr_url:
                ios_body += f"\n\n**Backend PR**: {backend_pr_url}"
            elif backend_pushed:
                ios_body += f"\n\n**Backend PR**: Created in AresFitness/RedefinedFitness (same branch `{branch_name}`)"

            try:
                base = asyncio.run(get_github_default_branch(REPO_OWNER, REPOS["ios"], github_token))
                url, _num, _existing = asyncio.run(create_github_pr(
                    repo_owner=REPO_OWNER,
                    repo_name=REPOS["ios"],
                    github_token=github_token,
                    title=title,
                    head_branch=branch_name,
                    base_branch=base,
                    body=ios_body,
                ))
                ios_pr_url = url
            except Exception as e:
                errors.append(f"iOS PR creation failed: {e}")

        # Step 3: Update backend PR body with iOS PR link if both were created
        if backend_pr_url and ios_pr_url:
            try:
                updated_body = body + ticket_ref + f"\n\n**iOS PR**: {ios_pr_url}"
                # Update via GitHub API
                import httpx
                httpx.patch(
                    f"https://api.github.com/repos/{REPO_OWNER}/{REPOS['backend']}/pulls/{backend_pr_url.split('/')[-1]}",
                    headers={"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"},
                    json={"body": updated_body},
                )
            except Exception:
                logger.debug("Failed to update backend PR with iOS link, non-critical")

        return {
            "success": bool(backend_pr_url or ios_pr_url),
            "errors": errors or None,
            "backend_pr_url": backend_pr_url,
            "ios_pr_url": ios_pr_url,
        }
    except Exception as e:
        logger.exception("cross_repo_commit_and_open_prs failed")
        return {"success": False, "errors": [f"{type(e).__name__}: {e}"], "backend_pr_url": None, "ios_pr_url": None}
