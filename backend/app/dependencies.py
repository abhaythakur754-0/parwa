"""
Shared FastAPI dependencies for the PARWA backend.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import AsyncSessionLocal, logger


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.
    Ensures session is properly committed/rolled back and closed.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Database session rollback in dependency", exc_info=e)
            raise
        finally:
            await session.close()
