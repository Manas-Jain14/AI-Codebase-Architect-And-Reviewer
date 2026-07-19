from __future__ import annotations

import ast
import datetime as dt
import os
import zipfile
from pathlib import Path
from typing import Any


ROUTE_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
    "trace",
}

DATABASE_IMPORT_PREFIXES = (
    "sqlalchemy",
    "asyncpg",
    "psycopg",
    "databases",
)


def safe_extract_zip(zip_path: str | Path, destination_dir: str | Path) -> Path:
    """Extract a ZIP file safely into a destination directory."""

    zip_path = Path(zip_path)
    destination_dir = Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute():
                raise ValueError(f"Unsafe absolute path in ZIP: {member.filename}")

            resolved_target = (destination_dir / member_path).resolve()
            resolved_root = destination_dir.resolve()
            if resolved_root not in resolved_target.parents and resolved_target != resolved_root:
                raise ValueError(f"Unsafe path traversal in ZIP: {member.filename}")

        archive.extractall(destination_dir)

    return destination_dir


def analyze_structure(project_root: str | Path) -> dict[str, Any]:
    project_root = Path(project_root)

    total_files = 0
    total_folders = 0
    python_files: list[str] = []

    for path in sorted(project_root.rglob("*")):
        if path.is_dir():
            total_folders += 1
            continue

        total_files += 1
        if path.suffix == ".py":
            python_files.append(str(path.relative_to(project_root)).replace(os.sep, "/"))

    file_tree = _build_file_tree(project_root)

    return {
        "file_tree": file_tree,
        "total_files": total_files,
        "total_folders": total_folders,
        "python_files": python_files,
    }


def analyze_entrypoints(project_root: str | Path) -> list[dict[str, Any]]:
    project_root = Path(project_root)
    entry_points: list[dict[str, Any]] = []

    for python_file in sorted(project_root.rglob("*.py")):
        tree = _parse_python_file(python_file)
        if tree is None:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue

            if _is_main_guard(node.test):
                entry_points.append(
                    {
                        "file": _relative_path(project_root, python_file),
                        "kind": "main_guard",
                        "line": node.lineno,
                    }
                )

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            if _is_uvicorn_run(node):
                entry_points.append(
                    {
                        "file": _relative_path(project_root, python_file),
                        "kind": "uvicorn_run",
                        "line": node.lineno,
                    }
                )

    return entry_points


def analyze_imports(project_root: str | Path) -> dict[str, Any]:
    project_root = Path(project_root)
    python_files = sorted(project_root.rglob("*.py"))
    internal_modules = _build_internal_module_index(project_root, python_files)

    imports_by_file: dict[str, list[dict[str, Any]]] = {}
    dependency_graph: dict[str, list[str]] = {}

    for python_file in python_files:
        tree = _parse_python_file(python_file)
        if tree is None:
            continue

        file_key = _relative_path(project_root, python_file)
        imports_by_file[file_key] = []
        dependency_graph[file_key] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    resolved = _resolve_import(module_name, internal_modules)
                    imports_by_file[file_key].append(
                        {
                            "name": module_name,
                            "alias": alias.asname,
                            "resolved": resolved,
                            "line": node.lineno,
                        }
                    )
                    if resolved is not None:
                        dependency_graph[file_key].append(resolved)

            elif isinstance(node, ast.ImportFrom):
                module_name = _resolve_from_module(node, python_file, project_root)
                for alias in node.names:
                    imported_name = f"{module_name}.{alias.name}" if module_name else alias.name
                    resolved = _resolve_import(imported_name, internal_modules)
                    imports_by_file[file_key].append(
                        {
                            "name": imported_name,
                            "alias": alias.asname,
                            "resolved": resolved,
                            "line": node.lineno,
                        }
                    )
                    if resolved is not None:
                        dependency_graph[file_key].append(resolved)

    for source_file, targets in dependency_graph.items():
        deduplicated_targets = sorted(set(targets))
        dependency_graph[source_file] = deduplicated_targets

    return {
        "imports": imports_by_file,
        "dependency_graph": dependency_graph,
    }


def analyze_functions(project_root: str | Path) -> list[dict[str, Any]]:
    project_root = Path(project_root)
    functions: list[dict[str, Any]] = []

    for python_file in sorted(project_root.rglob("*.py")):
        tree = _parse_python_file(python_file)
        if tree is None:
            continue

        visitor = _DefinitionVisitor(project_root, python_file)
        visitor.visit(tree)
        functions.extend(visitor.functions)

    return functions


def analyze_classes(project_root: str | Path) -> list[dict[str, Any]]:
    project_root = Path(project_root)
    classes: list[dict[str, Any]] = []

    for python_file in sorted(project_root.rglob("*.py")):
        tree = _parse_python_file(python_file)
        if tree is None:
            continue

        visitor = _DefinitionVisitor(project_root, python_file)
        visitor.visit(tree)
        classes.extend(visitor.classes)

    return classes


def analyze_api_routes(project_root: str | Path) -> list[dict[str, Any]]:
    project_root = Path(project_root)
    api_routes: list[dict[str, Any]] = []

    for python_file in sorted(project_root.rglob("*.py")):
        tree = _parse_python_file(python_file)
        if tree is None:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for decorator in node.decorator_list:
                route_info = _extract_route_info(decorator)
                if route_info is None:
                    continue

                api_routes.append(
                    {
                        "file": _relative_path(project_root, python_file),
                        "function": node.name,
                        "path": route_info["path"],
                        "methods": route_info["methods"],
                        "line": node.lineno,
                    }
                )

    return api_routes


def analyze_database_usage(project_root: str | Path) -> dict[str, Any]:
    project_root = Path(project_root)
    usage: dict[str, dict[str, Any]] = {}

    for python_file in sorted(project_root.rglob("*.py")):
        tree = _parse_python_file(python_file)
        if tree is None:
            continue

        file_key = _relative_path(project_root, python_file)
        imports: list[str] = []
        operations: list[dict[str, Any]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(DATABASE_IMPORT_PREFIXES):
                        imports.append(alias.name)

            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                if module_name.startswith(DATABASE_IMPORT_PREFIXES):
                    imports.append(module_name)

            elif isinstance(node, ast.Call):
                call_name = _get_call_name(node.func)
                if call_name is None:
                    continue

                if any(
                    call_name.endswith(suffix)
                    for suffix in (".execute", ".commit", ".add", ".add_all", ".refresh", ".rollback", ".fetchone", ".fetchall")
                ):
                    operations.append(
                        {
                            "name": call_name,
                            "line": node.lineno,
                        }
                    )

        if imports or operations:
            usage[file_key] = {
                "imports": sorted(set(imports)),
                "operations": operations,
            }

    return {
        "files": usage,
    }


def analyze_function_calls(project_root: str | Path) -> dict[str, Any]:
    """Analyze function calls within the project.
    
    Returns a mapping of function names to the functions they call.
    """
    project_root = Path(project_root)
    function_calls: dict[str, list[str]] = {}

    for python_file in sorted(project_root.rglob("*.py")):
        tree = _parse_python_file(python_file)
        if tree is None:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            function_name = node.name
            calls: list[str] = []

            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    call_name = _get_call_name(child.func)
                    if call_name is not None and call_name not in calls:
                        calls.append(call_name)

            if calls:
                function_calls[function_name] = sorted(set(calls))

    return {
        "function_calls": function_calls,
    }


def build_context(project_root: str | Path, project_name: str | None = None) -> dict[str, Any]:
    project_root = Path(project_root)
    structure = analyze_structure(project_root)
    import_info = analyze_imports(project_root)
    function_call_info = analyze_function_calls(project_root)

    context = {
        "project_name": project_name or project_root.name,
        "file_tree": structure["file_tree"],
        "total_files": structure["total_files"],
        "total_folders": structure["total_folders"],
        "python_files": structure["python_files"],
        "imports": import_info["imports"],
        "dependency_graph": import_info["dependency_graph"],
        "functions": analyze_functions(project_root),
        "classes": analyze_classes(project_root),
        "api_routes": analyze_api_routes(project_root),
        "database_usage": analyze_database_usage(project_root),
        "entry_points": analyze_entrypoints(project_root),
        "function_calls": function_call_info["function_calls"],
        "analysis_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    return context


def _build_file_tree(path: Path) -> dict[str, Any]:
    children: list[dict[str, Any]] = []

    for child in sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
        node = {
            "name": child.name,
            "path": str(child.relative_to(path)).replace(os.sep, "/"),
            "type": "directory" if child.is_dir() else "file",
        }
        if child.is_dir():
            node["children"] = _build_file_tree(child)["children"]
        children.append(node)

    return {
        "name": path.name,
        "path": ".",
        "type": "directory",
        "children": children,
    }


def _parse_python_file(python_file: Path) -> ast.AST | None:
    try:
        return ast.parse(python_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None


def _relative_path(project_root: Path, path: Path) -> str:
    return str(path.relative_to(project_root)).replace(os.sep, "/")


def _build_internal_module_index(project_root: Path, python_files: list[Path]) -> dict[str, str]:
    module_index: dict[str, str] = {}

    for python_file in python_files:
        relative_path = python_file.relative_to(project_root)
        module_name = _path_to_module_name(relative_path)
        if module_name:
            module_index[module_name] = _relative_path(project_root, python_file)

    return module_index


def _path_to_module_name(relative_path: Path) -> str:
    parts = list(relative_path.parts)
    if not parts:
        return ""

    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].removesuffix(".py")

    parts = [part for part in parts if part]
    return ".".join(parts)


def _resolve_import(module_name: str, internal_modules: dict[str, str]) -> str | None:
    if module_name in internal_modules:
        return internal_modules[module_name]

    parts = module_name.split(".")
    while len(parts) > 1:
        parts.pop()
        candidate = ".".join(parts)
        if candidate in internal_modules:
            return internal_modules[candidate]

    return None


def _resolve_from_module(node: ast.ImportFrom, python_file: Path, project_root: Path) -> str:
    module = node.module or ""
    if node.level == 0:
        return module

    current_module = _path_to_module_name(python_file.relative_to(project_root))
    current_parts = current_module.split(".") if current_module else []

    base_parts = current_parts[:-node.level] if node.level <= len(current_parts) else []

    if module:
        base_parts.extend(module.split("."))

    return ".".join(part for part in base_parts if part)


def _is_main_guard(test: ast.AST) -> bool:
    if not isinstance(test, ast.Compare):
        return False

    if not isinstance(test.left, ast.Name) or test.left.id != "__name__":
        return False

    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False

    if len(test.comparators) != 1:
        return False

    comparator = test.comparators[0]
    return isinstance(comparator, ast.Constant) and comparator.value == "__main__"


def _is_uvicorn_run(node: ast.Call) -> bool:
    call_name = _get_call_name(node.func)
    if call_name is None:
        return False

    return call_name.endswith("uvicorn.run") or call_name == "run"


def _extract_route_info(decorator: ast.AST) -> dict[str, Any] | None:
    if not isinstance(decorator, ast.Call):
        return None

    func_name = _get_call_name(decorator.func)
    if func_name is None:
        return None

    route_name = func_name.split(".")[-1]
    if route_name not in ROUTE_METHODS and route_name != "api_route":
        return None

    path = None
    if decorator.args:
        first_arg = decorator.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            path = first_arg.value

    methods: list[str]
    if route_name == "api_route":
        methods = _extract_methods_kwarg(decorator)
    else:
        methods = [route_name.upper()]

    return {
        "path": path or "/",
        "methods": methods,
    }


def _extract_methods_kwarg(decorator: ast.Call) -> list[str]:
    for keyword in decorator.keywords:
        if keyword.arg != "methods":
            continue

        if isinstance(keyword.value, (ast.List, ast.Tuple)):
            methods: list[str] = []
            for element in keyword.value.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    methods.append(element.value.upper())
            if methods:
                return methods

    return ["GET"]


def _get_call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parent = _get_call_name(node.value)
        if parent is None:
            return node.attr
        return f"{parent}.{node.attr}"

    return None


class _DefinitionVisitor(ast.NodeVisitor):
    def __init__(self, project_root: Path, python_file: Path) -> None:
        self.project_root = project_root
        self.python_file = python_file
        self.class_stack: list[str] = []
        self.functions: list[dict[str, Any]] = []
        self.classes: list[dict[str, Any]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._record_function(node, is_async=False)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._record_function(node, is_async=True)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        class_name = node.name
        bases = [_get_call_name(base) or _describe_ast(base) for base in node.bases]
        self.classes.append(
            {
                "file": _relative_path(self.project_root, self.python_file),
                "name": class_name,
                "bases": bases,
                "methods": [],
                "line": node.lineno,
            }
        )

        self.class_stack.append(class_name)
        self.generic_visit(node)
        self.class_stack.pop()

    def _record_function(self, node: ast.AST, *, is_async: bool) -> None:
        function_name = getattr(node, "name", "")
        current_class = self.class_stack[-1] if self.class_stack else None
        parameters = _extract_parameters(node)
        function_info = {
            "file": _relative_path(self.project_root, self.python_file),
            "name": function_name,
            "class": current_class,
            "is_async": is_async,
            "parameters": parameters,
            "line": getattr(node, "lineno", None),
        }
        self.functions.append(function_info)

        if current_class is not None:
            for class_info in reversed(self.classes):
                if class_info["name"] == current_class and class_info["file"] == function_info["file"]:
                    class_info["methods"].append(function_name)
                    break


def _extract_parameters(node: ast.AST) -> list[str]:
    arguments = getattr(node, "args", None)
    if arguments is None:
        return []

    parameters: list[str] = []
    for argument in arguments.posonlyargs:
        parameters.append(argument.arg)
    for argument in arguments.args:
        parameters.append(argument.arg)
    if arguments.vararg is not None:
        parameters.append(f"*{arguments.vararg.arg}")
    for argument in arguments.kwonlyargs:
        parameters.append(argument.arg)
    if arguments.kwarg is not None:
        parameters.append(f"**{arguments.kwarg.arg}")

    return parameters


def _describe_ast(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        return repr(node.value)
    return node.__class__.__name__
