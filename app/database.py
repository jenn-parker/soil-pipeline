import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# Fallback to local default if env vars aren't injected by Docker Compose
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://postgres:postgres@localhost:5432/soil_db"
)

# 1. Create the Async Engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    future=True
)

# 2. Configure the Async Session Factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# 3. Base class for declarative models
class Base(DeclarativeBase):
    pass

# 4. FastAPI Dependency injection tool
async def get_db_session() -> AsyncSession: # type: ignore
    """FastAPI dependency yielding an async database session per request."""
    async with async_session_factory() as session:
        try:
            yield session # type: ignore
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
