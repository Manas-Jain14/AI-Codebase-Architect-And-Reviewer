from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import settings


class Base(AsyncAttrs, DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine():
    settings.validate_required()
    return create_async_engine(settings.DATABASE_URL, echo=False)


@lru_cache(maxsize=1)
def get_sessionmaker():
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def init_db():
    """Create database tables for the existing SQLAlchemy metadata."""

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_name: Mapped[str] = mapped_column(String, nullable=False)
    zip_path: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    reports: Mapped[list["AnalysisReport"]] = relationship(back_populates="project")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="project")


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    architecture: Mapped[str] = mapped_column(Text, nullable=False)
    strengths: Mapped[str] = mapped_column(Text, nullable=False)
    weaknesses: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    roadmap: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    project: Mapped[Project] = relationship(back_populates="reports")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    project: Mapped[Project] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    session: Mapped[ChatSession] = relationship(back_populates="messages")


async def get_session():
    """Return an async database session.

    This is async because database I/O must not block the event loop.
    """

    async with get_sessionmaker()() as session:
        yield session


async def get_session_dependency():
    """Compatibility wrapper for FastAPI dependencies.

    This is async because it yields an async database session.
    """

    async for session in get_session():
        yield session
