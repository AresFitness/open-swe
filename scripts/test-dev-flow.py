"""Test harness for SWE agent dev flow compliance.

Submits a task to the LangGraph server, polls for completion, and audits
the message log against expected dev flow steps.

Usage:
    uv run python scripts/test-dev-flow.py --preset backend-timeout
    uv run python scripts/test-dev-flow.py --preset cross-repo-field
    uv run python scripts/test-dev-flow.py --task "custom task" --type backend-only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langgraph_sdk import get_client

logger = logging.getLogger(__name__)

SANDBOX_ROOT = "/private/tmp/amp-swe-sandbox"

PRESETS = {
    "backend-timeout": {
        "task": (
            "The updateKlaviyo Lambda task is timing out after 60 seconds. "
            "The call to Klaviyo API needs to be limited and retried so it "
            "doesn't fail and cause errors. Add a timeout limit on the Klaviyo "
            "API call and implement retry logic with backoff to handle transient failures."
        ),
        "type": "backend-only",
    },
    "cross-repo-field": {
        "task": (
            "Add a new isCommunityWorkout boolean field to the planned workout model. "
            "This field marks workouts created by the Amp customer community. On the iOS app, "
            "community workouts should display a unique icon/badge on the workout preview "
            "screen to distinguish them from coach-created workouts. "
            "This is a cross-repo feature: backend schema + iOS UI."
        ),
        "type": "cross-repo",
    },
}

# Patterns that indicate the orchestrator is writing code (VIOLATION)
WRITE_PATTERNS = [
    r'\bsed\b.*-i',
    r'\becho\b.*>',
    r'\bcat\b.*<<',
    r'\btee\b\s',
    r'\bwrite_file\b',
    r'\bedit_file\b',
    r'\bpython3?\b.*-c.*open\(',
    r'\bmkdir\b',
    r'\btouch\b\s',
    r'\brm\b\s',
]

# Read-only commands that are OK for the orchestrator
READ_OK_PATTERNS = [
    r'(grep|rg|find|ls|cat|head|tail|wc)\b',
    r'git\s+(log|diff|status|branch|show|ls-tree|remote|rev-parse|fetch)',
    r'^echo\s+"',  # echo for display only (no redirect)
    r'^which\b',
    r'^backend_local\b',
    r'^cd\s+.*&&\s*(grep|rg|find|ls|cat|head|tail|git)',  # cd + read-only
    r'^gh\s+',  # GitHub CLI
]


@dataclass
class CheckResult:
    name: str
    passed: bool | None  # None = N/A
    details: str


@dataclass
class AuditReport:
    task: str
    task_type: str
    thread_id: str
    run_id: str
    status: str
    duration_seconds: float
    checks: list[CheckResult] = field(default_factory=list)
    delegations: list[dict] = field(default_factory=list)
    total_messages: int = 0
    total_tool_calls: int = 0

    @property
    def overall_pass(self) -> bool:
        return all(c.passed is True or c.passed is None for c in self.checks)


class TaskRunner:
    def __init__(self, langgraph_url: str):
        self.url = langgraph_url
        self.client = get_client(url=langgraph_url)

    async def create_thread(self) -> str:
        thread = await self.client.threads.create(metadata={})
        return thread["thread_id"]

    async def submit_task(self, thread_id: str, task: str) -> str:
        run = await self.client.runs.create(
            thread_id=thread_id,
            assistant_id="agent",
            input={"messages": [{"role": "user", "content": task}]},
            config={
                "configurable": {
                    "repo": {"owner": "AresFitness", "name": "RedefinedFitness"},
                    "source": "github",
                }
            },
        )
        return run["run_id"]

    async def poll_completion(
        self, thread_id: str, run_id: str, timeout: int = 2400, poll_interval: int = 30
    ) -> str:
        elapsed = 0
        while elapsed < timeout:
            run = await self.client.runs.get(thread_id=thread_id, run_id=run_id)
            status = run.get("status", "unknown")
            if status in ("success", "error", "interrupted"):
                return status
            logger.info("Run %s status: %s (elapsed: %ds)", run_id[:8], status, elapsed)
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        return "timeout"

    async def get_messages(self, thread_id: str) -> list[dict]:
        state = await self.client.threads.get_state(thread_id)
        values = state.get("values", {})
        return values.get("messages", [])

    async def close(self):
        await self.client.aclose()


class ComplianceAuditor:
    def __init__(self, messages: list[dict], task_type: str):
        self.messages = messages
        self.task_type = task_type
        self._tool_calls = self._extract_tool_calls()
        self._delegations = self._extract_delegations()

    def _extract_tool_calls(self) -> list[dict]:
        calls = []
        for i, m in enumerate(self.messages):
            content = m.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        calls.append({
                            "msg_idx": i,
                            "name": block["name"],
                            "input": block.get("input", {}),
                        })
        return calls

    def _extract_delegations(self) -> list[dict]:
        delegations = []
        for tc in self._tool_calls:
            if tc["name"] == "task":
                delegations.append({
                    "subagent": tc["input"].get("subagent_type", "?"),
                    "description": tc["input"].get("description", "")[:300],
                    "msg_idx": tc["msg_idx"],
                })
        return delegations

    def _get_subagent_results(self) -> list[str]:
        results = []
        for i, m in enumerate(self.messages):
            if m.get("type") == "tool" and m.get("name") == "task":
                content = m.get("content", "")
                if isinstance(content, str):
                    results.append(content)
        return results

    def check_plan_before_build(self) -> CheckResult:
        plan_idx = None
        first_impl_task_idx = None

        for tc in self._tool_calls:
            if tc["name"] == "update_dashboard":
                phase = tc["input"].get("phase", "")
                if phase == "plan" and plan_idx is None:
                    plan_idx = tc["msg_idx"]
            if tc["name"] == "task":
                desc = tc["input"].get("description", "").lower()
                # Research delegations are OK before plan
                if any(kw in desc for kw in ["research", "find", "search", "read", "understand"]):
                    continue
                if first_impl_task_idx is None:
                    first_impl_task_idx = tc["msg_idx"]

        if plan_idx is None:
            return CheckResult("plan_before_build", False, "No plan phase found")
        if first_impl_task_idx is None:
            return CheckResult("plan_before_build", True, "Plan at msg #{}, no impl delegation found".format(plan_idx))
        if plan_idx < first_impl_task_idx:
            return CheckResult("plan_before_build", True, f"Plan at msg #{plan_idx}, first impl at #{first_impl_task_idx}")
        return CheckResult("plan_before_build", False, f"Impl at #{first_impl_task_idx} BEFORE plan at #{plan_idx}")

    def check_orchestrator_no_write(self) -> CheckResult:
        violations = []
        for tc in self._tool_calls:
            if tc["name"] == "execute":
                cmd = tc["input"].get("command", "").strip()
                # Strip leading cd ... && to get the actual command
                actual_cmd = re.sub(r'^cd\s+\S+\s*&&\s*', '', cmd)
                # Check if the actual command is read-only
                is_read = any(re.search(p, actual_cmd) for p in READ_OK_PATTERNS)
                if is_read:
                    continue
                # Check if it's a write operation
                is_write = any(re.search(p, cmd) for p in WRITE_PATTERNS)
                if is_write:
                    violations.append(f"msg #{tc['msg_idx']}: {cmd[:100]}")
            elif tc["name"] in ("write_file", "edit_file"):
                violations.append(f"msg #{tc['msg_idx']}: {tc['name']}")

        if not violations:
            return CheckResult("orchestrator_no_write", True, f"{len(self._tool_calls)} tool calls, 0 write violations")
        return CheckResult("orchestrator_no_write", False, f"{len(violations)} violations: {'; '.join(violations[:3])}")

    def _check_step_in_results(self, step_name: str, patterns: list[str], aliases: list[str] | None = None) -> CheckResult:
        results = self._get_subagent_results()
        all_text = " ".join(results).lower()

        # Names to search for in COMPLETION REPORT
        search_names = [step_name]
        if aliases:
            search_names.extend(aliases)

        # First try: look for COMPLETION REPORT format (iterate REVERSE — prefer last/implementation result)
        for result in reversed(results):
            if "COMPLETION REPORT" in result or "STEPS_RAN" in result:
                for line in result.split("\n"):
                    for name in search_names:
                        if name.upper() in line.upper():
                            if "PASS" in line.upper():
                                return CheckResult(step_name, True, f"COMPLETION REPORT: {line.strip()[:100]}")
                            elif "FAIL" in line.upper():
                                return CheckResult(step_name, False, f"COMPLETION REPORT: {line.strip()[:100]}")
                            elif "SKIPPED" in line.upper() or "N_A" in line.upper() or "N/A" in line.upper():
                                return CheckResult(step_name, None, f"COMPLETION REPORT: {line.strip()[:100]}")

        # Fallback: look for command patterns in sub-agent results
        for pattern in patterns:
            if pattern.lower() in all_text:
                # Check for pass/success indicators near the pattern
                for result in results:
                    if pattern.lower() in result.lower():
                        if any(w in result.lower() for w in ["pass", "succeed", "✅", "0 error", "0 fail"]):
                            return CheckResult(step_name, True, f"Found '{pattern}' with success indicators")
                        elif any(w in result.lower() for w in ["fail", "error", "❌"]):
                            return CheckResult(step_name, False, f"Found '{pattern}' with failure indicators")
                return CheckResult(step_name, True, f"Found '{pattern}' in sub-agent results (assumed pass)")

        return CheckResult(step_name, False, f"NOT FOUND — none of {patterns} appeared in sub-agent results")

    def check_backend_typecheck(self) -> CheckResult:
        if self.task_type == "ios-only":
            return CheckResult("backend_typecheck", None, "N/A (iOS-only task)")
        return self._check_step_in_results("typecheck", ["pnpm typecheck", "pnpm tsc", "tsc --noEmit"])

    def check_backend_lint(self) -> CheckResult:
        if self.task_type == "ios-only":
            return CheckResult("backend_lint", None, "N/A (iOS-only task)")
        return self._check_step_in_results("lint", ["pnpm lint", "pnpm eslint", "eslint"])

    def check_backend_test(self) -> CheckResult:
        if self.task_type == "ios-only":
            return CheckResult("backend_test", None, "N/A (iOS-only task)")
        return self._check_step_in_results("unit_tests", ["pnpm jest", "pnpm test", "jest --testPathPattern"], aliases=["test", "implement_tests"])

    def check_ios_compile(self) -> CheckResult:
        if self.task_type == "backend-only":
            return CheckResult("ios_compile", None, "N/A (backend-only task)")
        return self._check_step_in_results("compile", ["xcodebuild", "build succeeded"])

    def check_ios_lint(self) -> CheckResult:
        if self.task_type == "backend-only":
            return CheckResult("ios_lint", None, "N/A (backend-only task)")
        return self._check_step_in_results("ios_lint", ["swiftlint"])

    def check_ios_test(self) -> CheckResult:
        if self.task_type == "backend-only":
            return CheckResult("ios_test", None, "N/A (backend-only task)")
        return self._check_step_in_results("ios_test", ["xcodebuild test", "AmpTests", "AmpSnapshotTestPlan"])

    def check_ios_maestro(self) -> CheckResult:
        if self.task_type == "backend-only":
            return CheckResult("ios_maestro", None, "N/A (backend-only task)")
        return self._check_step_in_results("maestro", ["maestro test", "maestro"])

    def check_pr_created(self) -> CheckResult:
        for m in self.messages:
            if m.get("type") == "tool":
                name = m.get("name", "")
                if name in ("commit_and_open_pr", "cross_repo_commit_and_open_prs"):
                    content = m.get("content", "")
                    if isinstance(content, str):
                        try:
                            data = json.loads(content)
                            if data.get("success"):
                                pr_url = data.get("pr_url") or data.get("backend_pr_url") or ""
                                return CheckResult("pr_created", True, pr_url)
                        except (json.JSONDecodeError, TypeError):
                            if "success" in content.lower():
                                return CheckResult("pr_created", True, "PR created (parsed from text)")
        return CheckResult("pr_created", False, "No successful PR creation found")

    def run_all_checks(self) -> list[CheckResult]:
        return [
            self.check_plan_before_build(),
            self.check_orchestrator_no_write(),
            self.check_backend_typecheck(),
            self.check_backend_lint(),
            self.check_backend_test(),
            self.check_ios_compile(),
            self.check_ios_lint(),
            self.check_ios_test(),
            self.check_ios_maestro(),
            self.check_pr_created(),
        ]


def print_report(report: AuditReport):
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    GRAY = "\033[90m"

    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}SWE Agent Dev Flow Compliance Report{RESET}")
    print(f"{'=' * 70}")
    print(f"Task: {report.task[:100]}...")
    print(f"Type: {report.task_type}")
    print(f"Thread: {report.thread_id}")
    print(f"Status: {report.status}")
    print(f"Duration: {report.duration_seconds:.0f}s ({report.duration_seconds / 60:.1f}m)")
    print(f"Messages: {report.total_messages} | Tool calls: {report.total_tool_calls}")

    print(f"\n{BOLD}Delegations ({len(report.delegations)}):{RESET}")
    for i, d in enumerate(report.delegations):
        print(f"  {i + 1}. → {d['subagent']}: {d['description'][:80]}...")

    print(f"\n{BOLD}Compliance Checks:{RESET}")
    for check in report.checks:
        if check.passed is True:
            icon = f"{GREEN}PASS{RESET}"
        elif check.passed is False:
            icon = f"{RED}FAIL{RESET}"
        else:
            icon = f"{GRAY}N/A {RESET}"
        print(f"  {icon}  {check.name:25s}  {check.details[:80]}")

    overall = report.overall_pass
    color = GREEN if overall else RED
    print(f"\n{BOLD}Overall: {color}{'PASS' if overall else 'FAIL'}{RESET}")
    print(f"{'=' * 70}\n")


def save_report(report: AuditReport, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    # JSON report
    json_path = output_dir / f"{ts}_report.json"
    json_data = {
        "task": report.task,
        "task_type": report.task_type,
        "thread_id": report.thread_id,
        "run_id": report.run_id,
        "status": report.status,
        "duration_seconds": report.duration_seconds,
        "total_messages": report.total_messages,
        "total_tool_calls": report.total_tool_calls,
        "delegations": report.delegations,
        "checks": {
            c.name: {"pass": c.passed, "details": c.details} for c in report.checks
        },
        "overall_pass": report.overall_pass,
    }
    json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
    logger.info("Report saved to %s", json_path)

    return json_path


def save_messages(messages: list[dict], output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    msg_path = output_dir / f"{ts}_messages.jsonl"
    with open(msg_path, "w") as f:
        for m in messages:
            f.write(json.dumps(m, default=str) + "\n")
    logger.info("Messages saved to %s", msg_path)
    return msg_path


def reset_sandbox_repos():
    logger.info("Resetting sandbox repos to clean state...")
    repos = {
        "RedefinedFitness": "feat/swe-dev-flow",
        "amp-ios": "feat/swe-dev-flow",
    }
    for repo, branch in repos.items():
        repo_path = os.path.join(SANDBOX_ROOT, repo)
        if os.path.isdir(repo_path):
            subprocess.run(
                ["git", "fetch", "origin", branch],
                cwd=repo_path, capture_output=True,
            )
            subprocess.run(
                ["git", "checkout", branch],
                cwd=repo_path, capture_output=True,
            )
            subprocess.run(
                ["git", "reset", "--hard", f"origin/{branch}"],
                cwd=repo_path, capture_output=True,
            )
            subprocess.run(
                ["git", "clean", "-fd"],
                cwd=repo_path, capture_output=True,
            )
            logger.info("Reset %s to origin/%s (clean)", repo, branch)
        else:
            logger.warning("Repo %s not found at %s", repo, repo_path)


async def run_test(
    task: str,
    task_type: str,
    langgraph_url: str,
    output_dir: Path,
    timeout: int,
    reset_repos: bool,
) -> AuditReport:
    if reset_repos:
        reset_sandbox_repos()

    runner = TaskRunner(langgraph_url)
    start_time = time.time()

    try:
        # Submit task
        thread_id = await runner.create_thread()
        logger.info("Created thread: %s", thread_id)

        run_id = await runner.submit_task(thread_id, task)
        logger.info("Submitted run: %s", run_id)

        # Poll for completion
        status = await runner.poll_completion(thread_id, run_id, timeout=timeout)
        duration = time.time() - start_time
        logger.info("Run completed with status: %s (%.0fs)", status, duration)

        # Get messages
        messages = await runner.get_messages(thread_id)
        logger.info("Retrieved %d messages", len(messages))

        # Save raw messages
        save_messages(messages, output_dir)

        # Audit
        auditor = ComplianceAuditor(messages, task_type)
        checks = auditor.run_all_checks()

        # Count tool calls
        total_tool_calls = sum(
            1 for m in messages
            if isinstance(m.get("content"), list)
            for b in m["content"]
            if isinstance(b, dict) and b.get("type") == "tool_use"
        )

        report = AuditReport(
            task=task,
            task_type=task_type,
            thread_id=thread_id,
            run_id=run_id,
            status=status,
            duration_seconds=duration,
            checks=checks,
            delegations=auditor._delegations,
            total_messages=len(messages),
            total_tool_calls=total_tool_calls,
        )

        # Print and save
        print_report(report)
        save_report(report, output_dir)

        return report

    finally:
        await runner.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test SWE agent dev flow compliance")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preset", choices=list(PRESETS.keys()), help="Use a predefined test task")
    group.add_argument("--task", help="Custom task description")

    parser.add_argument("--type", choices=["backend-only", "cross-repo", "ios-only"],
                       help="Task type (required with --task)")
    parser.add_argument("--langgraph-url", default="http://localhost:2024")
    parser.add_argument("--output-dir", default="test-results", help="Output directory for reports")
    parser.add_argument("--timeout", type=int, default=2400, help="Max seconds to wait (default: 2400)")
    parser.add_argument("--reset-repos", action="store_true", help="Reset sandbox repos before running")
    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    args = parse_args()

    if args.preset:
        preset = PRESETS[args.preset]
        task = preset["task"]
        task_type = preset["type"]
    else:
        if not args.type:
            print("ERROR: --type is required when using --task")
            return
        task = args.task
        task_type = args.type

    asyncio.run(
        run_test(
            task=task,
            task_type=task_type,
            langgraph_url=args.langgraph_url,
            output_dir=Path(args.output_dir),
            timeout=args.timeout,
            reset_repos=args.reset_repos,
        )
    )


if __name__ == "__main__":
    main()
