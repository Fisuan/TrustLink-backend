import logging
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.base_class import Base
from app.models import User, UserRole

from app.models import Incident, ChatMessage, Attachment


async def init_db(engine: AsyncEngine) -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logging.info("Database tables initialized")


async def create_initial_data(session) -> None:
    """Create initial data in the database."""
    from app.core.security import get_password_hash
    
    admin = await session.query(User).filter(
        User.email == "admin@trustlink.com"
    ).first()
    
    if not admin:
        admin_user = User(
            email="admin@trustlink.com",
            hashed_password=get_password_hash("admin123"),
            full_name="TrustLink Admin",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        session.add(admin_user)
        await session.commit()
        logging.info("Admin user created")
    
    logging.info("Initial data created") 