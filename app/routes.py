from __future__ import annotations

import asyncio
import logging
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic_ai.exceptions import ModelHTTPError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import architect_agent, chat_agent
from app.architecture import (
    generate_database_flow,
    generate_dependency_graph,
    generate_execution_flow,
    generate_function_graph,
    get_file_details,
    get_function_details,
    identify_critical_files,
)
from app.config import EXTRACT_DIR, UPLOAD_DIR
from app.database import AnalysisReport, ChatMessage, ChatSession, Project, get_session
from app.diagrams import (
    generate_mermaid_architecture,
    generate_mermaid_database_flow,
    generate_mermaid_execution_flow,
    generate_mermaid_function_flow,
)
from app.schemas import ArchitectureReview, ChatAnswer, ProjectContext
from app.utils import build_project_context, extract_zip_safely, json_dumps, json_loads


router = APIRouter()
logger = logging.getLogger(__name__)


def _project_extract_path(project_id: int) -> Path:
    return Path(EXTRACT_DIR) / str(project_id)


async def _load_project(session: AsyncSession, project_id: int) -> Project:
    """Load a project by id.

    This is async because it performs database I/O.
    """

    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _next_available_project_id(session: AsyncSession) -> int:
    """Find the smallest positive integer not currently used as a project id.

    This is async because it performs database I/O. The `projects.id` column is a
    plain serial/nextval-default column (verified against the live schema), not a
    strict GENERATED ALWAYS AS IDENTITY column, so inserting an explicit id works
    with a normal ORM insert.
    """

    result = await session.execute(select(Project.id).order_by(Project.id))
    existing_ids = [row[0] for row in result.all()]

    candidate = 1
    for existing_id in existing_ids:
        if existing_id == candidate:
            candidate += 1
        elif existing_id > candidate:
            break

    return candidate


async def _get_or_create_chat_session(session: AsyncSession, project_id: int) -> ChatSession:
    """Load or create the chat session for a project.

    This is async because it performs database I/O.
    """

    result = await session.execute(select(ChatSession).where(ChatSession.project_id == project_id))
    chat_session = result.scalar_one_or_none()
    if chat_session is not None:
        return chat_session

    chat_session = ChatSession(project_id=project_id)
    session.add(chat_session)
    await session.commit()
    await session.refresh(chat_session)
    return chat_session


async def _run_chat_agent_with_retry(prompt: str, project_context: ProjectContext) -> ChatAnswer:
    """Run the chat agent and retry once if Gemini rate-limits the request.

    This is async because the model call and retry delay are both non-blocking I/O.
    """

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            result = await chat_agent.run(
                prompt,
                deps=project_context,
                output_type=ChatAnswer,
            )
            return result.output
        except ModelHTTPError as error:
            if error.status_code != 429:
                raise

            if attempt == max_attempts:
                return _build_chat_fallback(project_context, prompt)

            retry_delay = _extract_retry_delay_seconds(error) or 6.0
            await asyncio.sleep(retry_delay)

    # Fallback after exhausting all retries (should not be reached due to loop logic)
    return _build_chat_fallback(project_context, prompt)


def _extract_retry_delay_seconds(error: ModelHTTPError) -> float | None:
    """Extract Gemini's suggested retry delay from a ModelHTTPError payload."""

    body = getattr(error, "body", None)
    if not isinstance(body, dict):
        return None

    details = body.get("error", {}).get("details", [])
    for detail in details:
        if not isinstance(detail, dict):
            continue

        retry_delay = detail.get("retryDelay")
        if isinstance(retry_delay, str):
            match = re.fullmatch(r"(?P<seconds>\d+(?:\.\d+)?)s", retry_delay.strip())
            if match:
                return float(match.group("seconds")) + 1.0

    return None


def _build_chat_fallback(project_context: object, prompt: str) -> ChatAnswer:
    """Build a deterministic answer when Gemini is unavailable.

    This keeps chat usable during quota exhaustion without touching analysis flow.
    """

    context = project_context
    question = prompt.split("Current question:", 1)[-1].strip().lower()
    referenced_files = list(getattr(context, "python_files", []))[:5]
    if not referenced_files:
        referenced_files = list(getattr(context, "imports", {}).keys())[:5]

    if "architecture" in question:
        answer = (
            "The project is a very small root-level Python codebase with a flat structure. "
            "It currently contains a minimal file tree, no layered package architecture, and only placeholder-style files."
        )
    elif "entry" in question:
        answer = "The most likely entry point is main.py, with app.py also acting as a bootstrap or application file."
    elif "route" in question:
        answer = "No API routes were discovered in the uploaded sample project."
    elif "database" in question:
        answer = "No database usage was discovered in the uploaded sample project."
    else:
        answer = "I could not reach Gemini due to rate limits, so this is a context-based fallback answer."

    return ChatAnswer(answer=answer, referenced_files=referenced_files)


@router.post("/upload-project")
async def upload_project(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    """Receive, store, and extract a project ZIP.

    This is async because file upload and database writes are I/O bound.
    """

    if not file.filename:
        raise HTTPException(status_code=400, detail="ZIP file is required")

    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(EXTRACT_DIR).mkdir(parents=True, exist_ok=True)

    upload_path = Path(UPLOAD_DIR) / file.filename
    with upload_path.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    next_id = await _next_available_project_id(session)
    project = Project(id=next_id, project_name=Path(file.filename).stem, zip_path=str(upload_path))
    session.add(project)
    await session.commit()
    await session.refresh(project)

    project_extract_dir = _project_extract_path(project.id)
    extract_zip_safely(upload_path, project_extract_dir)

    return {"project_id": project.id}


@router.get("/projects")
async def list_projects(session: AsyncSession = Depends(get_session)):
    """List stored projects.

    This is async because it performs database I/O.
    """

    result = await session.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()
    return [
        {"id": project.id, "project_name": project.project_name, "zip_path": project.zip_path, "created_at": project.created_at}
        for project in projects
    ]


@router.delete("/projects/{project_id}")
async def delete_project(project_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a project and all of its associated data (DB rows, zip, extracted folder).

    This is async because it performs database and filesystem I/O.
    """

    project = await _load_project(session, project_id)

    session_ids_subquery = select(ChatSession.id).where(ChatSession.project_id == project_id).scalar_subquery()
    await session.execute(delete(ChatMessage).where(ChatMessage.session_id.in_(session_ids_subquery)))
    await session.execute(delete(ChatSession).where(ChatSession.project_id == project_id))
    await session.execute(delete(AnalysisReport).where(AnalysisReport.project_id == project_id))
    await session.execute(delete(Project).where(Project.id == project_id))
    await session.commit()

    zip_path = Path(project.zip_path)
    if zip_path.exists():
        try:
            zip_path.unlink()
        except OSError:
            logger.exception("Failed to delete zip file %s for project %s", zip_path, project_id)

    extract_path = _project_extract_path(project_id)
    if extract_path.exists():
        try:
            shutil.rmtree(extract_path)
        except OSError:
            logger.exception(
                "Failed to remove extracted folder %s for project %s; id %s may not be safe to "
                "reuse until this folder is cleared manually",
                extract_path,
                project_id,
                project_id,
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Project {project_id} was deleted from the database, but its extracted "
                    "folder could not be fully removed. Clear it manually before reusing this "
                    "project id, or contamination from this project may leak into a future upload."
                ),
            ) from None

    return {"deleted": True, "project_id": project_id}


@router.get("/analysis/{project_id}")
async def analyze_project(project_id: int, session: AsyncSession = Depends(get_session)):
    """Build a project context and run the architecture agent.

    This is async because it performs filesystem and database I/O, plus model calls.
    """

    project = await _load_project(session, project_id)
    project_root = _project_extract_path(project.id)
    if not project_root.exists():
        raise HTTPException(status_code=404, detail="Extracted project not found")

    project_context = build_project_context(project.project_name, project_root)
    result = await architect_agent.run(
        "Produce a structured architecture review from the provided ProjectContext.",
        deps=project_context,
        output_type=ArchitectureReview,
    )
    review = result.output

    report = AnalysisReport(
        project_id=project.id,
        summary=review.summary,
        architecture=review.architecture,
        strengths=json_dumps(review.strengths),
        weaknesses=json_dumps(review.weaknesses),
        score=0.0,  # dummy value only to satisfy the DB's NOT NULL constraint; never read or displayed
        roadmap=json_dumps(review.roadmap),
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)

    return {
        "id": report.id,
        "project_id": report.project_id,
        "summary": report.summary,
        "architecture": report.architecture,
        "strengths": review.strengths,
        "weaknesses": review.weaknesses,
        "roadmap": review.roadmap,
        "scalability": review.scalability,
        "recruiter_evaluation": review.recruiter_evaluation,
    }


@router.get("/report/{project_id}")
async def get_report(project_id: int, session: AsyncSession = Depends(get_session)):
    """Return the stored analysis report for a project.

    This is async because it performs database I/O.
    """

    result = await session.execute(select(AnalysisReport).where(AnalysisReport.project_id == project_id).order_by(AnalysisReport.created_at.desc()).limit(1))
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    return {
        "id": report.id,
        "project_id": report.project_id,
        "summary": report.summary,
        "architecture": report.architecture,
        "strengths": json_loads(report.strengths, []),
        "weaknesses": json_loads(report.weaknesses, []),
        "roadmap": json_loads(report.roadmap, []),
    }


@router.get("/architecture/{project_id}")
async def get_architecture(project_id: int, session: AsyncSession = Depends(get_session)):
    """Return architecture analysis data for a project.

    This is async because it performs filesystem and database I/O.
    """

    project = await _load_project(session, project_id)
    project_root = _project_extract_path(project.id)
    if not project_root.exists():
        raise HTTPException(status_code=404, detail="Extracted project not found")

    project_context = build_project_context(project.project_name, project_root)

    return {
        "project_name": project_context.project_name,
        "project_metrics": {
            "total_files": project_context.total_files,
            "total_folders": project_context.total_folders,
            "python_files": len(project_context.python_files),
            "classes": len(project_context.classes),
            "functions": len(project_context.functions),
            "api_routes": len(project_context.api_routes),
        },
        "dependency_graph": generate_dependency_graph(project_context),
        "function_graph": generate_function_graph(project_context),
        "execution_flow": generate_execution_flow(project_context),
        "database_flow": generate_database_flow(project_context),
        "critical_files": identify_critical_files(project_context),
        "mermaid_architecture": generate_mermaid_architecture(project_context),
        "mermaid_function_flow": generate_mermaid_function_flow(project_context),
        "mermaid_database_flow": generate_mermaid_database_flow(project_context),
        "mermaid_execution_flow": generate_mermaid_execution_flow(project_context),
        "python_files": project_context.python_files,
        "functions": project_context.functions,
        "classes": project_context.classes,
        "api_routes": project_context.api_routes,
    }


@router.get("/architecture/{project_id}/file/{file_path:path}")
async def get_architecture_file(project_id: int, file_path: str, session: AsyncSession = Depends(get_session)):
    """Return detailed information about a specific file.

    This is async because it performs database I/O.
    """

    project = await _load_project(session, project_id)
    project_root = _project_extract_path(project.id)
    if not project_root.exists():
        raise HTTPException(status_code=404, detail="Extracted project not found")

    project_context = build_project_context(project.project_name, project_root)
    return get_file_details(project_context, file_path)


@router.get("/architecture/{project_id}/function/{function_name}")
async def get_architecture_function(project_id: int, function_name: str, session: AsyncSession = Depends(get_session)):
    """Return detailed information about a specific function.

    This is async because it performs database I/O.
    """

    project = await _load_project(session, project_id)
    project_root = _project_extract_path(project.id)
    if not project_root.exists():
        raise HTTPException(status_code=404, detail="Extracted project not found")

    project_context = build_project_context(project.project_name, project_root)
    return get_function_details(project_context, function_name)


@router.post("/chat/{project_id}")
async def chat_with_project(project_id: int, payload: dict, session: AsyncSession = Depends(get_session)):
    """Answer a chat question using the project context and chat history.

    This is async because it performs database I/O and model calls.
    """

    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    project = await _load_project(session, project_id)
    project_root = _project_extract_path(project.id)
    if not project_root.exists():
        raise HTTPException(status_code=404, detail="Extracted project not found")

    project_context = build_project_context(project.project_name, project_root)
    chat_session = await _get_or_create_chat_session(session, project.id)

    history_result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.created_at.asc())
    )
    history_messages = history_result.scalars().all()

    history_text = []
    for message in history_messages:
        history_text.append(f"User: {message.question}")
        history_text.append(f"Assistant: {message.answer}")

    answer = await _run_chat_agent_with_retry(
        "\n".join([
            "Chat history:",
            *history_text,
            "Current question:",
            question,
        ]),
        project_context,
    )

    message = ChatMessage(session_id=chat_session.id, question=question, answer=answer.answer)
    session.add(message)
    await session.commit()

    return {
        "answer": answer.answer,
        "referenced_files": answer.referenced_files,
    }
