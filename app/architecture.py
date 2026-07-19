from __future__ import annotations

from typing import Any

from app.schemas import ProjectContext


def generate_dependency_graph(context: ProjectContext) -> dict[str, Any]:
    """Generate file-to-file dependency relationships."""
    return {
        "files": context.dependency_graph,
        "total_files": len(context.dependency_graph),
    }


def generate_function_graph(context: ProjectContext) -> dict[str, Any]:
    """Generate function-to-function call relationships."""
    return {
        "function_calls": context.function_calls,
        "total_functions": len(context.functions),
    }


def generate_execution_flow(context: ProjectContext) -> list[dict[str, Any]]:
    """Generate execution flow for API routes.
    
    Maps each route to its handler function and the functions it calls.
    """
    flow: list[dict[str, Any]] = []

    for route in context.api_routes:
        route_func = route.get("function")
        if not route_func:
            continue

        called_functions = context.function_calls.get(route_func, [])
        flow.append(
            {
                "route": route.get("path", "/"),
                "methods": route.get("methods", []),
                "handler": route_func,
                "calls": called_functions,
            }
        )

    return flow


def generate_database_flow(context: ProjectContext) -> dict[str, Any]:
    """Generate database table to function relationships."""
    return {
        "database_usage": context.database_usage,
        "tables": ["projects", "analysis_reports", "chat_sessions", "chat_messages"],
    }


def identify_critical_files(context: ProjectContext) -> dict[str, list[str]]:
    """Identify critical files by their role in the architecture."""
    critical: dict[str, list[str]] = {
        "entry_point": [],
        "api_layer": [],
        "database_layer": [],
        "ai_layer": [],
        "analysis_layer": [],
    }

    # Categorize files based on naming patterns and content
    for py_file in context.python_files:
        if py_file in ["main.py"]:
            critical["entry_point"].append(py_file)
        elif py_file in ["routes.py"]:
            critical["api_layer"].append(py_file)
        elif py_file in ["database.py"]:
            critical["database_layer"].append(py_file)
        elif py_file in ["agent.py"]:
            critical["ai_layer"].append(py_file)
        elif py_file in ["analyzers.py"]:
            critical["analysis_layer"].append(py_file)

    return critical


def get_file_details(context: ProjectContext, file_path: str) -> dict[str, Any]:
    """Get detailed information about a specific file."""
    details: dict[str, Any] = {
        "file": file_path,
        "functions": [],
        "classes": [],
        "imports": [],
        "imported_by": [],
        "api_routes": [],
        "database_usage": None,
    }

    # Get functions in this file
    for func in context.functions:
        if func.get("file") == file_path:
            details["functions"].append(
                {
                    "name": func.get("name"),
                    "line": func.get("line"),
                    "is_async": func.get("is_async"),
                }
            )

    # Get classes in this file
    for cls in context.classes:
        if cls.get("file") == file_path:
            details["classes"].append(
                {
                    "name": cls.get("name"),
                    "line": cls.get("line"),
                    "methods": cls.get("methods"),
                }
            )

    # Get imports from this file
    if file_path in context.imports:
        details["imports"] = context.imports[file_path]

    # Get files that import this file
    for source, targets in context.dependency_graph.items():
        if file_path in targets:
            details["imported_by"].append(source)

    # Get API routes in this file
    for route in context.api_routes:
        if route.get("file") == file_path:
            details["api_routes"].append(
                {
                    "path": route.get("path"),
                    "methods": route.get("methods"),
                    "function": route.get("function"),
                }
            )

    # Get database usage in this file
    db_info = context.database_usage.get("files", {})
    if file_path in db_info:
        details["database_usage"] = db_info[file_path]

    return details


def get_function_details(context: ProjectContext, function_name: str) -> dict[str, Any]:
    """Get detailed information about a specific function."""
    details: dict[str, Any] = {
        "name": function_name,
        "file": None,
        "line": None,
        "is_async": False,
        "calls": context.function_calls.get(function_name, []),
        "called_by": [],
        "parameters": [],
        "class": None,
    }

    # Find the function definition
    for func in context.functions:
        if func.get("name") == function_name:
            details["file"] = func.get("file")
            details["line"] = func.get("line")
            details["is_async"] = func.get("is_async", False)
            details["parameters"] = func.get("parameters", [])
            details["class"] = func.get("class")
            break

    # Find all functions that call this function
    for other_func, calls in context.function_calls.items():
        if function_name in calls:
            details["called_by"].append(other_func)

    return details
