from datetime import timedelta
from typing import Any
import traceback
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.core.config import settings
from app.db.session import get_db
from app.schemas import Token, UserCreate, User
from app.crud.user import get_user_by_email, create_user, authenticate_user

# Настройка логгера
logger = logging.getLogger("app.auth")
logger.setLevel(logging.INFO)
# Настройка вывода логов в файл и консоль
if not logger.handlers:
    file_handler = logging.FileHandler("auth.log")
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

router = APIRouter()


@router.post("/auth/login", response_model=Token)
async def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get access token for user from login credentials.
    """
    try:
        logger.info(f"Login attempt: username={form_data.username}")
        user = await authenticate_user(db, email=form_data.username, password=form_data.password)
        
        if not user:
            logger.warning(f"Login failed - incorrect credentials: username={form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        elif not user.is_active:
            logger.warning(f"Login failed - inactive account: username={form_data.username}, user_id={user.id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is not active",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        token = create_access_token(
            subject=user.id, expires_delta=access_token_expires
        )
        
        logger.info(f"Login successful: username={form_data.username}, user_id={user.id}")
        return {
            "access_token": token,
            "token_type": "bearer",
        }
    except HTTPException:
        raise
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Login error: username={form_data.username}, error={str(e)}\n{error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during login",
        )


@router.post("/auth/register", response_model=User)
async def register_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Register a new user.
    """
    try:
        logger.info(f"Registration attempt: email={user_in.email}")
        
        # Check if user already exists
        existing_user = await get_user_by_email(db, email=user_in.email)
        if existing_user:
            logger.warning(f"Registration failed - email already registered: email={user_in.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        
        # Установка роли по умолчанию, если не указана
        if not user_in.role:
            user_in.role = "citizen"
        
        # Create new user
        user = await create_user(db, obj_in=user_in)
        logger.info(f"Registration successful: email={user_in.email}, user_id={user.id}, role={user.role}")
        return user
    except HTTPException:
        raise
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Registration error: email={user_in.email}, error={str(e)}\n{error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during registration",
        ) 