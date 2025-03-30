from typing import Any, List, Optional
import json
import logging
from datetime import datetime

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

# Настройка логгера
logger = logging.getLogger("app.chat")
logger.setLevel(logging.INFO)
# Настройка вывода логов в файл и консоль
if not logger.handlers:
    file_handler = logging.FileHandler("chat_messages.log")
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

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
        logger.info(f"WebSocket connection attempt: user_id={user.id}, incident_id={incident_id}")
    except HTTPException as e:
        logger.warning(f"WebSocket auth failed: token={token[:10]}..., error={str(e)}")
        await websocket.close(code=1008)  # Policy violation (invalid token)
        return
    
    # Check if the incident exists and user has access
    incident = await get_incident(db, id=incident_id)
    if not incident:
        logger.warning(f"WebSocket incident not found: incident_id={incident_id}, user_id={user.id}")
        await websocket.close(code=1011)  # Internal error (incident not found)
        return
    
    # Check if user has access to the incident
    if user.role == "citizen" and incident.user_id != user.id:
        logger.warning(f"WebSocket access denied: incident_id={incident_id}, user_id={user.id}, role={user.role}")
        await websocket.close(code=1008)  # Policy violation (no permission)
        return
    
    # Accept connection
    await websocket.accept()
    logger.info(f"WebSocket connected: user_id={user.id}, incident_id={incident_id}, role={user.role}")
    
    # Register connection
    await chat_manager.connect(websocket, user.id, incident_id, is_police=(user.role == "responder"))
    
    try:
        # Handle messages
        while True:
            data = await websocket.receive_json()
            logger.info(f"WebSocket message received: user_id={user.id}, incident_id={incident_id}, data={json.dumps(data)}")
            
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
                
                logger.info(f"New chat message stored: id={message.id}, user_id={user.id}, incident_id={incident_id}, content={message.content}")
                
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
                logger.info(f"Message broadcast: message_id={message.id}, incident_id={incident_id}")
            
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
                logger.debug(f"Typing indicator: user_id={user.id}, incident_id={incident_id}, is_typing={data.get('is_typing', False)}")
    
    except WebSocketDisconnect:
        # Handle disconnection
        logger.info(f"WebSocket disconnected: user_id={user.id}, incident_id={incident_id}")
        chat_manager.disconnect(websocket, user.id, incident_id)
    
    except Exception as e:
        # Log the error
        logger.error(f"WebSocket error: user_id={user.id}, incident_id={incident_id}, error={str(e)}")
        await websocket.close(code=1011)  # Internal error 


@router.get("/chat/admin/incidents/{incident_id}/messages", response_model=List[ChatMessage])
async def admin_get_incident_messages(
    incident_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get all messages for a specific incident (admin access).
    """
    # Check admin permission
    if current_user.role != "admin" and current_user.role != "responder":
        logger.warning(f"Unauthorized admin access: user_id={current_user.id}, role={current_user.role}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Only admin and responders can access this endpoint",
        )
    
    # Check if the incident exists
    incident = await get_incident(db, id=incident_id)
    if not incident:
        logger.warning(f"Admin incident not found: incident_id={incident_id}, user_id={current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    
    # Get all messages for the incident
    messages = await get_incident_messages(db, incident_id=incident_id)
    logger.info(f"Admin retrieved messages: incident_id={incident_id}, user_id={current_user.id}, count={len(messages)}")
    return messages


@router.get("/chat/admin/stats", response_model=dict)
async def admin_get_chat_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get statistics about WebSocket connections and messages.
    """
    # Check admin permission
    if current_user.role != "admin":
        logger.warning(f"Unauthorized stats access: user_id={current_user.id}, role={current_user.role}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Only admin can access this endpoint",
        )
    
    # Get connection statistics
    active_incidents = len(chat_manager.active_connections)
    active_users = len(chat_manager.user_connections)
    active_police = len(chat_manager.police_connections)
    
    incidents_with_connections = list(chat_manager.active_connections.keys())
    users_with_connections = list(chat_manager.user_connections.keys())
    
    stats = {
        "active_incidents": active_incidents,
        "active_users": active_users,
        "active_police": active_police,
        "incidents_with_connections": incidents_with_connections,
        "users_with_connections": users_with_connections,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.info(f"Admin retrieved stats: user_id={current_user.id}, stats={json.dumps(stats)}")
    return stats

@router.websocket("/ws/chat/admin/monitor")
async def admin_monitor_websocket(
    websocket: WebSocket,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket для администратора, получающего все сообщения чата в реальном времени.
    """
    # Аутентификация администратора
    try:
        user = await get_current_user(db, token=token)
        if user.role != "admin":
            logger.warning(f"WebSocket admin monitor access denied: user_id={user.id}, role={user.role}")
            await websocket.close(code=1008)
            return
        logger.info(f"Admin monitor connected: user_id={user.id}")
    except HTTPException as e:
        logger.warning(f"WebSocket admin auth failed: error={str(e)}")
        await websocket.close(code=1008)
        return
    
    # Принять соединение
    await websocket.accept()
    
    # Создаем специальный обработчик для перехвата всех сообщений
    async def message_handler(message: dict):
        try:
            # Добавляем метку времени и информацию о том, что это мониторинг
            message["admin_monitor"] = True
            message["monitor_timestamp"] = datetime.utcnow().isoformat()
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Admin monitor send error: {str(e)}")
    
    # Регистрируем обработчик в Redis или другом механизме
    # Внимание: это упрощенная реализация, в реальном приложении вам понадобится
    # настроить Redis pub/sub для всех сообщений чата
    
    try:
        # В простом варианте просто держим соединение открытым
        # В реальном приложении здесь должна быть подписка на Redis
        while True:
            # Получаем пинг от клиента и отвечаем
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
    except WebSocketDisconnect:
        logger.info(f"Admin monitor disconnected: user_id={user.id}")
    except Exception as e:
        logger.error(f"Admin monitor error: user_id={user.id}, error={str(e)}")
        await websocket.close(code=1011) 

@router.post("/chat/admin/send-test-message", response_model=ChatMessage)
async def admin_send_test_message(
    incident_id: int,
    message: str,
    sender_type: str = "system",  # system, admin, test
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Send a test message to a chat as admin/system.
    """
    # Check admin permission
    if current_user.role != "admin":
        logger.warning(f"Unauthorized test message: user_id={current_user.id}, role={current_user.role}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Only admin can access this endpoint",
        )
    
    # Check if the incident exists
    incident = await get_incident(db, id=incident_id)
    if not incident:
        logger.warning(f"Test message incident not found: incident_id={incident_id}, user_id={current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    
    # Create message with special prefix
    prefix = {
        "system": "[СИСТЕМА] ",
        "admin": "[АДМИН] ",
        "test": "[ТЕСТ] ",
    }.get(sender_type, "[ТЕСТ] ")
    
    message_data = ChatMessageCreate(
        content=f"{prefix}{message}",
        incident_id=incident_id,
    )
    
    # Save message to database
    created_message = await create_chat_message(
        db, obj_in=message_data, sender_id=current_user.id
    )
    
    logger.info(f"Admin sent test message: incident_id={incident_id}, user_id={current_user.id}, content={message}")
    
    # Broadcast to all connected clients for this incident
    await chat_manager.broadcast_message(
        incident_id=incident_id,
        message={
            "type": "new_message",
            "data": {
                "id": created_message.id,
                "content": created_message.content,
                "sender_id": created_message.sender_id,
                "sent_at": created_message.sent_at.isoformat(),
                "is_read": created_message.is_read,
                "is_system_message": True,
                "sender_type": sender_type
            }
        }
    )
    
    return created_message 