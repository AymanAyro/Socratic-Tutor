import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.Content import Project
from Models.Schemas import ProjectCreateRequest, ProjectOut
from database import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Project).order_by(Project.created_at.asc()))).scalars().all()
    return [ProjectOut.model_validate(r) for r in rows]


@router.post("", response_model=ProjectOut)
async def create_project(body: ProjectCreateRequest, db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(Project).where(Project.name == body.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Project name already exists")
    p = Project(id=uuid.uuid4(), name=body.name, created_at=datetime.now(timezone.utc))
    db.add(p)
    await db.flush()
    return ProjectOut.model_validate(p)


@router.delete("/{project_id}")
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(p)
    return {"deleted": str(project_id)}
