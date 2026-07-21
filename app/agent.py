from __future__ import annotations

from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.config import GEMINI_API_KEY, MODEL_NAME
from app.schemas import ArchitectureReview, ChatAnswer, ProjectContext


provider = GoogleProvider(api_key=GEMINI_API_KEY)
shared_model = GoogleModel(MODEL_NAME, provider=provider)


def get_project_structure(ctx: RunContext[ProjectContext]) -> dict[str, Any]:
    """Return the project structure from context.

    This is sync because it only reads already-built in-memory context.
    """

    return ctx.deps.file_tree


def get_dependency_graph(ctx: RunContext[ProjectContext]) -> dict[str, list[str]]:
    """Return the dependency graph from context.

    This is sync because it only reads already-built in-memory context.
    """

    return ctx.deps.dependency_graph


def get_function_flow(ctx: RunContext[ProjectContext]) -> list[dict[str, Any]]:
    """Return function data from context.

    This is sync because it only reads already-built in-memory context.
    """

    return ctx.deps.functions


def get_api_routes(ctx: RunContext[ProjectContext]) -> list[dict[str, Any]]:
    """Return API route data from context.

    This is sync because it only reads already-built in-memory context.
    """

    return ctx.deps.api_routes


def get_database_info(ctx: RunContext[ProjectContext]) -> dict[str, Any]:
    """Return database usage data from context.

    This is sync because it only reads already-built in-memory context.
    """

    return ctx.deps.database_usage


def get_project_metrics(ctx: RunContext[ProjectContext]) -> dict[str, Any]:
    """Return project metrics from context.

    This is sync because it only reads already-built in-memory context.
    """

    return {
        "total_files": ctx.deps.total_files,
        "total_folders": ctx.deps.total_folders,
        "python_files": len(ctx.deps.python_files),
        "class_count": len(ctx.deps.classes),
        "function_count": len(ctx.deps.functions),
        "route_count": len(ctx.deps.api_routes),
    }


def generate_mermaid(ctx: RunContext[ProjectContext]) -> str:
    """Generate Mermaid graph TD syntax from the dependency graph.

    This is sync because it only formats context data into text.
    """

    lines = ["graph TD"]
    graph = ctx.deps.dependency_graph

    for source, targets in graph.items():
        source_id = _node_id(source)
        if not targets:
            lines.append(f"    {source_id}[\"{source}\"]")
            continue

        for target in targets:
            target_id = _node_id(target)
            lines.append(f"    {source_id}[\"{source}\"] --> {target_id}[\"{target}\"]")

    return "\n".join(lines)


def _node_id(value: str) -> str:
    cleaned = [character if character.isalnum() else "_" for character in value]
    result = "".join(cleaned)
    if result and result[0].isdigit():
        result = f"n_{result}"
    return result or "node"


architect_agent = Agent(
    shared_model,
    deps_type=ProjectContext,
    output_type=ArchitectureReview,
    system_prompt=(
        "You are an architecture reviewer for codebases. "
        "Never assume project structure. Use tools before drawing conclusions. "
        "Return only structured output."
    ),
    tools=[
        get_project_structure,
        get_dependency_graph,
        get_function_flow,
        get_api_routes,
        get_database_info,
        get_project_metrics,
        generate_mermaid,
    ],
)

_CHAT_SYSTEM_PROMPT = (
    "You answer questions about a codebase using only ProjectContext and tools. "
    "Never access the filesystem or raw source code directly. "
    "Be precise and concise."
)
_CHAT_TOOLS = [
    get_project_structure,
    get_dependency_graph,
    get_function_flow,
    get_api_routes,
    get_database_info,
    get_project_metrics,
    generate_mermaid,
]

chat_agent = Agent(
    shared_model,
    deps_type=ProjectContext,
    output_type=ChatAnswer,
    system_prompt=_CHAT_SYSTEM_PROMPT,
    tools=_CHAT_TOOLS,
)

# Plain-text variant used for token-by-token streaming. Gemini's structured
# (JSON-mode) output for ChatAnswer only arrives in one or two large chunks even
# under stream_output(), so it can't drive a real word-by-word UI; a plain-text
# output_type streams in genuine incremental deltas via stream_text(delta=True).
chat_agent_stream = Agent(
    shared_model,
    deps_type=ProjectContext,
    system_prompt=_CHAT_SYSTEM_PROMPT,
    tools=_CHAT_TOOLS,
)
