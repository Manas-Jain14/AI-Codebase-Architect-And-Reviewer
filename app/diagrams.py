from __future__ import annotations

from collections import deque

from app.schemas import ProjectContext

MAX_FANOUT_PER_FILE = 3


def generate_mermaid_architecture(context: ProjectContext) -> str:
    """Generate a layered, role-based Mermaid diagram of file dependencies.

    Files are grouped into tiers by their shortest real distance (BFS) from the
    project's entry points, so a shared utility imported from many places still gets
    one clear tier instead of being duplicated across the diagram. Edges are the real
    dependency_graph edges (not a synthetic chain), capped to a small fan-out per file
    so the diagram stays readable.
    """
    dependency_graph = context.dependency_graph
    if not any(dependency_graph.values()):
        return 'graph TD\n    app["Application"]'

    tiers, disconnected = _compute_tiers(context)
    edges = _select_capped_edges(dependency_graph, MAX_FANOUT_PER_FILE)

    lines = ["graph TD"]

    max_tier = max(tiers.values()) if tiers else 0
    for tier_index in range(max_tier + 1):
        files_in_tier = sorted(file_path for file_path, tier in tiers.items() if tier == tier_index)
        if not files_in_tier:
            continue

        label = "Entry Points" if tier_index == 0 else f"Layer {tier_index}"
        subgraph_id = _node_id(f"tier_{tier_index}")
        lines.append(f'    subgraph {subgraph_id}["{label}"]')
        for file_path in files_in_tier:
            lines.append(f'        {_node_id(file_path)}["{_short_label(file_path)}"]')
        lines.append("    end")

    if disconnected:
        subgraph_id = _node_id("tier_disconnected")
        lines.append(f'    subgraph {subgraph_id}["Disconnected"]')
        for file_path in sorted(disconnected):
            lines.append(f'        {_node_id(file_path)}["{_short_label(file_path)}"]')
        lines.append("    end")

    for source, target in edges:
        lines.append(f'    {_node_id(source)} --> {_node_id(target)}')

    return "\n".join(lines)


def _compute_tiers(context: ProjectContext) -> tuple[dict[str, int], set[str]]:
    """Assign every file the shallowest tier (BFS distance) reachable from the
    project's entry points. Files never reached from an entry point are returned
    separately as the disconnected set."""
    dependency_graph = context.dependency_graph

    all_files: set[str] = set(dependency_graph.keys())
    for targets in dependency_graph.values():
        all_files.update(targets)

    roots = [root for root in _find_roots(context) if root]
    all_files.update(roots)

    tiers: dict[str, int] = {}
    queue: deque[str] = deque()
    for root in roots:
        if root not in tiers:
            tiers[root] = 0
            queue.append(root)

    while queue:
        current = queue.popleft()
        for target in dependency_graph.get(current, []):
            if target not in tiers:
                tiers[target] = tiers[current] + 1
                queue.append(target)

    disconnected = all_files - set(tiers.keys())
    return tiers, disconnected


def _find_roots(context: ProjectContext) -> list[str]:
    """Determine the tier-0 root files: detected entry points, or otherwise files
    that nothing else in the project depends on."""
    if context.entry_points:
        entry_files = sorted({entry.get("file") for entry in context.entry_points if entry.get("file")})
        if entry_files:
            return entry_files

    dependency_graph = context.dependency_graph
    all_files = set(dependency_graph.keys())
    depended_on = {target for targets in dependency_graph.values() for target in targets}
    roots = sorted(all_files - depended_on)
    if roots:
        return roots

    if all_files:
        return [sorted(all_files)[0]]

    return []


def _select_capped_edges(dependency_graph: dict[str, list[str]], max_fanout: int) -> list[tuple[str, str]]:
    """Keep at most max_fanout outgoing edges per file, preferring targets with the
    fewest existing incoming connections so arrows spread out instead of all piling
    onto the same one or two heavily-shared hub files."""
    in_degree: dict[str, int] = {}
    for targets in dependency_graph.values():
        for target in targets:
            in_degree[target] = in_degree.get(target, 0) + 1

    edges: list[tuple[str, str]] = []
    for source in sorted(dependency_graph.keys()):
        targets = dependency_graph[source]
        if not targets:
            continue

        ranked_targets = sorted(targets, key=lambda target: (in_degree.get(target, 0), target))
        for target in ranked_targets[:max_fanout]:
            edges.append((source, target))

    return edges


def generate_mermaid_function_flow(context: ProjectContext) -> str:
    """Generate a Mermaid diagram of call relationships between the project's own functions.

    Builtins, stdlib/library calls, and UI widget callbacks are excluded since they
    aren't functions defined in the analyzed project, and would otherwise show up as
    disconnected noise nodes.
    """
    defined_functions = {func.get("name") for func in context.functions if func.get("name")}
    func_file = {
        func.get("name"): func.get("file") or "unknown"
        for func in context.functions
        if func.get("name")
    }

    seen_edges: set[tuple[str, str]] = set()
    edges: list[tuple[str, str]] = []
    for func_name, calls in context.function_calls.items():
        if func_name not in defined_functions:
            continue
        for called_func in calls:
            if called_func not in defined_functions:
                continue
            edge = (func_name, called_func)
            if edge not in seen_edges:
                seen_edges.add(edge)
                edges.append(edge)

    if not edges:
        return (
            'graph TD\n'
            '    none["No direct calls detected between this project\'s own functions"]'
        )

    edges = edges[:40]  # Keep the diagram readable for large projects
    involved_functions = sorted({name for edge in edges for name in edge})

    files_to_functions: dict[str, list[str]] = {}
    for func_name in involved_functions:
        files_to_functions.setdefault(func_file.get(func_name, "unknown"), []).append(func_name)

    lines = ["graph TD"]
    for index, (file_name, func_names) in enumerate(sorted(files_to_functions.items())):
        subgraph_id = _node_id(f"file_{index}_{file_name}")
        lines.append(f'    subgraph {subgraph_id}["{_short_label(file_name)}"]')
        for func_name in func_names:
            lines.append(f'        {_node_id(func_name)}["{func_name}"]')
        lines.append("    end")

    for func_name, called_func in edges:
        lines.append(f'    {_node_id(func_name)} --> {_node_id(called_func)}')

    return "\n".join(lines)


def generate_mermaid_database_flow(context: ProjectContext) -> str:
    """Generate a Mermaid diagram of the analyzed project's own detected database usage.

    Derived entirely from context.database_usage (per-file DB imports and operations
    found in the project) rather than this analyzer tool's own internal schema.
    """
    db_files = context.database_usage.get("files", {})

    if not db_files:
        return 'graph TD\n    none["No database usage detected in this project"]'

    lines = ["graph TD"]
    seen_edges: set[tuple[str, str]] = set()

    for file_key, usage in list(db_files.items())[:8]:
        file_id = _node_id(file_key)
        lines.append(f'    {file_id}["{file_key}"]')

        for imp in usage.get("imports", [])[:4]:
            imp_id = _node_id(f"imp_{imp}")
            edge = (file_id, imp_id)
            if edge not in seen_edges:
                lines.append(f'    {imp_id}(["{imp}"])')
                lines.append(f'    {file_id} --> {imp_id}')
                seen_edges.add(edge)

        operation_names = sorted({op.get("name", "") for op in usage.get("operations", []) if op.get("name")})
        for op_name in operation_names[:4]:
            op_id = _node_id(f"op_{op_name}")
            edge = (file_id, op_id)
            if edge not in seen_edges:
                lines.append(f'    {op_id}{{"{op_name}"}}')
                lines.append(f'    {file_id} --> {op_id}')
                seen_edges.add(edge)

    return "\n".join(lines)


def generate_mermaid_execution_flow(context: ProjectContext) -> str:
    """Generate a Mermaid sequence diagram of the request execution lifecycle."""
    if not context.api_routes:
        return (
            "sequenceDiagram\n"
            "    participant Client\n"
            "    participant API as FastAPI Route\n"
            "    Client->>API: HTTP Request\n"
            "    API-->>Client: Response"
        )

    db_keywords = ("session", "execute", "commit", "query", "select", "insert", "update", "delete", "db")

    routes = context.api_routes[:8]  # Limit to keep the diagram readable

    participant_lines = ["    participant Client", "    participant API as FastAPI Route"]
    declared: set[str] = set()
    message_lines: list[str] = []
    uses_db = False

    for route in routes:
        handler = route.get("function") or "handler"
        path = route.get("path", "/")
        methods = route.get("methods") or ["GET"]
        method = methods[0]

        handler_id = _node_id(handler)
        if handler_id not in declared:
            participant_lines.append(f"    participant {handler_id} as {handler}")
            declared.add(handler_id)

        message_lines.append(f"    Client->>+API: {method} {path}")
        message_lines.append(f"    API->>+{handler_id}: {handler}()")

        for called in context.function_calls.get(handler, [])[:5]:
            if any(keyword in called.lower() for keyword in db_keywords):
                uses_db = True
                message_lines.append(f"    {handler_id}->>+DB: {called}()")
                message_lines.append(f"    DB-->>-{handler_id}: result")
            else:
                called_id = _node_id(called)
                if called_id not in declared:
                    participant_lines.append(f"    participant {called_id} as {called}")
                    declared.add(called_id)
                message_lines.append(f"    {handler_id}->>+{called_id}: {called}()")
                message_lines.append(f"    {called_id}-->>-{handler_id}: return")

        message_lines.append(f"    {handler_id}-->>-API: result")
        message_lines.append("    API-->>-Client: Response")

    if uses_db:
        participant_lines.insert(2, "    participant DB as Database or External API")

    lines = ["sequenceDiagram", *participant_lines, *message_lines]
    return "\n".join(lines)


def _short_label(path: str) -> str:
    """Shorten a repo-relative path to its last two segments (folder/filename.py)."""
    segments = [segment for segment in path.replace("\\", "/").split("/") if segment]
    if not segments:
        return path
    return "/".join(segments[-2:])


def _node_id(value: str) -> str:
    """Convert a string to a valid Mermaid node ID."""
    cleaned = [character if character.isalnum() else "_" for character in value]
    result = "".join(cleaned)
    if result and result[0].isdigit():
        result = f"n_{result}"
    return result or "node"
