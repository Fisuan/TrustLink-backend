import json
from typing import Any, Optional

import redis.asyncio as redis
from app.core.config import settings

# Создание подключения к Redis
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    decode_responses=True,
)

async def set_key(key: str, value: Any, expire: int = None) -> bool:
    """Сохранить значение в Redis с опциональным TTL."""
    serialized_value = json.dumps(value)
    await redis_client.set(key, serialized_value)
    if expire:
        await redis_client.expire(key, expire)
    return True

async def get_key(key: str) -> Optional[Any]:
    """Получить значение из Redis."""
    value = await redis_client.get(key)
    if value:
        return json.loads(value)
    return None

async def delete_key(key: str) -> bool:
    """Удалить ключ из Redis."""
    return await redis_client.delete(key) > 0

async def publish_message(channel: str, message: Any) -> int:
    """Опубликовать сообщение в канал Redis."""
    serialized_message = json.dumps(message)
    return await redis_client.publish(channel, serialized_message)

async def subscribe_to_channel(channel: str):
    """Подписаться на канал Redis."""
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)
    return pubsub
