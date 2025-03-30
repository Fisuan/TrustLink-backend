from typing import Any, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import get_current_active_user, get_current_police_user
from app.db.session import get_db
from app.models import User, Incident, IncidentStatus
from app.schemas import Incident as IncidentSchema
from app.schemas import IncidentCreate, IncidentUpdate, IncidentDetail
from app.crud.incident import (
    get_incident,
    get_incidents,
    get_user_incidents,
    create_incident,
    update_incident,
    delete_incident
)

router = APIRouter()


@router.post("/incidents", response_model=IncidentSchema)
async def create_new_incident(
    incident_in: IncidentCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create new incident.
    """
    incident = await create_incident(db, obj_in=incident_in, user_id=current_user.id)
    return incident


@router.get("/incidents", response_model=List[IncidentSchema])
async def read_incidents(
    skip: int = 0,
    limit: int = 100,
    status: str = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Retrieve incidents.
    Citizens can only see their own incidents, police can see all.
    """
    if current_user.role == "citizen":
        incidents = await get_user_incidents(
            db, user_id=current_user.id, skip=skip, limit=limit, status=status
        )
    else:
        incidents = await get_incidents(db, skip=skip, limit=limit, status=status)
    return incidents


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
async def read_incident(
    incident_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get incident by ID.
    Citizens can only get their own incidents, police can get any.
    """
    incident = await get_incident(db, id=incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    if current_user.role == "citizen" and incident.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return incident


@router.put("/incidents/{incident_id}", response_model=IncidentSchema)
async def update_incident_status(
    incident_id: int,
    incident_in: IncidentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update an incident.
    Citizens can only update their own incidents, and only certain fields.
    Police can update any incident.
    """
    incident = await get_incident(db, id=incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    
    # Check permissions
    if current_user.role == "citizen":
        if incident.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        # Citizens can't update status
        if incident_in.status is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Citizens can't update incident status",
            )
    
    incident = await update_incident(db, db_obj=incident, obj_in=incident_in)
    return incident


@router.delete("/incidents/{incident_id}", response_model=IncidentSchema)
async def delete_incident_by_id(
    incident_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Delete an incident.
    Citizens can only delete their own incidents, and only if they're in REPORTED status.
    Police can delete any incident.
    """
    incident = await get_incident(db, id=incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    
    # Check permissions
    if current_user.role == "citizen":
        if incident.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        if incident.status != IncidentStatus.REPORTED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only delete incidents in 'reported' status",
            )
    
    incident = await delete_incident(db, id=incident_id)
    return incident


# Классы для экстренных ситуаций и отчетов
class EmergencyRequest(BaseModel):
    message: str
    location: dict = None
    address: str = None
    media: dict = None
    timestamp: str = None

class ReportRequest(BaseModel):
    title: str
    description: str
    location: dict = None
    address: str = None
    media: dict = None
    timestamp: str = None

@router.post("/incidents/emergency", response_model=dict)
async def create_emergency(
    emergency: EmergencyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Создать экстренное сообщение и инцидент.
    """
    # Создаем инцидент с высоким приоритетом
    incident_data = IncidentCreate(
        title="ЭКСТРЕННАЯ СИТУАЦИЯ",
        description=emergency.message,
        status="urgent",
        location=emergency.address or "Неизвестное местоположение",
        priority="high",
        incident_type="emergency",
    )
    
    # Сохраняем инцидент
    incident = await create_incident(db, obj_in=incident_data, user_id=current_user.id)
    
    # Создаем сообщение чата с экстренным уведомлением
    from app.schemas import ChatMessageCreate
    from app.crud.chat import create_chat_message
    
    message_data = ChatMessageCreate(
        content=f"[ЭКСТРЕННОЕ СООБЩЕНИЕ] {emergency.message}",
        incident_id=incident.id,
        is_emergency=True,
    )
    
    message = await create_chat_message(db, obj_in=message_data, sender_id=current_user.id)
    
    # Отправляем уведомление всем операторам через WebSocket
    from app.services.websocket_manager import chat_manager
    
    await chat_manager.broadcast_to_police(
        message={
            "type": "emergency",
            "data": {
                "incident_id": incident.id,
                "message": emergency.message,
                "user_id": current_user.id,
                "user_name": current_user.full_name or "Пользователь",
                "location": emergency.address,
                "timestamp": emergency.timestamp or datetime.utcnow().isoformat(),
                "has_media": emergency.media is not None,
            }
        }
    )
    
    # Возвращаем информацию об инциденте
    return {
        "success": True,
        "incident_id": incident.id,
        "message": "Экстренное сообщение отправлено",
        "status": "urgent",
    }


@router.post("/incidents/report", response_model=dict)
async def create_report(
    report: ReportRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Создать отчет о происшествии.
    """
    # Создаем инцидент
    incident_data = IncidentCreate(
        title=report.title,
        description=report.description,
        status="new",
        location=report.address or "Неизвестное местоположение",
        priority="medium",
        incident_type="report",
    )
    
    # Сохраняем инцидент
    incident = await create_incident(db, obj_in=incident_data, user_id=current_user.id)
    
    # Создаем сообщение чата с отчетом
    from app.schemas import ChatMessageCreate
    from app.crud.chat import create_chat_message
    
    message_data = ChatMessageCreate(
        content=f"[ОТЧЕТ] {report.description}",
        incident_id=incident.id,
    )
    
    message = await create_chat_message(db, obj_in=message_data, sender_id=current_user.id)
    
    # Возвращаем информацию об инциденте
    return {
        "success": True,
        "incident_id": incident.id,
        "message": "Отчет отправлен",
        "status": "new",
    } 