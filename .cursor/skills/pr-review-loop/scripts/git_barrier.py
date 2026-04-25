#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List

DEFAULT_GIT_COMMAND_TIMEOUT_SECONDS = 30
DEFAULT_GIT_PUSH_TIMEOUT_SECONDS = 120


class BarrierError(Exception):
    pass


def format_failed_command(cmd: List[str], result: subprocess.CompletedProcess[str]) -> str:
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    return (
        f"Command failed: {' '.join(cmd)}\n"
        f"stdout:\n{stdout if stdout else '<empty>'}\n"
        f"stderr:\n{stderr if stderr else '<empty>'}"
    )


def get_timeout_seconds_for_command(args: List[str]) -> int:
    command = args[0] if args else ""
    env_var_name = "GIT_COMMAND_TIMEOUT_SECONDS"
    default_timeout = DEFAULT_GIT_COMMAND_TIMEOUT_SECONDS
    if command == "push":
        env_var_name = "GIT_PUSH_TIMEOUT_SECONDS"
        default_timeout = DEFAULT_GIT_PUSH_TIMEOUT_SECONDS
    timeout_value = os.environ.get(env_var_name, str(default_timeout))
    try:
        return int(timeout_value)
    except ValueError as exc:
        raise BarrierError(
            f"Invalid value for {env_var_name}: {timeout_value!r}. Expected an integer number of seconds."
        ) from exc


def run_git(args: List[str]) -> str:
    cmd = ["git", *args]
    timeout_seconds = get_timeout_seconds_for_command(args)
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise BarrierError(f"Command timed out after {timeout_seconds} seconds: {' '.join(cmd)}") from exc
    except OSError as exc:
        raise BarrierError(f"Failed to execute command: {' '.join(cmd)}\n{exc}") from exc

    if result.returncode != 0:
        raise BarrierError(format_failed_command(cmd, result))
    return result.stdout.strip()


def ensure_push_synced() -> None:
    status_porcelain = run_git(["status", "--porcelain"])
    if status_porcelain:
        raise BarrierError("Commit barrier failed: working tree is not clean after push.")

    try:
        upstream = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    except BarrierError as exc:
        raise BarrierError("Commit barrier failed: current branch has no upstream after push.") from exc

    ahead_behind = run_git(["rev-list", "--left-right", "--count", f"{upstream}...HEAD"])
    parts = ahead_behind.split()
    if len(parts) != 2:
        raise BarrierError(f"Unexpected ahead/behind output: {ahead_behind}")

    try:
        behind_count = int(parts[0])
        ahead_count = int(parts[1])
    except ValueError as exc:
        raise BarrierError(f"Unexpected ahead/behind output: {ahead_behind}") from exc
    if ahead_count > 0:
        raise BarrierError(f"Commit barrier failed: local branch still ahead by {ahead_count} commit(s).")
    if behind_count > 0:
        raise BarrierError(f"Commit barrier failed: local branch behind by {behind_count} commit(s).")


def cmd_run(args: argparse.Namespace) -> None:
    message_path = Path(args.message_file)
    if not message_path.exists():
        raise BarrierError(f"Commit message file not found: {message_path}")

    try:
        commit_message = message_path.read_text().strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise BarrierError(f"Failed to read commit message file {message_path}: {exc}") from exc
    if not commit_message:
        raise BarrierError(f"Commit message file is empty: {message_path}")

    run_git(["add", "--", *args.files])
    commit_args = ["commit"]
    if args.trailer:
        commit_args.extend(["--trailer", args.trailer])
    commit_args.extend(["-m", commit_message])
    run_git(commit_args)
    run_git(["push"])
    ensure_push_synced()

    print(
        json.dumps(
            {
                "ok": True,
                "files_staged": args.files,
                "trailer": args.trailer,
                "message_file": str(message_path),
            },
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run commit barrier commands sequentially for pr-review-loop."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Stage files, commit, push, and verify sync",
    )
    run_parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="Files to stage with git add",
    )
    run_parser.add_argument(
        "--message-file",
        required=True,
        help="Path to plain-text commit message file",
    )
    run_parser.add_argument(
        "--trailer",
        default=None,
        help="Optional git trailer to append to the commit when provided",
    )
    run_parser.set_defaults(func=cmd_run)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except BarrierError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
