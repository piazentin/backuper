"""Shared pure helpers (paths, hashing); see AGENTS.md for layering."""

from backuper.utils.gitignore_lines import (
    gitignore_pattern_lines,
    gitignore_pattern_lines_from_text,
    iter_gitignore_pattern_lines,
)
from backuper.utils.hashing import compute_hash
from backuper.utils.paths import (
    hash_to_stored_location,
    normalize_path,
    relative_dir_from_hash,
)

__all__ = [
    "gitignore_pattern_lines",
    "gitignore_pattern_lines_from_text",
    "iter_gitignore_pattern_lines",
    "compute_hash",
    "hash_to_stored_location",
    "normalize_path",
    "relative_dir_from_hash",
]
