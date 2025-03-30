from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Incident, IncidentStatus
from app.schemas import IncidentCreate, IncidentUpdate


async def get_incident(db: AsyncSession, id: int) -> Optional[Incident]:
    """
    Get an incident by ID.
    """
    result = await db.execute(select(Incident).filter(Incident.id == id))
    return result.scalars().first()


async def get_incidents(
    db: AsyncSession, skip: int = 0, limit: int = 100, status: Optional[str] = None
) -> List[Incident]:
    """
    Get multiple incidents with optional filtering by status.
    """
    query = select(Incident)
    if status:
        query = query.filter(Incident.status == status)
    
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


async def get_user_incidents(
    db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100, status: Optional[str] = None
) -> List[Incident]:
    """
    Get incidents created by a specific user.
    """
    query = select(Incident).filter(Incident.user_id == user_id)
    if status:
        query = query.filter(Incident.status == status)
    
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


async def create_incident(
    db: AsyncSession, obj_in: IncidentCreate, user_id: int
) -> Incident:
    """
    Create a new incident.
    """
    db_obj = Incident(
        type=obj_in.type,
        title=obj_in.title,
        description=obj_in.description,
        location_lat=obj_in.location_lat,
        location_lng=obj_in.location_lng,
        location_address=obj_in.location_address,
        status=IncidentStatus.REPORTED,
        user_id=user_id,
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def update_incident(
    db: AsyncSession, db_obj: Incident, obj_in: Union[IncidentUpdate, Dict[str, Any]]
) -> Incident:
    """
    Update an incident.
    """
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    
    for field in update_data:
        if update_data[field] is not None:
            setattr(db_obj, field, update_data[field])
    
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def delete_incident(db: AsyncSession, id: int) -> Incident:
    """
    Delete an incident.
    """
    incident = await get_incident(db, id=id)
    await db.delete(incident)
    await db.commit()
    return incident 