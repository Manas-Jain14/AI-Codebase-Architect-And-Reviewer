from __future__ import annotations

from app.schemas import ProjectContext


def generate_mermaid_architecture(context: ProjectContext) -> str:
    """Generate a Mermaid diagram of file dependencies."""
    lines = ["graph TD"]

    # Add nodes and edges from dependency graph
    seen_edges: set[tuple[str, str]] = set()
    for source, targets in context.dependency_graph.items():
        for target in targets[:5]:  # Limit to 5 dependencies per file
            edge = (source, target)
            if edge not in seen_edges:
                source_id = _node_id(source)
                target_id = _node_id(target)
                lines.append(f'    {source_id}["{source}"] --> {target_id}["{target}"]')
                seen_edges.add(edge)

    if len(lines) == 1:  # Only graph TD, no edges
        lines.append('    app["Application"]')

    return "\n".join(lines)


def generate_mermaid_function_flow(context: ProjectContext) -> str:
    """Generate a Mermaid diagram of function call flows."""
    lines = ["graph TD"]

    # Get the most important functions (those with the most calls)
    important_funcs = sorted(
        context.function_calls.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:10]

    seen_edges: set[tuple[str, str]] = set()
    for func_name, calls in important_funcs:
        for called_func in calls[:3]:  # Limit to 3 calls per function
            edge = (func_name, called_func)
            if edge not in seen_edges:
                func_id = _node_id(func_name)
                called_id = _node_id(called_func)
                lines.append(f'    {func_id}["{func_name}"] --> {called_id}["{called_func}"]')
                seen_edges.add(edge)

    if len(lines) == 1:  # Only graph TD, no edges
        lines.append('    start["Program Start"]')

    return "\n".join(lines)


def generate_mermaid_database_flow(context: ProjectContext) -> str:
    """Generate a Mermaid diagram of database interactions."""
    lines = ["graph TD"]

    # Map database operations to tables
    db_ops = context.database_usage.get("files", {})

    # Define table nodes
    tables = ["projects", "analysis_reports", "chat_sessions", "chat_messages"]
    for table in tables:
        table_id = _node_id(f"tbl_{table}")
        lines.append(f'    {table_id}["{table} Table"]')

    # Add relationships
    for file_key, usage in list(db_ops.items())[:5]:
        file_id = _node_id(file_key)
        lines.append(f'    {file_id}["{file_key}"]')

        # Link to tables based on operations
        ops = usage.get("operations", [])
        for op in ops:
            op_name = op.get("name", "")
            if any(keyword in op_name for keyword in ["execute", "commit", "add"]):
                # Assume all DB operations interact with analysis_reports for simplicity
                table_id = _node_id("tbl_analysis_reports")
                lines.append(f'    {file_id} --> {table_id}')
                break

    if len(lines) <= len(tables) + 1:  # Only table nodes, no connections
        lines.append('    app["Application"] --> tbl_projects["projects Table"]')

    return "\n".join(lines)


def _node_id(value: str) -> str:
    """Convert a string to a valid Mermaid node ID."""
    cleaned = [character if character.isalnum() else "_" for character in value]
    result = "".join(cleaned)
    if result and result[0].isdigit():
        result = f"n_{result}"
    return result or "node"
