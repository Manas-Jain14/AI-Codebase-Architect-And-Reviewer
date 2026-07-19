from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProjectContext(BaseModel):
    project_name: str
    file_tree: dict[str, Any]
    total_files: int
    total_folders: int
    python_files: list[str]
    imports: dict[str, Any]
    dependency_graph: dict[str, list[str]]
    functions: list[dict[str, Any]]
    classes: list[dict[str, Any]]
    api_routes: list[dict[str, Any]]
    database_usage: dict[str, Any]
    entry_points: list[dict[str, Any]]
    function_calls: dict[str, list[str]]
    analysis_timestamp: str


class ArchitectureReview(BaseModel):
    summary: str
    architecture: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    score: float
    scalability: str
    recruiter_evaluation: str
    roadmap: list[str] = Field(default_factory=list)


class ChatAnswer(BaseModel):
    answer: str
    referenced_files: list[str] = Field(default_factory=list)
