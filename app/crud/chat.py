from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage
from app.schemas import ChatMessageCreate, ChatMessageUpdate, EmergencyChatCreate


async def get_chat_message(db: AsyncSession, id: int) -> Optional[ChatMessage]:
    """
    Get a chat message by ID.
    """
    result = await db.execute(select(ChatMessage).filter(ChatMessage.id == id))
    return result.scalars().first()


async def get_incident_messages(
    db: AsyncSession, incident_id: int, skip: int = 0, limit: int = 100
) -> List[ChatMessage]:
    """
    Get all chat messages for a specific incident.
    """
    result = await db.execute(
        select(ChatMessage)
        .filter(ChatMessage.incident_id == incident_id)
        .order_by(ChatMessage.sent_at.asc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def create_chat_message(
    db: AsyncSession, obj_in: ChatMessageCreate, sender_id: int
) -> ChatMessage:
    """
    Create a new chat message.
    """
    db_obj = ChatMessage(
        content=obj_in.content,
        sender_id=sender_id,
        incident_id=obj_in.incident_id,
        is_emergency=obj_in.is_emergency,
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def create_emergency_message(
    db: AsyncSession, obj_in: EmergencyChatCreate, sender_id: int
) -> ChatMessage:
    """
    Create an emergency chat message.
    """
    # Create a placeholder incident_id for emergency messages
    # In a real app, you might handle this differently
    db_obj = ChatMessage(
        content=obj_in.content,
        sender_id=sender_id,
        incident_id=1,  # Placeholder, would be handled differently in a real app
        is_emergency=True,
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def update_chat_message(
    db: AsyncSession, db_obj: ChatMessage, obj_in: Union[ChatMessageUpdate, Dict[str, Any]]
) -> ChatMessage:
    """
    Update a chat message.
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


async def mark_messages_as_read(
    db: AsyncSession, incident_id: int, user_id: int
) -> None:
    """
    Mark all messages in an incident as read for a specific user.
    Only marks messages sent by other users.
    """
    stmt = (
        update(ChatMessage)
        .where(
            and_(
                ChatMessage.incident_id == incident_id,
                ChatMessage.sender_id != user_id,
                ChatMessage.is_read == False,
            )
        )
        .values(is_read=True)
    )
    await db.execute(stmt)
    await db.commit() 