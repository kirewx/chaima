"""Service layer for Project entities (group-scoped)."""
from uuid import UUID

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.project import Project


async def create_project(
    session: AsyncSession, *, group_id: UUID, name: str
) -> Project:
    """Create a project, or return existing case-insensitive match."""
    trimmed = name.strip()
    existing = (
        await session.exec(
            select(Project).where(
                Project.group_id == group_id,
                func.lower(Project.name) == trimmed.lower(),
            )
        )
    ).first()
    if existing is not None:
        return existing
    project = Project(group_id=group_id, name=trimmed)
    session.add(project)
    await session.flush()
    return project


async def list_projects(
    session: AsyncSession, *, group_id: UUID, include_archived: bool = False
) -> list[Project]:
    stmt = select(Project).where(Project.group_id == group_id)
    if not include_archived:
        stmt = stmt.where(Project.is_archived == False)  # noqa: E712
    stmt = stmt.order_by(Project.name)
    return list((await session.exec(stmt)).all())


async def get_project(session: AsyncSession, project_id: UUID) -> Project | None:
    return await session.get(Project, project_id)


async def update_project(
    session: AsyncSession, project: Project, *, name: str | None = None
) -> Project:
    if name is not None:
        project.name = name.strip()
    session.add(project)
    await session.flush()
    return project


async def archive_project(session: AsyncSession, project: Project) -> Project:
    project.is_archived = True
    session.add(project)
    await session.flush()
    return project
