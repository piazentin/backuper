"""Compatibility module for CLI command runners."""

from backuper.entrypoints.cli_runner import (
    run_new,
    run_restore,
    run_update,
    run_verify_integrity,
)

__all__ = ["run_new", "run_update", "run_verify_integrity", "run_restore"]
