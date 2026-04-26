"""Router for Project management endpoints."""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from chaima.dependencies import GroupAdminDep, GroupMemberDep, SessionDep
from chaima.schemas.pagination import PaginatedResponse
from chaima.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from chaima.services import projects as project_service

router = APIRouter(
    prefix="/api/v1/groups/{group_id}/projects", tags=["projects"]
)


@router.get("", response_model=PaginatedResponse[ProjectRead])
async def list_projects(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    include_archived: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> PaginatedResponse[ProjectRead]:
    items = await project_service.list_projects(
        session, group_id=group_id, include_archived=include_archived
    )
    page = items[offset : offset + limit]
    return PaginatedResponse(
        items=[ProjectRead.model_validate(p) for p in page],
        total=len(items),
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    group_id: UUID,
    body: ProjectCreate,
    session: SessionDep,
    member: GroupMemberDep,
) -> ProjectRead:
    project = await project_service.create_project(
        session, group_id=group_id, name=body.name
    )
    await session.commit()
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    group_id: UUID,
    project_id: UUID,
    body: ProjectUpdate,
    session: SessionDep,
    admin: GroupAdminDep,
) -> ProjectRead:
    project = await project_service.get_project(session, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if body.name is not None:
        await project_service.update_project(session, project, name=body.name)
    if body.is_archived is True:
        await project_service.archive_project(session, project)
    if body.is_archived is False:
        project.is_archived = False
        session.add(project)
    await session.commit()
    return ProjectRead.model_validate(project)


@router.post("/{project_id}/archive", response_model=ProjectRead)
async def archive_project(
    group_id: UUID,
    project_id: UUID,
    session: SessionDep,
    admin: GroupAdminDep,
) -> ProjectRead:
    project = await project_service.get_project(session, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    await project_service.archive_project(session, project)
    await session.commit()
    return ProjectRead.model_validate(project)
