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
from pydantic import BaseModel

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


async def generate_auto_response(message_content: str, incident_type: str = None) -> str:
    """
    Генерирует автоматический ответ на сообщение пользователя.
    """
    message_content = message_content.lower()
    
    # Экстренные сообщения
    if any(word in message_content for word in ["помогите", "срочно", "экстренно", "помощь", "спасите", "нападение", "насилие", "угроза"]):
        return "[АВТООТВЕТЧИК] Ваше сообщение передано оператору службы экстренной помощи. Оставайтесь на связи, оператор ответит вам в ближайшее время."
    
    # Запросы о статусе
    if any(word in message_content for word in ["статус", "состояние", "обновление", "новости", "как дела"]):
        return "[АВТООТВЕТЧИК] Ваше обращение в обработке. Оператор ответит вам как можно скорее."
    
    # Благодарности
    if any(word in message_content for word in ["спасибо", "благодарю", "отлично", "хорошо", "круто", "здорово"]):
        return "[АВТООТВЕТЧИК] Рады быть полезными! Если у вас возникнут дополнительные вопросы, не стесняйтесь обращаться."
    
    # Приветствия
    if any(word in message_content for word in ["привет", "здравствуйте", "добрый день", "доброе утро", "добрый вечер", "здравствуй"]):
        return "[АВТООТВЕТЧИК] Здравствуйте! Чем мы можем вам помочь?"
    
    # Общий ответ по умолчанию
    return "[АВТООТВЕТЧИК] Спасибо за ваше сообщение. Оператор ответит вам в ближайшее время."


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
                message_content = data.get("content", "")
                
                # Create a new message in the database
                message_data = ChatMessageCreate(
                    content=message_content,
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
                
                # Отправляем автоматический ответ, если пользователь - гражданин
                if user.role == "citizen":
                    # Генерируем ответ
                    auto_response = await generate_auto_response(message_content, incident.incident_type)
                    
                    # Создаем сообщение от системы
                    auto_message_data = ChatMessageCreate(
                        content=auto_response,
                        incident_id=incident_id,
                    )
                    
                    # Используем ID системного пользователя или создаем специальный ID для автоответчика
                    system_user_id = 1  # Предполагается, что у системного пользователя ID = 1
                    
                    auto_message = await create_chat_message(
                        db, obj_in=auto_message_data, sender_id=system_user_id
                    )
                    
                    # Отправляем автоответ всем клиентам (включая отправителя)
                    await chat_manager.broadcast_message(
                        incident_id=incident_id,
                        message={
                            "type": "new_message",
                            "data": {
                                "id": auto_message.id,
                                "content": auto_message.content,
                                "sender_id": system_user_id,
                                "sent_at": auto_message.sent_at.isoformat(),
                                "is_read": False,
                                "is_system_message": True,
                            }
                        }
                    )
                    
                    logger.info(f"Auto-response sent: message_id={auto_message.id}, incident_id={incident_id}, response={auto_response}")
            
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

@router.websocket("/ws/admin/monitor")
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

class TestMessageRequest(BaseModel):
    incident_id: int
    message: str
    sender_type: str = "system"  # system, admin, test

@router.post("/chat/admin/send-test-message", response_model=ChatMessage)
async def admin_send_test_message(
    request: TestMessageRequest,
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
    incident = await get_incident(db, id=request.incident_id)
    if not incident:
        logger.warning(f"Test message incident not found: incident_id={request.incident_id}, user_id={current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    
    # Create message with special prefix
    prefix = {
        "system": "[СИСТЕМА] ",
        "admin": "[АДМИН] ",
        "test": "[ТЕСТ] ",
    }.get(request.sender_type, "[ТЕСТ] ")
    
    message_data = ChatMessageCreate(
        content=f"{prefix}{request.message}",
        incident_id=request.incident_id,
    )
    
    # Save message to database
    created_message = await create_chat_message(
        db, obj_in=message_data, sender_id=current_user.id
    )
    
    logger.info(f"Admin sent test message: incident_id={request.incident_id}, user_id={current_user.id}, content={request.message}")
    
    # Broadcast to all connected clients for this incident
    await chat_manager.broadcast_message(
        incident_id=request.incident_id,
        message={
            "type": "new_message",
            "data": {
                "id": created_message.id,
                "content": created_message.content,
                "sender_id": created_message.sender_id,
                "sent_at": created_message.sent_at.isoformat(),
                "is_read": created_message.is_read,
                "is_system_message": True,
                "sender_type": request.sender_type
            }
        }
    )
    
    return created_message

@router.get("/chat/admin/check", response_model=dict)
async def admin_check_access(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Проверка доступа к админским функциям.
    """
    response = {
        "access": current_user.role in ["admin", "responder"],
        "role": current_user.role,
        "user_id": current_user.id,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if current_user.role not in ["admin", "responder"]:
        logger.warning(f"Admin check failed: user_id={current_user.id}, role={current_user.role}")
    else:
        logger.info(f"Admin check successful: user_id={current_user.id}, role={current_user.role}")
    
    return response 

# Простой класс для получения токена оператора
class OperatorLoginRequest(BaseModel):
    email: str
    password: str

# Упрощенный класс для отправки сообщения
class OperatorMessageRequest(BaseModel):
    incident_id: int
    message: str
    operator_name: str = "Оператор"

@router.post("/chat/operator/login", response_model=dict)
async def operator_login(
    request: OperatorLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Простой логин для операторов, возвращает токен.
    """
    from app.crud.user import authenticate_user
    from app.core.security import create_access_token
    from datetime import timedelta
    from app.core.config import settings
    
    # Аутентификация оператора
    user = await authenticate_user(db, email=request.email, password=request.password)
    if not user:
        logger.warning(f"Operator login failed: email={request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    
    # Проверка, что пользователь - оператор или админ
    if user.role not in ["responder", "admin"]:
        logger.warning(f"Non-operator tried to login: email={request.email}, role={user.role}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для операторов",
        )
    
    # Создание токена
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    
    logger.info(f"Operator logged in: id={user.id}, email={request.email}")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "role": user.role,
        "name": user.full_name,
    }

@router.get("/chat/operator/incidents", response_model=List[dict])
async def get_operator_incidents(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Получить список всех инцидентов для оператора.
    """
    try:
        # Проверяем токен
        user = await get_current_user(db, token=token)
        if user.role not in ["responder", "admin"]:
            logger.warning(f"Unauthorized incidents access: user_id={user.id}, role={user.role}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ только для операторов",
            )
        
        # Получаем все инциденты
        from app.crud.incident import get_incidents
        incidents = await get_incidents(db)
        
        # Преобразуем в формат для отображения
        result = []
        for incident in incidents:
            result.append({
                "id": incident.id,
                "title": incident.title,
                "description": incident.description,
                "status": incident.status,
                "user_id": incident.user_id,
                "created_at": incident.created_at.isoformat(),
                "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
                "location": incident.location,
                "has_unread_messages": False,  # В будущем можно добавить проверку
            })
        
        logger.info(f"Operator retrieved incidents: user_id={user.id}, count={len(result)}")
        return result
    
    except HTTPException as e:
        logger.warning(f"Token validation failed: {str(e)}")
        raise
    
    except Exception as e:
        logger.error(f"Error retrieving incidents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении инцидентов",
        )

@router.get("/chat/operator/incidents/{incident_id}/messages", response_model=List[dict])
async def get_operator_incident_messages(
    incident_id: int,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Получить сообщения для конкретного инцидента (для оператора).
    """
    try:
        # Проверяем токен
        user = await get_current_user(db, token=token)
        if user.role not in ["responder", "admin"]:
            logger.warning(f"Unauthorized messages access: user_id={user.id}, role={user.role}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ только для операторов",
            )
        
        # Проверяем существование инцидента
        incident = await get_incident(db, id=incident_id)
        if not incident:
            logger.warning(f"Incident not found: incident_id={incident_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Инцидент не найден",
            )
        
        # Получаем сообщения
        messages = await get_incident_messages(db, incident_id=incident_id)
        
        # Форматируем сообщения
        result = []
        from app.crud.user import get_user
        for message in messages:
            # Получаем информацию о пользователе (можно оптимизировать)
            sender = await get_user(db, id=message.sender_id)
            sender_name = sender.full_name if sender else "Неизвестный"
            
            result.append({
                "id": message.id,
                "content": message.content,
                "sender_id": message.sender_id,
                "sender_name": sender_name,
                "sender_role": sender.role if sender else "unknown",
                "sent_at": message.sent_at.isoformat(),
                "is_read": message.is_read,
            })
        
        logger.info(f"Operator retrieved messages: user_id={user.id}, incident_id={incident_id}, count={len(result)}")
        return result
    
    except HTTPException as e:
        logger.warning(f"Token validation failed: {str(e)}")
        raise
    
    except Exception as e:
        logger.error(f"Error retrieving messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении сообщений",
        )

@router.post("/chat/operator/send-message", response_model=dict)
async def operator_send_message(
    request: OperatorMessageRequest,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Отправить сообщение от имени оператора.
    """
    try:
        # Проверяем токен
        user = await get_current_user(db, token=token)
        if user.role not in ["responder", "admin"]:
            logger.warning(f"Unauthorized message send: user_id={user.id}, role={user.role}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ только для операторов",
            )
        
        # Проверяем существование инцидента
        incident = await get_incident(db, id=request.incident_id)
        if not incident:
            logger.warning(f"Incident not found: incident_id={request.incident_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Инцидент не найден",
            )
        
        # Создаем сообщение
        operator_prefix = f"[{request.operator_name}] "
        message_data = ChatMessageCreate(
            content=f"{operator_prefix}{request.message}",
            incident_id=request.incident_id,
        )
        
        message = await create_chat_message(
            db, obj_in=message_data, sender_id=user.id
        )
        
        # Отправляем через WebSocket
        await chat_manager.broadcast_message(
            incident_id=request.incident_id,
            message={
                "type": "new_message",
                "data": {
                    "id": message.id,
                    "content": message.content,
                    "sender_id": message.sender_id,
                    "sender_name": request.operator_name,
                    "sent_at": message.sent_at.isoformat(),
                    "is_read": message.is_read,
                    "is_operator": True,
                }
            }
        )
        
        logger.info(f"Operator sent message: user_id={user.id}, incident_id={request.incident_id}, content={request.message}")
        
        return {
            "success": True,
            "message_id": message.id,
            "incident_id": request.incident_id,
            "sent_at": message.sent_at.isoformat(),
        }
    
    except HTTPException as e:
        logger.warning(f"Token validation failed: {str(e)}")
        raise
    
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при отправке сообщения: {str(e)}",
        ) 