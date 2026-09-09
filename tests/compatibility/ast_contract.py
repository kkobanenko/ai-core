"""Static Python API shape extraction for historical source evidence."""

from __future__ import annotations

import ast
from typing import Any


class ContractExtractionError(ValueError):
    """Source cannot be represented as a deterministic static contract."""


def _text(node: ast.AST | None) -> str | None:
    return None if node is None else ast.unparse(node)


def _argument(name: str, annotation: ast.AST | None, default: ast.AST | None) -> dict[str, str | None]:
    return {
        "name": name,
        "annotation": _text(annotation),
        "default": _text(default),
    }


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    positional = [*node.args.posonlyargs, *node.args.args]
    padding = [None] * (len(positional) - len(node.args.defaults))
    defaults = [*padding, *node.args.defaults]
    positional_only_count = len(node.args.posonlyargs)
    positional_specs = [
        _argument(item.arg, item.annotation, default)
        for item, default in zip(positional, defaults)
    ]
    keyword_only = [
        _argument(item.arg, item.annotation, default)
        for item, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
    ]
    return {
        "positional_only": positional_specs[:positional_only_count],
        "positional": positional_specs[positional_only_count:],
        "keyword_only": keyword_only,
        "vararg": (
            None
            if node.args.vararg is None
            else _argument(node.args.vararg.arg, node.args.vararg.annotation, None)
        ),
        "kwarg": (
            None
            if node.args.kwarg is None
            else _argument(node.args.kwarg.arg, node.args.kwarg.annotation, None)
        ),
        "returns": _text(node.returns),
    }


def _class_contract(node: ast.ClassDef) -> dict[str, Any]:
    fields: list[dict[str, str | None]] = []
    methods: dict[str, dict[str, Any]] = {}
    enum_members: list[dict[str, object]] = []
    is_enum = any(_text(base).endswith("Enum") for base in node.bases)

    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            fields.append(
                {
                    "name": item.target.id,
                    "annotation": _text(item.annotation),
                    "default": _text(item.value),
                }
            )
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods[item.name] = _signature(item)
        elif is_enum and isinstance(item, ast.Assign) and len(item.targets) == 1:
            target = item.targets[0]
            if isinstance(target, ast.Name):
                try:
                    value = ast.literal_eval(item.value)
                except (ValueError, TypeError):
                    value = _text(item.value)
                enum_members.append({"name": target.id, "value": value})

    return {
        "bases": [_text(base) for base in node.bases],
        "decorators": [_text(decorator) for decorator in node.decorator_list],
        "fields": fields,
        "methods": methods,
        "enum_members": enum_members,
    }


def module_contract(source: str) -> dict[str, Any]:
    """Extract a JSON-compatible public shape without importing the module."""
    tree = ast.parse(source)
    exports: list[str] | None = None
    saw_all = False
    functions: dict[str, dict[str, Any]] = {}
    classes: dict[str, dict[str, Any]] = {}
    imports: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[node.name] = _signature(node)
        elif isinstance(node, ast.ClassDef):
            classes[node.name] = _class_contract(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
                saw_all = True
                value = node.value
                try:
                    candidate = ast.literal_eval(value) if value is not None else None
                except (ValueError, TypeError):
                    candidate = None
                if not isinstance(candidate, (list, tuple)) or not all(
                    isinstance(item, str) for item in candidate
                ):
                    raise ContractExtractionError("module must use a literal __all__")
                exports = list(candidate)

    if saw_all and exports is None:
        raise ContractExtractionError("module must use a literal __all__")
    return {
        "exports": exports,
        "imports": sorted(imports),
        "functions": functions,
        "classes": classes,
    }
