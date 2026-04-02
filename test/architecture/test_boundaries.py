"""
AST-based architecture guardrails for `backuper.implementation`.

Enforces legacy isolation under implementation, controller layering (function-only
controllers), no imports of concrete `components` from controllers (ports live in
`implementation.interfaces`), and no controller-to-controller coupling.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_ROOT = REPO_ROOT / "backuper" / "implementation"
CONTROLLERS_ROOT = IMPLEMENTATION_ROOT / "controllers"

_COMPONENTS_ROOT_PKG = "backuper.implementation.components"


def _is_under_components_package(module_path: str) -> bool:
    return module_path == _COMPONENTS_ROOT_PKG or module_path.startswith(
        _COMPONENTS_ROOT_PKG + "."
    )


def _iter_py_files(root: Path) -> Iterator[Path]:
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*.py")):
        if path.name == "__pycache__":
            continue
        yield path


def _rel_posix(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _importfrom_resolved_pairs(node: ast.ImportFrom) -> list[tuple[str, str]]:
    """Absolute ImportFrom only: (resolved module path, local binding name) per alias."""
    if node.level != 0 or node.module is None:
        return []
    m = node.module
    pairs: list[tuple[str, str]] = []
    for alias in node.names:
        if alias.name == "*":
            continue
        local = alias.asname or alias.name
        if m == _COMPONENTS_ROOT_PKG:
            resolved = f"{_COMPONENTS_ROOT_PKG}.{alias.name}"
        else:
            resolved = m
        pairs.append((resolved, local))
    return pairs


def _collect_controller_components_import_violations(
    tree: ast.Module, relpath: str
) -> list[str]:
    bad: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                path = alias.name
                if not _is_under_components_package(path):
                    continue
                bad.append(
                    f"{relpath}:{node.lineno}: import of {path!r} not allowed "
                    f"(controllers must not import {_COMPONENTS_ROOT_PKG!r}; "
                    f"use backuper.implementation.interfaces for ports)"
                )
        elif isinstance(node, ast.ImportFrom):
            reported: set[str] = set()
            for resolved, _ in _importfrom_resolved_pairs(node):
                if resolved in reported:
                    continue
                if not _is_under_components_package(resolved):
                    continue
                reported.add(resolved)
                bad.append(
                    f"{relpath}:{node.lineno}: import from {resolved!r} not allowed "
                    f"(controllers must not import {_COMPONENTS_ROOT_PKG!r}; "
                    f"use backuper.implementation.interfaces for ports)"
                )
    return bad


def _collect_legacy_import_violations(tree: ast.Module, relpath: str) -> list[str]:
    bad: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "backuper.legacy" or alias.name.startswith(
                    "backuper.legacy."
                ):
                    bad.append(
                        f"{relpath}:{node.lineno}: forbidden legacy import {alias.name!r}"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module and (
                node.module == "backuper.legacy"
                or node.module.startswith("backuper.legacy.")
            ):
                bad.append(
                    f"{relpath}:{node.lineno}: forbidden legacy import from "
                    f"{node.module!r}"
                )
    return bad


def _collect_controller_cross_import_violations(
    tree: ast.Module, relpath: str
) -> list[str]:
    bad: list[str] = []
    prefix = "backuper.implementation.controllers"

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module and (
            node.module == prefix or node.module.startswith(prefix + ".")
        ):
            bad.append(
                f"{relpath}:{node.lineno}: controllers must not import other controller "
                f"modules ({node.module!r})"
            )
    return bad


def test_no_legacy_imports_under_implementation() -> None:
    violations: list[str] = []
    for path in _iter_py_files(IMPLEMENTATION_ROOT):
        tree = _parse(path)
        violations.extend(_collect_legacy_import_violations(tree, _rel_posix(path)))
    assert not violations, "Legacy imports under implementation:\n" + "\n".join(
        violations
    )


def test_no_controller_to_controller_imports() -> None:
    violations: list[str] = []
    for path in _iter_py_files(CONTROLLERS_ROOT):
        tree = _parse(path)
        violations.extend(
            _collect_controller_cross_import_violations(tree, _rel_posix(path))
        )
    assert not violations, "Controller cross-imports:\n" + "\n".join(violations)


def test_controllers_do_not_import_components() -> None:
    violations: list[str] = []
    for path in _iter_py_files(CONTROLLERS_ROOT):
        tree = _parse(path)
        violations.extend(
            _collect_controller_components_import_violations(tree, _rel_posix(path))
        )
    assert not violations, "Forbidden components imports:\n" + "\n".join(violations)


def test_controllers_are_function_only_no_classes() -> None:
    violations: list[str] = []
    for path in _iter_py_files(CONTROLLERS_ROOT):
        tree = _parse(path)
        relpath = _rel_posix(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                violations.append(
                    f"{relpath}:{node.lineno}: unexpected class {node.name!r} "
                    f"(controllers must remain function-only)"
                )
    assert not violations, "Unexpected controller classes:\n" + "\n".join(violations)


@pytest.mark.parametrize(
    "path",
    list(_iter_py_files(IMPLEMENTATION_ROOT)),
    ids=lambda p: _rel_posix(p),
)
def test_implementation_modules_parse_as_ast(path: Path) -> None:
    _parse(path)
