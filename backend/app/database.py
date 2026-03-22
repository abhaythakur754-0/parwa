"""
Async Database connection module using SQLAlchemy and asyncpg.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger("database")
settings = get_settings()

# Determine the database URL
# asyncpg requires postgresql+asyncpg:// format
db_url = str(settings.database_url)
# Only add the asyncpg dialect if it's not already there
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create the Async Engine
try:
    engine: AsyncEngine = create_async_engine(
        db_url,
        echo=settings.debug,
        future=True,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True, # Verify connection liveness before checking out from pool
    )
except Exception as e:
    logger.error(f"Failed to create async DB engine: {str(e)}")
    raise

# Create the async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Declarative base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session.
    Automatically handles commit/rollback and closes the session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Database session rollback due to exception", exc_info=e)
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """
    Utility function to verify DB connection (useful for health checks).
    """
    from sqlalchemy import text
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {str(e)}")
        return False
