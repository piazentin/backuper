"""Compatibility module forwarding to `backuper.entrypoints.cli.runner`."""

from backuper.entrypoints.cli.runner import (
    run_new,
    run_restore,
    run_update,
    run_verify_integrity,
)

__all__ = ["run_new", "run_update", "run_verify_integrity", "run_restore"]
