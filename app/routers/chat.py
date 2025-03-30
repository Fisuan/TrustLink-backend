from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_user
from app.db.session import get_db
from app.models import User, Incident
from app.schemas import ChatMessage, ChatMessageCreate, ChatMessageUpdate, EmergencyChatCreate
from app.crud.chat import (
    get_chat_message,
    get_incident_messages,
    create_chat_message,
    update_chat_message,
    mark_messages_as_read,
    create_emergency_message,
)
from app.crud.incident import get_incident
from app.services.websocket_manager import chat_manager

router = APIRouter()


@router.post("/chat/messages", response_model=ChatMessage)
async def create_message(
    message_in: ChatMessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create a new chat message.
    """
    # Check if the incident exists and user has access
    incident = await get_incident(db, id=message_in.incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    
    # Check if user has access to the incident
    if current_user.role == "citizen" and incident.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Create message
    message = await create_chat_message(
        db, obj_in=message_in, sender_id=current_user.id
    )
    
    # Broadcast message to connected clients
    await chat_manager.broadcast_message(
        incident_id=message.incident_id,
        message={
            "type": "new_message",
            "data": {
                "id": message.id,
                "content": message.content,
                "sender_id": message.sender_id,
                "sent_at": message.sent_at.isoformat(),
                "is_read": message.is_read,
                "is_emergency": message.is_emergency,
            }
        }
    )
    
    return message


@router.post("/chat/emergency", response_model=ChatMessage)
async def create_emergency_chat(
    message_in: EmergencyChatCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create an emergency chat message.
    These messages are not tied to a specific incident and are for emergencies.
    """
    # Create emergency message
    message = await create_emergency_message(
        db, obj_in=message_in, sender_id=current_user.id
    )
    
    # Broadcast to police users (in a real app, would need to identify which police to notify)
    await chat_manager.broadcast_to_police(
        message={
            "type": "emergency",
            "data": {
                "id": message.id,
                "content": message.content,
                "sender_id": message.sender_id,
                "sender_name": current_user.full_name,
                "sent_at": message.sent_at.isoformat(),
            }
        }
    )
    
    return message


@router.get("/chat/incidents/{incident_id}/messages", response_model=List[ChatMessage])
async def read_incident_messages(
    incident_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Retrieve chat messages for a specific incident.
    Citizens can only see messages for their own incidents, police can see all.
    """
    # Check if the incident exists and user has access
    incident = await get_incident(db, id=incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    
    # Check if user has access to the incident
    if current_user.role == "citizen" and incident.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Get messages
    messages = await get_incident_messages(db, incident_id=incident_id, skip=skip, limit=limit)
    
    # Mark messages as read if the user is not the sender
    await mark_messages_as_read(db, incident_id=incident_id, user_id=current_user.id)
    
    return messages


@router.put("/chat/messages/{message_id}", response_model=ChatMessage)
async def update_message_status(
    message_id: int,
    message_in: ChatMessageUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update a chat message (mark as read).
    """
    message = await get_chat_message(db, id=message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    
    # Only receiver can mark as read
    if message.sender_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User cannot mark their own messages as read",
        )
    
    # For citizens, check if they have access to the incident
    incident = await get_incident(db, id=message.incident_id)
    if current_user.role == "citizen" and incident.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Update message
    message = await update_chat_message(db, db_obj=message, obj_in=message_in)
    
    # Notify the sender that the message was read
    await chat_manager.send_message_to_user(
        user_id=message.sender_id,
        message={
            "type": "message_read",
            "data": {
                "message_id": message.id,
                "read_by": current_user.id,
            }
        }
    )
    
    return message


@router.websocket("/ws/chat/{incident_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    incident_id: int,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for real-time chat.
    """
    # Authenticate user
    try:
        user = await get_current_user(db, token=token)
    except HTTPException:
        await websocket.close(code=1008)  # Policy violation (invalid token)
        return
    
    # Check if the incident exists and user has access
    incident = await get_incident(db, id=incident_id)
    if not incident:
        await websocket.close(code=1011)  # Internal error (incident not found)
        return
    
    # Check if user has access to the incident
    if user.role == "citizen" and incident.user_id != user.id:
        await websocket.close(code=1008)  # Policy violation (no permission)
        return
    
    # Accept connection
    await websocket.accept()
    
    # Register connection
    await chat_manager.connect(websocket, user.id, incident_id)
    
    try:
        # Handle messages
        while True:
            data = await websocket.receive_json()
            
            # Process message based on type
            if data.get("type") == "message":
                # Create a new message in the database
                message_data = ChatMessageCreate(
                    content=data.get("content", ""),
                    incident_id=incident_id,
                )
                message = await create_chat_message(
                    db, obj_in=message_data, sender_id=user.id
                )
                
                # Broadcast to all connected clients for this incident
                await chat_manager.broadcast_message(
                    incident_id=incident_id,
                    message={
                        "type": "new_message",
                        "data": {
                            "id": message.id,
                            "content": message.content,
                            "sender_id": message.sender_id,
                            "sent_at": message.sent_at.isoformat(),
                            "is_read": message.is_read,
                        }
                    },
                    exclude=websocket,  # Don't send back to sender
                )
            
            elif data.get("type") == "typing":
                # Broadcast typing indicator
                await chat_manager.broadcast_message(
                    incident_id=incident_id,
                    message={
                        "type": "typing",
                        "data": {
                            "user_id": user.id,
                            "is_typing": data.get("is_typing", False),
                        }
                    },
                    exclude=websocket,  # Don't send back to sender
                )
    
    except WebSocketDisconnect:
        # Handle disconnection
        chat_manager.disconnect(websocket, user.id, incident_id)
    
    except Exception as e:
        # Log the error
        print(f"WebSocket error: {str(e)}")
        await websocket.close(code=1011)  # Internal error 