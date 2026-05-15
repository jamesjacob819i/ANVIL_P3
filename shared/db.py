import os
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional, Any

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Column, String, JSON, DateTime, Text, select

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://sentinel:sentinel123@localhost:5432/sentinel",
)


class Base(DeclarativeBase):
    pass


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class EventRecord(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(64))
    parent_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    topic: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(64))
    agent_name: Mapped[str] = mapped_column(String(64))
    input_json: Mapped[dict] = mapped_column(JSON)
    output_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def save_incident(
    incident_id: str, alert_payload: dict, session: Optional[AsyncSession] = None
) -> Incident:
    async def _do(s: AsyncSession):
        inc = Incident(
            id=incident_id,
            alert_payload=alert_payload,
            status="open",
        )
        s.add(inc)
        return inc

    if session:
        return await _do(session)
    async with get_session() as s:
        return await _do(s)


async def save_event(
    event_id: str,
    incident_id: str,
    parent_event_id: Optional[str],
    topic: str,
    payload: dict,
    session: Optional[AsyncSession] = None,
) -> EventRecord:
    async def _do(s: AsyncSession):
        rec = EventRecord(
            id=event_id,
            incident_id=incident_id,
            parent_event_id=parent_event_id,
            topic=topic,
            payload_json=payload,
        )
        s.add(rec)
        return rec

    if session:
        return await _do(session)
    async with get_session() as s:
        return await _do(s)


async def save_agent_run(
    agent_run_id: str,
    incident_id: str,
    agent_name: str,
    input_data: dict,
    session: Optional[AsyncSession] = None,
) -> AgentRun:
    async def _do(s: AsyncSession):
        run = AgentRun(
            id=agent_run_id,
            incident_id=incident_id,
            agent_name=agent_name,
            input_json=input_data,
            status="running",
        )
        s.add(run)
        return run

    if session:
        return await _do(session)
    async with get_session() as s:
        return await _do(s)


async def complete_agent_run(
    agent_run_id: str,
    output_data: dict,
    status: str = "completed",
    session: Optional[AsyncSession] = None,
) -> None:
    async def _do(s: AsyncSession):
        result = await s.execute(select(AgentRun).where(AgentRun.id == agent_run_id))
        run = result.scalar_one_or_none()
        if run:
            run.output_json = output_data
            run.status = status
            run.ended_at = datetime.now(timezone.utc)

    if session:
        return await _do(session)
    async with get_session() as s:
        return await _do(s)


async def get_open_incidents(session: Optional[AsyncSession] = None) -> list[Incident]:
    async def _do(s: AsyncSession):
        result = await s.execute(
            select(Incident).where(Incident.status == "open")
        )
        return result.scalars().all()

    if session:
        return await _do(session)
    async with get_session() as s:
        return await _do(s)


async def update_incident_status(
    incident_id: str,
    status: str,
    session: Optional[AsyncSession] = None,
) -> None:
    async def _do(s: AsyncSession):
        result = await s.execute(select(Incident).where(Incident.id == incident_id))
        inc = result.scalar_one_or_none()
        if inc:
            inc.status = status
            if status in ("resolved", "closed"):
                inc.resolved_at = datetime.now(timezone.utc)

    if session:
        return await _do(session)
    async with get_session() as s:
        return await _do(s)


async def get_incident_events(
    incident_id: str, session: Optional[AsyncSession] = None
) -> list[EventRecord]:
    async def _do(s: AsyncSession):
        result = await s.execute(
            select(EventRecord)
            .where(EventRecord.incident_id == incident_id)
            .order_by(EventRecord.created_at)
        )
        return result.scalars().all()

    if session:
        return await _do(session)
    async with get_session() as s:
        return await _do(s)
