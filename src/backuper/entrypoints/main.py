"""Compatibility module forwarding to `backuper.entrypoints.cli.main`."""

from backuper.entrypoints.cli.main import dispatch_command, main, run_with_args

__all__ = ["dispatch_command", "run_with_args", "main"]
