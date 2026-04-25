#!/usr/bin/env python3
import argparse
import copy
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SKILL_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = SKILL_ROOT / ".loop-state.json"
COPILOT_LOGINS = {"copilot", "copilot-pull-request-reviewer[bot]", "copilot-pull-request-reviewer"}
COPILOT_REVIEWER_STATE_AWAITING = "awaiting"
COPILOT_REVIEWER_STATE_NOT_AWAITING = "not_awaiting"
DEFAULT_GH_COMMAND_TIMEOUT_SECONDS = 60
DEFAULT_GIT_COMMAND_TIMEOUT_SECONDS = 30
STATE_VERSION = 2
ROLE_SEQUENCE = ["triage", "implementation", "self_review"]
FINALIZE_SUCCESS = "success"
FINALIZE_NEEDS_LOOP = "needs_loop"
FINALIZE_TIMEOUT = "timeout"
FINALIZE_DRIFTED = "drifted"
FINALIZE_CAP_EXCEEDED = "cap_exceeded"


class LoopError(Exception):
    pass


def run_command(cmd: List[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            stdin=subprocess.DEVNULL,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise LoopError(f"Command timed out after {timeout_seconds} seconds: {' '.join(cmd)}") from exc
    except OSError as exc:
        raise LoopError(f"Failed to execute command: {' '.join(cmd)}\n{exc}") from exc


def format_failed_command(cmd: List[str], result: subprocess.CompletedProcess[str]) -> str:
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    return (
        f"Command failed: {' '.join(cmd)}\n"
        f"stdout:\n{stdout if stdout else '<empty>'}\n"
        f"stderr:\n{stderr if stderr else '<empty>'}"
    )


def run_gh_json(args: List[str]) -> Any:
    cmd = ["gh", *args]
    result = run_command(cmd, timeout_seconds=DEFAULT_GH_COMMAND_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise LoopError(format_failed_command(cmd, result))
    stdout = result.stdout.strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise LoopError(f"Command returned non-JSON output: {' '.join(cmd)}\n{stdout}") from exc


def run_gh(args: List[str]) -> str:
    cmd = ["gh", *args]
    result = run_command(cmd, timeout_seconds=DEFAULT_GH_COMMAND_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise LoopError(format_failed_command(cmd, result))
    return result.stdout.strip()


def run_gh_allow_error(args: List[str]) -> subprocess.CompletedProcess[str]:
    cmd = ["gh", *args]
    return run_command(cmd, timeout_seconds=DEFAULT_GH_COMMAND_TIMEOUT_SECONDS)


def run_git(args: List[str]) -> str:
    cmd = ["git", *args]
    result = run_command(cmd, timeout_seconds=DEFAULT_GIT_COMMAND_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise LoopError(format_failed_command(cmd, result))
    return result.stdout.strip()


def utc_now_minus_seconds_iso(seconds: int) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=seconds)).replace(microsecond=0).isoformat()


def parse_iso(ts: str) -> dt.datetime:
    normalized = ts.replace("Z", "+00:00")
    return dt.datetime.fromisoformat(normalized)


def is_copilot_reviewer(reviewer: Dict[str, Any]) -> bool:
    login = (reviewer.get("login") or "").lower()
    slug = (reviewer.get("slug") or "").lower()
    # Keep request matching permissive: review requests can surface as user/bot/team.
    return login in COPILOT_LOGINS or slug == "copilot"


def ensure_state_dir() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def save_state(state: Dict[str, Any]) -> None:
    tmp_path = STATE_PATH.with_suffix(f"{STATE_PATH.suffix}.tmp")
    write_exc: Optional[Exception] = None
    try:
        ensure_state_dir()
        tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
        tmp_path.replace(STATE_PATH)
    except OSError as exc:
        write_exc = exc
        raise LoopError(f"Failed to save state file {STATE_PATH} via temporary file {tmp_path}: {exc}") from exc
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        except OSError as exc:
            if write_exc is None:
                raise LoopError(
                    f"Failed to clean up temporary state file {tmp_path} for {STATE_PATH}: {exc}"
                ) from exc


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def default_state_extensions() -> Dict[str, Any]:
    return {
        "state_version": STATE_VERSION,
        "migration_applied_at": None,
        "migration_notes": [],
        "current_iteration": 1,
        "max_iterations": 10,
        "roles_completed": [],
        "role_agent_ids": {},
        "iteration_artifacts": {},
        "last_fix_sha": None,
        "post_fix_review_requested_at": None,
        "post_fix_review_completed_at": None,
        "post_fix_review_sha": None,
        "unresolved_after_post_fix_review": None,
        "invariant_failures": [],
    }


def ensure_iteration_bucket(state: Dict[str, Any], iteration: int) -> Dict[str, Any]:
    artifacts = state.setdefault("iteration_artifacts", {})
    key = str(iteration)
    bucket = artifacts.get(key)
    if not isinstance(bucket, dict):
        bucket = {"roles_completed": [], "role_agent_ids": {}, "artifacts": {}}
        artifacts[key] = bucket
    bucket.setdefault("roles_completed", [])
    bucket.setdefault("role_agent_ids", {})
    bucket.setdefault("artifacts", {})
    return bucket


def migrate_state(state: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(state, dict):
        raise LoopError(f"State file {STATE_PATH} must contain a JSON object.")
    migrated = copy.deepcopy(state)
    defaults = default_state_extensions()
    notes: List[str] = []
    for key, default in defaults.items():
        if key not in migrated:
            migrated[key] = copy.deepcopy(default)
            notes.append(f"defaulted:{key}")
    if not isinstance(migrated.get("max_iterations"), int) or migrated["max_iterations"] <= 0:
        migrated["max_iterations"] = 10
        notes.append("recovered:max_iterations")
    loop_count = migrated.get("loop_count")
    if not isinstance(loop_count, int) or loop_count < 0:
        loop_count = 0
        migrated["loop_count"] = 0
        notes.append("recovered:loop_count")
    if not isinstance(migrated.get("current_iteration"), int) or migrated["current_iteration"] <= 0:
        migrated["current_iteration"] = loop_count + 1
        notes.append("recovered:current_iteration_from_loop_count")
    if not isinstance(migrated.get("iteration_artifacts"), dict):
        raise LoopError(f"State file {STATE_PATH} has fatal shape error: iteration_artifacts must be an object.")

    bucket = ensure_iteration_bucket(migrated, int(migrated["current_iteration"]))
    if migrated.get("roles_completed"):
        bucket["roles_completed"] = list(migrated.get("roles_completed", []))
    if migrated.get("role_agent_ids"):
        bucket["role_agent_ids"] = dict(migrated.get("role_agent_ids", {}))
    if not migrated.get("roles_completed"):
        migrated["roles_completed"] = list(bucket.get("roles_completed", []))
    if not migrated.get("role_agent_ids"):
        migrated["role_agent_ids"] = dict(bucket.get("role_agent_ids", {}))

    prev_version = migrated.get("state_version")
    migrated["state_version"] = STATE_VERSION
    if prev_version != STATE_VERSION or notes:
        migrated["migration_applied_at"] = iso_now()
        history = list(migrated.get("migration_notes", []))
        history.extend(notes)
        migrated["migration_notes"] = history
    return migrated


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        raise LoopError(f"State file not found: {STATE_PATH}")
    try:
        raw = json.loads(STATE_PATH.read_text())
    except (OSError, UnicodeDecodeError) as exc:
        raise LoopError(f"Failed to read state file {STATE_PATH}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LoopError(f"Failed to parse state file {STATE_PATH}: {exc}") from exc
    migrated = migrate_state(raw)
    if migrated != raw:
        save_state(migrated)
    return migrated


def get_current_bucket(state: Dict[str, Any]) -> Dict[str, Any]:
    return ensure_iteration_bucket(state, int(state.get("current_iteration", 1)))


def sync_current_iteration_role_views(state: Dict[str, Any]) -> None:
    bucket = get_current_bucket(state)
    state["roles_completed"] = list(bucket.get("roles_completed", []))
    state["role_agent_ids"] = dict(bucket.get("role_agent_ids", {}))


def ensure_within_iteration_cap(state: Dict[str, Any]) -> None:
    current = int(state.get("current_iteration", 1))
    max_iterations = int(state.get("max_iterations", 10))
    if current > max_iterations:
        raise LoopError(f"{FINALIZE_CAP_EXCEEDED}: current_iteration={current} exceeds max_iterations={max_iterations}")


def state_has_implementation_push(state: Dict[str, Any]) -> bool:
    impl = get_current_bucket(state).get("artifacts", {}).get("implementation")
    if not isinstance(impl, dict):
        return False
    return bool(impl.get("push_completed")) and bool(impl.get("pushed_sha"))


def require_implementation_push(state: Dict[str, Any]) -> None:
    if not state_has_implementation_push(state):
        raise LoopError(
            "Implementation artifact is missing push proof for the active iteration. "
            "Record implementation with push_completed=true and pushed_sha before GitHub mutation steps."
        )


def clear_copilot_cycle_state(state: Dict[str, Any]) -> None:
    state["copilot_requested_at"] = None
    state["copilot_review_baseline_at"] = None
    state["last_seen_review_event_at"] = None
    state["post_fix_review_requested_at"] = None
    state["post_fix_review_completed_at"] = None
    state["post_fix_review_sha"] = None
    state["unresolved_after_post_fix_review"] = None


def advance_iteration_or_fail(state: Dict[str, Any]) -> None:
    next_iteration = int(state.get("current_iteration", 1)) + 1
    max_iterations = int(state.get("max_iterations", 10))
    if next_iteration > max_iterations:
        state["current_iteration"] = next_iteration
        state["loop_count"] = next_iteration - 1
        state["escalation_reason"] = f"Loop limit reached ({max_iterations})"
        clear_copilot_cycle_state(state)
        state.setdefault("invariant_failures", []).append(FINALIZE_CAP_EXCEEDED)
        if state.get("run_id"):
            save_state(state)
        raise LoopError(FINALIZE_CAP_EXCEEDED)
    state["current_iteration"] = next_iteration
    state["loop_count"] = next_iteration - 1
    clear_copilot_cycle_state(state)
    ensure_iteration_bucket(state, next_iteration)
    sync_current_iteration_role_views(state)


def record_role_artifact(
    state: Dict[str, Any],
    role: str,
    agent_id: str,
    artifact: Dict[str, Any],
    replace: bool,
    replace_reason: Optional[str],
) -> Dict[str, Any]:
    if role not in ROLE_SEQUENCE:
        raise LoopError(f"Unknown role: {role}")
    ensure_within_iteration_cap(state)
    bucket = get_current_bucket(state)
    artifacts = dict(bucket.get("artifacts", {}))
    roles_completed = list(bucket.get("roles_completed", []))
    role_agent_ids = dict(bucket.get("role_agent_ids", {}))
    expected_role = ROLE_SEQUENCE[len(roles_completed)] if len(roles_completed) < len(ROLE_SEQUENCE) else None
    if role not in roles_completed and expected_role != role:
        raise LoopError(f"Role order violation: expected {expected_role}, got {role}")
    if role in artifacts and not replace:
        raise LoopError(
            f"Artifact already recorded for role={role} iteration={state['current_iteration']}. "
            "Use --replace with --replace-reason."
        )
    if role in artifacts and replace and not replace_reason:
        raise LoopError("--replace requires --replace-reason for auditability.")
    for existing_role, existing_agent in role_agent_ids.items():
        if existing_role != role and existing_agent == agent_id:
            raise LoopError("Distinct-agent invariant failed for active iteration.")

    payload = dict(artifact)
    payload["recorded_at"] = iso_now()
    payload["agent_id"] = agent_id
    if replace:
        payload["replaced"] = True
        payload["replace_reason"] = replace_reason
    artifacts[role] = payload
    role_agent_ids[role] = agent_id
    if role not in roles_completed:
        roles_completed.append(role)

    bucket["artifacts"] = artifacts
    bucket["role_agent_ids"] = role_agent_ids
    bucket["roles_completed"] = roles_completed
    sync_current_iteration_role_views(state)
    return payload


def collect_invariant_failures(state: Dict[str, Any]) -> List[str]:
    failures: List[str] = []
    ensure_iteration_bucket(state, int(state.get("current_iteration", 1)))
    current = int(state.get("current_iteration", 1))
    max_iterations = int(state.get("max_iterations", 10))
    if current > max_iterations:
        failures.append(FINALIZE_CAP_EXCEEDED)
    bucket = get_current_bucket(state)
    artifacts = bucket.get("artifacts", {})
    roles_completed = bucket.get("roles_completed", [])
    role_agent_ids = bucket.get("role_agent_ids", {})
    if roles_completed != ROLE_SEQUENCE:
        failures.append("role_order_incomplete_or_invalid")
    for role in ROLE_SEQUENCE:
        if role not in artifacts:
            failures.append(f"missing_role:{role}")
    ids = [role_agent_ids.get(role) for role in ROLE_SEQUENCE if role_agent_ids.get(role)]
    if len(ids) != len(set(ids)):
        failures.append("duplicate_role_agent_id")
    impl = artifacts.get("implementation") or {}
    if not (impl.get("push_completed") and impl.get("pushed_sha")):
        failures.append("implementation_push_missing")
    return failures


def require_state_keys(state: Dict[str, Any], required_keys: List[str]) -> None:
    missing = [key for key in required_keys if key not in state]
    if missing:
        raise LoopError(
            f"State file {STATE_PATH} is missing required keys: {', '.join(missing)}. Run init to recreate state."
        )


def ensure_changes_pushed() -> None:
    status_porcelain = run_git(["status", "--porcelain"])
    if status_porcelain:
        raise LoopError(
            "Commit barrier failed: working tree is not clean. Commit and push all fix changes before GitHub actions."
        )

    try:
        upstream = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    except LoopError as exc:
        raise LoopError(
            "Commit barrier failed: current branch has no upstream. Push with -u before continuing."
        ) from exc

    ahead_behind = run_git(["rev-list", "--left-right", "--count", f"{upstream}...HEAD"])
    parts = ahead_behind.split()
    if len(parts) != 2:
        raise LoopError(f"Commit barrier failed: unexpected ahead/behind output: {ahead_behind}")

    try:
        behind_count = int(parts[0])
        ahead_count = int(parts[1])
    except ValueError as exc:
        raise LoopError(f"Commit barrier failed: unexpected ahead/behind output: {ahead_behind}") from exc
    if ahead_count > 0:
        raise LoopError(
            f"Commit barrier failed: local branch is ahead by {ahead_count} commit(s). Push before GitHub actions."
        )
    if behind_count > 0:
        raise LoopError(
            f"Commit barrier failed: local branch is behind upstream by {behind_count} commit(s). Sync branch first."
        )


def ensure_on_pr_branch(state: Dict[str, Any]) -> None:
    expected_branch = state.get("pr_branch")
    current_branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if expected_branch and current_branch != expected_branch:
        raise LoopError(
            f"Commit barrier failed: current branch is {current_branch}, expected {expected_branch} for this PR state."
        )


def graphql(query: str, fields: Dict[str, Any]) -> Any:
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in fields.items():
        if value is None:
            continue
        args.extend(["-F", f"{key}={value}"])
    payload = run_gh_json(args)
    if not isinstance(payload, dict):
        raise LoopError(f"GraphQL returned an unexpected response type: {type(payload).__name__}")

    errors = payload.get("errors")
    if errors:
        if isinstance(errors, list):
            messages = []
            for error in errors:
                if isinstance(error, dict):
                    message = error.get("message")
                    messages.append(message if message else json.dumps(error, sort_keys=True))
                else:
                    messages.append(str(error))
            error_text = "; ".join(messages)
        else:
            error_text = str(errors)
        raise LoopError(f"GraphQL query failed: {error_text}. Query: {query.strip()}")

    if "data" not in payload or payload["data"] is None:
        raise LoopError(f"GraphQL response did not include data. Query: {query.strip()}")

    return payload


def get_pr_context(owner: str, repo: str, pr_ref: str) -> Dict[str, Any]:
    repo_full = f"{owner}/{repo}"
    data = run_gh_json(
        [
            "pr",
            "view",
            pr_ref,
            "--repo",
            repo_full,
            "--json",
            "number,headRefName,baseRefName,headRefOid,url",
        ]
    )
    required_fields = ["number", "headRefName", "baseRefName", "headRefOid", "url"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise LoopError(
            f"gh pr view returned incomplete data (missing: {', '.join(missing_fields)}). "
            "Verify gh version/permissions and retry."
        )
    return {
        "pr_number": data["number"],
        "head_branch": data["headRefName"],
        "base_branch": data["baseRefName"],
        "head_sha": data["headRefOid"],
        "url": data["url"],
    }


def fetch_unresolved_threads(owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
    query = """
query($owner:String!,$repo:String!,$number:Int!,$threadsCursor:String){
  repository(owner:$owner,name:$repo){
    pullRequest(number:$number){
      reviewThreads(first:100, after:$threadsCursor){
        nodes{
          id
          isResolved
          isOutdated
          path
        }
        pageInfo{
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""
    threads: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    while True:
        payload = graphql(query, {"owner": owner, "repo": repo, "number": pr_number, "threadsCursor": cursor})
        page = payload["data"]["repository"]["pullRequest"]["reviewThreads"]
        threads.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    unresolved: List[Dict[str, Any]] = []
    for thread in threads:
        # Include outdated threads so operators can explicitly reply/resolve every
        # unresolved review comment in the loop.
        if thread["isResolved"]:
            continue
        unresolved.append(thread)
    return unresolved


def has_copilot_request(owner: str, repo: str, pr_number: int) -> bool:
    query = """
query($owner:String!,$repo:String!,$number:Int!,$cursor:String){
  repository(owner:$owner,name:$repo){
    pullRequest(number:$number){
      reviewRequests(first:100, after:$cursor){
        nodes{
          requestedReviewer{
            ... on User{ login }
            ... on Bot{ login }
            ... on Team{ slug }
          }
        }
        pageInfo{
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""
    cursor: Optional[str] = None
    while True:
        payload = graphql(query, {"owner": owner, "repo": repo, "number": pr_number, "cursor": cursor})
        requests = payload["data"]["repository"]["pullRequest"]["reviewRequests"]
        nodes = requests["nodes"]
        for node in nodes:
            reviewer = node.get("requestedReviewer") or {}
            if is_copilot_reviewer(reviewer):
                return True
        if not requests["pageInfo"]["hasNextPage"]:
            break
        cursor = requests["pageInfo"]["endCursor"]
    return False


def get_copilot_reviewer_state(owner: str, repo: str, pr_number: int) -> str:
    # Use the same GraphQL-backed matcher as request-copilot to avoid shape
    # drift in `gh pr view --json reviewRequests` output.
    if has_copilot_request(owner, repo, pr_number):
        return COPILOT_REVIEWER_STATE_AWAITING
    return COPILOT_REVIEWER_STATE_NOT_AWAITING


def get_copilot_reviews(owner: str, repo: str, pr_number: int, since_ts: str) -> List[Dict[str, Any]]:
    paged = run_gh_json(["api", "--paginate", "--slurp", f"repos/{owner}/{repo}/pulls/{pr_number}/reviews"])
    reviews: List[Dict[str, Any]] = []
    if isinstance(paged, list):
        for page in paged:
            if isinstance(page, list):
                reviews.extend(page)
            elif isinstance(page, dict):
                reviews.append(page)
    since = parse_iso(since_ts)
    found = []
    for review in reviews:
        user = ((review.get("user") or {}).get("login", "") or "").lower()
        submitted_at = review.get("submitted_at")
        if user in COPILOT_LOGINS and submitted_at and parse_iso(submitted_at) >= since:
            found.append(review)
    return found


def get_latest_copilot_review_submitted_at(owner: str, repo: str, pr_number: int) -> Optional[str]:
    paged = run_gh_json(["api", "--paginate", "--slurp", f"repos/{owner}/{repo}/pulls/{pr_number}/reviews"])
    reviews: List[Dict[str, Any]] = []
    if isinstance(paged, list):
        for page in paged:
            if isinstance(page, list):
                reviews.extend(page)
            elif isinstance(page, dict):
                reviews.append(page)

    latest: Optional[str] = None
    for review in reviews:
        user = ((review.get("user") or {}).get("login", "") or "").lower()
        submitted_at = review.get("submitted_at")
        if user not in COPILOT_LOGINS or not submitted_at:
            continue
        if latest is None or parse_iso(submitted_at) > parse_iso(latest):
            latest = submitted_at
    return latest


def is_retryable_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    retry_markers = [
        "timeout",
        "timed out",
        "connection reset",
        "connection refused",
        "connection aborted",
        "temporary failure",
        "secondary rate limit",
        "abuse detection",
        "502",
        "503",
        "504",
    ]
    return any(marker in msg for marker in retry_markers)


def with_retries(func, deadline: float, max_retries: int = 3):
    delay = 2.0
    retries = 0
    while True:
        try:
            return func()
        except LoopError as exc:
            retries += 1
            if retries > max_retries or not is_retryable_error(exc):
                raise
            if time.time() + delay >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 20.0)


def cmd_init(args: argparse.Namespace) -> None:
    pr_context = get_pr_context(args.owner, args.repo, args.pr)
    unresolved = fetch_unresolved_threads(args.owner, args.repo, pr_context["pr_number"])
    state = {
        "run_id": f"pr-{pr_context['pr_number']}-{int(time.time())}",
        "loop_count": 0,
        "owner": args.owner,
        "repo": args.repo,
        "pr_number": pr_context["pr_number"],
        "pr_branch": pr_context["head_branch"],
        "base_branch": pr_context["base_branch"],
        "last_processed_head_sha": pr_context["head_sha"],
        "copilot_requested_at": None,
        "copilot_review_baseline_at": None,
        "last_seen_review_event_at": None,
        "known_thread_ids": [t["id"] for t in unresolved],
        "processed_actions": [],
        "escalation_reason": None,
    }
    state.update(default_state_extensions())
    ensure_iteration_bucket(state, 1)
    save_state(state)
    print(json.dumps({"state_path": str(STATE_PATH), "unresolved_count": len(unresolved)}, indent=2))


def cmd_request_copilot(_: argparse.Namespace) -> None:
    state = load_state()
    require_state_keys(state, ["owner", "repo", "pr_number", "pr_branch"])
    ensure_within_iteration_cap(state)
    require_implementation_push(state)
    ensure_changes_pushed()
    ensure_on_pr_branch(state)
    owner = state["owner"]
    repo = state["repo"]
    pr_number = state["pr_number"]
    repo_full = f"{owner}/{repo}"
    current_local_head = run_git(["rev-parse", "HEAD"])
    current_pr_head = get_pr_context(owner, repo, str(pr_number))["head_sha"]
    if current_local_head != current_pr_head:
        raise LoopError(
            "Commit barrier failed: local HEAD does not match current PR head. "
            "Checkout/sync the PR branch before requesting review."
        )
    impl = get_current_bucket(state).get("artifacts", {}).get("implementation", {})
    impl_sha = impl.get("pushed_sha") if isinstance(impl, dict) else None
    if impl_sha != current_pr_head:
        raise LoopError(
            "Implementation push proof is stale for current PR head. "
            "Record implementation with pushed_sha matching the current PR head before request-copilot."
        )
    state["last_processed_head_sha"] = current_pr_head
    # Capture current latest Copilot review so poll waits for a newer one.
    state["copilot_review_baseline_at"] = get_latest_copilot_review_submitted_at(owner, repo, pr_number)

    request_anchor = utc_now_minus_seconds_iso(120)
    requested = has_copilot_request(owner, repo, pr_number)
    if not requested:
        result = run_gh_allow_error(["pr", "edit", str(pr_number), "--repo", repo_full, "--add-reviewer", "@copilot"])
        if result.returncode != 0:
            stdout_text = (result.stdout or "").strip()
            stderr_text = (result.stderr or "").strip()
            combined_output = "\n".join(part for part in [stdout_text, stderr_text] if part)
            err = combined_output.lower()
            if "already" not in err and "exists" not in err:
                fake_result = subprocess.CompletedProcess(
                    args=["gh", "pr", "edit", str(pr_number), "--repo", repo_full, "--add-reviewer", "@copilot"],
                    returncode=result.returncode,
                    stdout=stdout_text,
                    stderr=stderr_text,
                )
                raise LoopError(format_failed_command(fake_result.args, fake_result))
    reviewer_state = get_copilot_reviewer_state(owner, repo, pr_number)
    immediate_review_found = False
    if reviewer_state != COPILOT_REVIEWER_STATE_AWAITING:
        immediate_reviews = get_copilot_reviews(owner, repo, pr_number, request_anchor)
        if baseline_ts := state.get("copilot_review_baseline_at"):
            immediate_reviews = [
                review
                for review in immediate_reviews
                if review.get("submitted_at") and parse_iso(review["submitted_at"]) > parse_iso(baseline_ts)
            ]
        if not immediate_reviews:
            raise LoopError(
                "Post-condition failed: Copilot reviewer is not awaiting review after request-copilot, "
                "and no new Copilot review was detected."
            )
        newest = max(review["submitted_at"] for review in immediate_reviews if review.get("submitted_at"))
        state["last_seen_review_event_at"] = newest
        immediate_review_found = True
    # Always refresh the request anchor so polling only considers reviews
    # associated with the current request cycle.
    # Add a small clock-skew buffer so server-side review timestamps are not missed.
    state["copilot_requested_at"] = request_anchor
    state["escalation_reason"] = None
    if not immediate_review_found:
        state["last_seen_review_event_at"] = None
    save_state(state)
    print(
        json.dumps(
            {
                "copilot_requested": True,
                "already_requested": requested,
                "copilot_reviewer_state": reviewer_state,
                "copilot_requested_at": state["copilot_requested_at"],
                "copilot_review_baseline_at": state["copilot_review_baseline_at"],
            },
            indent=2,
        )
    )


def cmd_poll_copilot(args: argparse.Namespace) -> None:
    state = load_state()
    require_state_keys(
        state,
        ["owner", "repo", "pr_number", "pr_branch", "last_processed_head_sha", "loop_count", "known_thread_ids"],
    )
    ensure_within_iteration_cap(state)
    ensure_on_pr_branch(state)
    ensure_changes_pushed()
    if not state.get("copilot_requested_at"):
        raise LoopError("copilot_requested_at is missing. Run request-copilot first.")
    baseline_ts = state.get("copilot_review_baseline_at")

    if args.interval_minutes <= 0:
        raise LoopError("--interval-minutes must be > 0")
    if args.timeout_minutes <= 0:
        raise LoopError("--timeout-minutes must be > 0")
    if args.interval_minutes > args.timeout_minutes:
        raise LoopError("--interval-minutes must be <= --timeout-minutes")

    owner = state["owner"]
    repo = state["repo"]
    pr_number = state["pr_number"]
    deadline = time.time() + args.timeout_minutes * 60
    interval_seconds = args.interval_minutes * 60

    attempts = 0
    found_reviews: List[Dict[str, Any]] = []
    initial_reviewer_state = with_retries(
        lambda: get_copilot_reviewer_state(owner, repo, pr_number),
        deadline=deadline,
    )
    seen_awaiting_state = initial_reviewer_state == COPILOT_REVIEWER_STATE_AWAITING
    current_sha = with_retries(
        lambda: get_pr_context(owner, repo, str(pr_number))["head_sha"],
        deadline=deadline,
    )
    if current_sha != state.get("last_processed_head_sha"):
        state["escalation_reason"] = (
            f"PR head drift detected before polling: state={state.get('last_processed_head_sha')} current={current_sha}"
        )
        save_state(state)
        raise LoopError(state["escalation_reason"])

    while time.time() <= deadline:
        attempts += 1
        polled_sha = with_retries(
            lambda: get_pr_context(owner, repo, str(pr_number))["head_sha"],
            deadline=deadline,
        )
        if polled_sha != state.get("last_processed_head_sha"):
            state["escalation_reason"] = (
                f"PR head drift detected during polling: state={state.get('last_processed_head_sha')} current={polled_sha}"
            )
            save_state(state)
            raise LoopError(state["escalation_reason"])

        reviewer_state = with_retries(
            lambda: get_copilot_reviewer_state(owner, repo, pr_number),
            deadline=deadline,
        )
        if reviewer_state == COPILOT_REVIEWER_STATE_AWAITING:
            seen_awaiting_state = True
            if time.time() + interval_seconds > deadline:
                break
            time.sleep(interval_seconds)
            continue

        # Reviewer transitioned out of awaiting (or was already non-awaiting)
        # for the active cycle, so treat this as poll completion and then fetch
        # review artifacts/threads for loop decisions.
        found_reviews = with_retries(
            lambda: get_copilot_reviews(owner, repo, pr_number, state["copilot_requested_at"]),
            deadline=deadline,
        )
        if baseline_ts:
            found_reviews = [
                review
                for review in found_reviews
                if review.get("submitted_at") and parse_iso(review["submitted_at"]) > parse_iso(baseline_ts)
            ]
        if found_reviews:
            newest = max(review["submitted_at"] for review in found_reviews if review.get("submitted_at"))
            state["last_seen_review_event_at"] = newest
        else:
            state["last_seen_review_event_at"] = None
            state["escalation_reason"] = (
                "Copilot reviewer left awaiting state, but no new Copilot review was found for this cycle."
            )
            save_state(state)
            raise LoopError(state["escalation_reason"])

        unresolved = with_retries(lambda: fetch_unresolved_threads(owner, repo, pr_number), deadline=deadline)
        state["known_thread_ids"] = [t["id"] for t in unresolved]
        state["last_processed_head_sha"] = polled_sha
        if unresolved:
            advance_iteration_or_fail(state)
        save_state(state)
        print(
            json.dumps(
                {
                    "copilot_review_found": len(found_reviews) > 0,
                    "completion_signal": "reviewer_state",
                    "copilot_reviewer_state": reviewer_state,
                    "saw_awaiting_before_completion": seen_awaiting_state,
                    "attempts": attempts,
                    "copilot_review_count": len(found_reviews),
                    "new_unresolved_count": len(unresolved),
                    "loop_should_restart": len(unresolved) > 0,
                    "loop_count": state["loop_count"],
                    "loop_limit_reached": int(state.get("loop_count", 0)) >= int(state.get("max_iterations", 10)),
                },
                indent=2,
            )
        )
        return

    state["escalation_reason"] = (
        "Timed out waiting for Copilot reviewer state change "
        f"after {attempts} attempt(s) over {args.timeout_minutes} minute(s)."
    )
    save_state(state)
    raise LoopError(state["escalation_reason"])


def cmd_record_triage(args: argparse.Namespace) -> None:
    state = load_state()
    artifact = {
        "unresolved_decisions": args.unresolved_decisions,
        "action_plan": args.action_plan,
    }
    payload = record_role_artifact(state, "triage", args.agent_id, artifact, args.replace, args.replace_reason)
    state["invariant_failures"] = []
    save_state(state)
    print(json.dumps({"iteration": state["current_iteration"], "role": "triage", "artifact": payload}, indent=2))


def cmd_record_implementation(args: argparse.Namespace) -> None:
    state = load_state()
    if args.push_completed and not args.pushed_sha:
        raise LoopError("--pushed-sha is required when --push-completed is set.")
    artifact = {
        "checks_run": [part.strip() for part in args.checks_run.split(",") if part.strip()],
        "checks_passed": args.checks_passed,
        "push_completed": args.push_completed,
        "pushed_sha": args.pushed_sha,
    }
    payload = record_role_artifact(
        state, "implementation", args.agent_id, artifact, args.replace, args.replace_reason
    )
    if args.push_completed and args.pushed_sha:
        state["last_fix_sha"] = args.pushed_sha
    state["invariant_failures"] = []
    save_state(state)
    print(json.dumps({"iteration": state["current_iteration"], "role": "implementation", "artifact": payload}, indent=2))


def cmd_record_self_review(args: argparse.Namespace) -> None:
    state = load_state()
    artifact = {
        "gate": args.gate,
        "notes": args.notes,
    }
    payload = record_role_artifact(state, "self_review", args.agent_id, artifact, args.replace, args.replace_reason)
    state["invariant_failures"] = []
    save_state(state)
    print(json.dumps({"iteration": state["current_iteration"], "role": "self_review", "artifact": payload}, indent=2))


def cmd_verify_invariants(_: argparse.Namespace) -> None:
    state = load_state()
    failures = collect_invariant_failures(state)
    state["invariant_failures"] = failures
    save_state(state)
    if failures:
        raise LoopError(f"Invariant check failed: {', '.join(failures)}")
    print(
        json.dumps(
            {
                "iteration": state["current_iteration"],
                "status": "ok",
                "roles_completed": state.get("roles_completed", []),
            },
            indent=2,
        )
    )


def run_finalize_cycle(state: Dict[str, Any], interval_minutes: int, timeout_minutes: int, target_sha: str) -> Dict[str, Any]:
    owner = state["owner"]
    repo = state["repo"]
    pr_number = state["pr_number"]
    request_anchor = iso_now()
    query_anchor = utc_now_minus_seconds_iso(120)
    requested = has_copilot_request(owner, repo, pr_number)
    if not requested:
        repo_full = f"{owner}/{repo}"
        edit_cmd = ["pr", "edit", str(pr_number), "--repo", repo_full, "--add-reviewer", "@copilot"]
        result = run_gh_allow_error(edit_cmd)
        if result.returncode != 0:
            raise LoopError(format_failed_command(["gh", *edit_cmd], result))
    state["post_fix_review_requested_at"] = request_anchor
    state["copilot_requested_at"] = request_anchor
    save_state(state)

    deadline = time.time() + timeout_minutes * 60
    interval_seconds = interval_minutes * 60
    while time.time() <= deadline:
        current_sha = get_pr_context(owner, repo, str(pr_number))["head_sha"]
        if current_sha != target_sha:
            return {"status": FINALIZE_DRIFTED, "target_sha": target_sha, "current_sha": current_sha}
        reviewer_state = get_copilot_reviewer_state(owner, repo, pr_number)
        if reviewer_state == COPILOT_REVIEWER_STATE_AWAITING:
            if time.time() + interval_seconds > deadline:
                break
            time.sleep(interval_seconds)
            continue
        reviews = get_copilot_reviews(owner, repo, pr_number, query_anchor)
        reviews = [
            review for review in reviews if review.get("submitted_at") and parse_iso(review["submitted_at"]) > parse_iso(request_anchor)
        ]
        if not reviews:
            if time.time() + interval_seconds > deadline:
                break
            time.sleep(interval_seconds)
            continue
        newest = max(review["submitted_at"] for review in reviews if review.get("submitted_at"))
        state["post_fix_review_completed_at"] = newest
        state["post_fix_review_sha"] = target_sha
        unresolved = fetch_unresolved_threads(owner, repo, pr_number)
        state["unresolved_after_post_fix_review"] = len(unresolved)
        save_state(state)
        if unresolved:
            return {"status": FINALIZE_NEEDS_LOOP, "unresolved_count": len(unresolved), "target_sha": target_sha}
        return {"status": FINALIZE_SUCCESS, "unresolved_count": 0, "target_sha": target_sha}
    return {"status": FINALIZE_TIMEOUT, "target_sha": target_sha}


def cmd_finalize(args: argparse.Namespace) -> None:
    state = load_state()
    require_state_keys(state, ["owner", "repo", "pr_number", "pr_branch", "last_processed_head_sha"])
    ensure_on_pr_branch(state)
    ensure_changes_pushed()
    ensure_within_iteration_cap(state)
    failures = collect_invariant_failures(state)
    if failures:
        state["invariant_failures"] = failures
        save_state(state)
        raise LoopError(f"Invariant check failed before finalize: {', '.join(failures)}")
    require_implementation_push(state)
    if args.interval_minutes <= 0:
        raise LoopError("--interval-minutes must be > 0")
    if args.timeout_minutes <= 0:
        raise LoopError("--timeout-minutes must be > 0")
    if args.interval_minutes > args.timeout_minutes:
        raise LoopError("--interval-minutes must be <= --timeout-minutes")

    impl = get_current_bucket(state).get("artifacts", {}).get("implementation", {})
    impl_sha = impl.get("pushed_sha")
    if not impl_sha:
        raise LoopError("Implementation artifact is missing pushed_sha.")
    head_sha = args.head_sha or get_pr_context(state["owner"], state["repo"], str(state["pr_number"]))["head_sha"]
    if head_sha != impl_sha:
        print(json.dumps({"status": FINALIZE_DRIFTED, "target_sha": impl_sha, "head_sha": head_sha}, indent=2))
        return

    result = run_finalize_cycle(state, args.interval_minutes, args.timeout_minutes, impl_sha)
    status = result["status"]
    if status == FINALIZE_NEEDS_LOOP:
        advance_iteration_or_fail(state)
    elif status == FINALIZE_SUCCESS:
        state["last_processed_head_sha"] = impl_sha

    # Fresh-cycle timing proof must be after push artifact.
    impl_recorded_at = impl.get("recorded_at")
    if status == FINALIZE_SUCCESS and impl_recorded_at:
        requested_at = state.get("post_fix_review_requested_at")
        completed_at = state.get("post_fix_review_completed_at")
        if not requested_at or not completed_at or parse_iso(requested_at) <= parse_iso(impl_recorded_at) or parse_iso(
            completed_at
        ) <= parse_iso(impl_recorded_at):
            status = FINALIZE_NEEDS_LOOP
            state["invariant_failures"] = state.get("invariant_failures", []) + ["post_fix_review_not_fresh"]
            advance_iteration_or_fail(state)

    save_state(state)
    print(json.dumps({**result, "status": status, "iteration": state["current_iteration"]}, indent=2))


def cmd_validate_scenarios(_: argparse.Namespace) -> None:
    base = {
        "current_iteration": 1,
        "max_iterations": 10,
        "iteration_artifacts": {},
        "roles_completed": [],
        "role_agent_ids": {},
        "invariant_failures": [],
    }
    state = migrate_state(base)
    record_role_artifact(state, "triage", "agent-triage", {"action_plan": "ok", "unresolved_decisions": "ok"}, False, None)
    try:
        record_role_artifact(state, "self_review", "agent-review", {"gate": "pass", "notes": "bad order"}, False, None)
        raise LoopError("expected out-of-order rejection")
    except LoopError:
        pass
    record_role_artifact(
        state,
        "implementation",
        "agent-impl",
        {"checks_run": ["project-ci-command"], "checks_passed": True, "push_completed": True, "pushed_sha": "abc123"},
        False,
        None,
    )
    try:
        record_role_artifact(
            state,
            "self_review",
            "agent-impl",
            {"gate": "pass", "notes": "duplicate"},
            False,
            None,
        )
        raise LoopError("expected duplicate-agent rejection")
    except LoopError:
        pass
    record_role_artifact(state, "self_review", "agent-review", {"gate": "pass", "notes": "ok"}, False, None)
    failures = collect_invariant_failures(state)
    if failures:
        raise LoopError(f"expected no failures for happy path, got: {failures}")
    cap_state = migrate_state({"current_iteration": 10, "max_iterations": 10, "iteration_artifacts": {}})
    try:
        advance_iteration_or_fail(cap_state)
        raise LoopError("expected cap_exceeded at iteration 11")
    except LoopError as exc:
        if FINALIZE_CAP_EXCEEDED not in str(exc):
            raise
    print(json.dumps({"validation": "ok", "scenarios": 5}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stateful runner for PR review loop skill")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize loop state and unresolved thread snapshot")
    init_parser.add_argument("--owner", required=True)
    init_parser.add_argument("--repo", required=True)
    init_parser.add_argument("--pr", required=True, help="PR number, URL, or branch")
    init_parser.set_defaults(func=cmd_init)

    request_parser = subparsers.add_parser("request-copilot", help="Request Copilot review idempotently")
    request_parser.set_defaults(func=cmd_request_copilot)

    poll_parser = subparsers.add_parser("poll-copilot", help="Poll for Copilot review with timeout")
    poll_parser.add_argument("--interval-minutes", type=int, default=3)
    poll_parser.add_argument("--timeout-minutes", type=int, default=15)
    poll_parser.set_defaults(func=cmd_poll_copilot)

    triage_parser = subparsers.add_parser("record-triage", help="Record triage artifact for active iteration")
    triage_parser.add_argument("--agent-id", required=True)
    triage_parser.add_argument("--unresolved-decisions", required=True)
    triage_parser.add_argument("--action-plan", required=True)
    triage_parser.add_argument("--replace", action="store_true")
    triage_parser.add_argument("--replace-reason")
    triage_parser.set_defaults(func=cmd_record_triage)

    implementation_parser = subparsers.add_parser(
        "record-implementation", help="Record implementation artifact for active iteration"
    )
    implementation_parser.add_argument("--agent-id", required=True)
    implementation_parser.add_argument("--checks-run", required=True, help="Comma-separated commands")
    implementation_parser.add_argument("--checks-passed", action="store_true")
    implementation_parser.add_argument("--push-completed", action="store_true")
    implementation_parser.add_argument("--pushed-sha")
    implementation_parser.add_argument("--replace", action="store_true")
    implementation_parser.add_argument("--replace-reason")
    implementation_parser.set_defaults(func=cmd_record_implementation)

    self_review_parser = subparsers.add_parser("record-self-review", help="Record self-review gate artifact")
    self_review_parser.add_argument("--agent-id", required=True)
    self_review_parser.add_argument("--gate", required=True, choices=["pass", "fail", "blocked"])
    self_review_parser.add_argument("--notes", required=True)
    self_review_parser.add_argument("--replace", action="store_true")
    self_review_parser.add_argument("--replace-reason")
    self_review_parser.set_defaults(func=cmd_record_self_review)

    verify_parser = subparsers.add_parser("verify-invariants", help="Verify current iteration invariants")
    verify_parser.set_defaults(func=cmd_verify_invariants)

    finalize_parser = subparsers.add_parser("finalize", help="Run final post-fix Copilot gate for active iteration")
    finalize_parser.add_argument("--head-sha")
    finalize_parser.add_argument("--interval-minutes", type=int, default=3)
    finalize_parser.add_argument("--timeout-minutes", type=int, default=15)
    finalize_parser.set_defaults(func=cmd_finalize)

    validate_parser = subparsers.add_parser("validate-scenarios", help="Run script-level validation scenarios")
    validate_parser.set_defaults(func=cmd_validate_scenarios)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except LoopError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
